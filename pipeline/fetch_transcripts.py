#!/usr/bin/env python3
"""Fetch the providers' official transcripts for the catalog's MIT OpenCourseWare and Open Yale Courses lectures.
Runs in the transcripts workflow (a machine that can reach ocw.mit.edu and oyc.yale.edu; the build machine cannot).

    python3 pipeline/fetch_transcripts.py [--limit N]

Reads  work/transcripts/plan.json   (pipeline/transcripts.py plan): per course the provider, its base URL and our video ids
Writes work/transcripts/checked.json            {video_id: {"pid", "p", "src": transcript url, "status", "words"}}
       work/transcripts/text/<pid>.json          {video_id: {"src": url, "text": "..."}}
       work/transcripts/oyc_sample.html          one Open Yale Courses lecture page as fetched (to check the extraction against)

MIT OCW: the course site is crawled (course page -> video galleries -> one resource page per video); each resource page
embeds the YouTube id and links the transcript PDF (<hash>_<id>.pdf) and usually the captions (<hash>_<id>.srt). The
captions are the cleaner text, so they are preferred and the PDF (pypdf) is the fallback. Open Yale Courses: the lecture
page carries the transcript. Both are CC BY-NC-SA; the site shows them with that attribution. One request at a time.
"""
import html
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
UA = "PsychTube transcript fetch (github.com/contofalskyR/PsychTube; one request at a time)"
PAUSE = 0.35


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
            time.sleep(PAUSE)
            return r.status, data, r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        time.sleep(PAUSE)
        return e.code, b"", ""
    except Exception as e:                      # noqa: BLE001 - any network failure is a miss, recorded as 0
        print("ERR", url, e, file=sys.stderr)
        return 0, b"", ""


def pdf_text(data):
    from pypdf import PdfReader
    rd = PdfReader(io.BytesIO(data))
    pages = []
    for pg in rd.pages:
        try:
            pages.append(pg.extract_text() or "")
        except Exception:                        # noqa: BLE001
            pages.append("")
    txt = "\n".join(pages)
    txt = re.sub(r"\r", "", txt)
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt.strip()


def srt_text(data):
    """SubRip captions -> running text (cue numbers and timestamps dropped, lines joined, tags removed)."""
    t = data.decode("utf-8", "replace").replace("﻿", "")
    out = []
    for block in re.split(r"\n\s*\n", t):
        lines = [ln.strip() for ln in block.strip().splitlines()]
        lines = [ln for ln in lines if ln and not re.fullmatch(r"\d+", ln) and "-->" not in ln]
        if lines:
            out.append(" ".join(lines))
    txt = " ".join(out)
    txt = re.sub(r"<[^>]+>", "", txt)
    txt = html.unescape(txt)
    txt = re.sub(r"\s+", " ", txt)
    return txt.strip()


def links(page, base):
    return [urllib.parse.urljoin(base, m) for m in re.findall(r'href="([^"#]+)"', page.decode("utf-8", "replace"))]


def crawl_ocw(base, want_ids):
    """Resource pages under an OCW course -> {youtube_id: {"pdf": url|None, "srt": url|None, "page": url}} for the ids we want."""
    found = {}
    st, home, _ = get(base)
    if st != 200:
        print("OCW course page", st, base, file=sys.stderr)
        return found
    galleries = sorted({u for u in links(home, base) if "/video_galleries/" in u and u.startswith(base)})
    pages = {u for u in links(home, base) if "/resources/" in u and u.startswith(base)}
    for g in galleries:
        st, gp, _ = get(g)
        if st == 200:
            pages |= {u for u in links(gp, base) if "/resources/" in u and u.startswith(base)}
    pages = sorted(u if u.endswith("/") else u + "/" for u in pages)
    print(f"  {len(galleries)} galleries, {len(pages)} resource pages under {base}", flush=True)
    for u in pages:
        if len(found) >= len(want_ids):
            break
        st, rp, _ = get(u)
        if st != 200:
            continue
        h = rp.decode("utf-8", "replace")
        m = re.search(r"youtube(?:-nocookie)?\.com/embed/([\w-]{11})", h)
        if not m or m.group(1) not in want_ids or m.group(1) in found:
            continue
        vid = m.group(1)
        pdf = re.search(r'href="([^"]+_' + re.escape(vid) + r'\.pdf)"', h)
        srt = re.search(r'href="([^"]+_' + re.escape(vid) + r'\.(?:srt|vtt))"', h)
        found[vid] = {"page": u, "pdf": urllib.parse.urljoin(u, pdf.group(1)) if pdf else None, "srt": urllib.parse.urljoin(u, srt.group(1)) if srt else None}
    return found


def oyc_transcript(page):
    """The transcript section of an Open Yale Courses lecture page, as text."""
    h = page.decode("utf-8", "replace")
    m = (re.search(r"(?is)<h\d[^>]*>\s*Transcript\s*</h\d>(.*)", h) or re.search(r'(?is)id="transcript"[^>]*>(.*)', h)
         or re.search(r'(?is)class="[^"]*transcript[^"]*"[^>]*>(.*)', h) or re.search(r"(?is)>\s*Transcript\s*<(.*)", h))
    if not m:
        return ""
    body = m.group(1)
    body = re.split(r"(?is)<footer|<div[^>]+class=\"[^\"]*(?:footer|region-footer|block-menu)", body)[0]
    body = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", body)
    body = re.sub(r"(?i)</(p|div|li|h\d|br)\s*>|<br\s*/?>", "\n\n", body)
    body = re.sub(r"<[^>]+>", " ", body)
    body = html.unescape(body)
    body = re.sub(r"[ \t\xa0]+", " ", body)
    body = re.sub(r"\n\s*\n(\s*\n)+", "\n\n", body)
    return body.strip()


def main():
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    plan = json.load(open(P("work", "transcripts", "plan.json"), encoding="utf-8"))
    if limit:
        plan = plan[:limit]
    os.makedirs(P("work", "transcripts", "text"), exist_ok=True)
    checked, texts = {}, {}
    sample_saved = False
    by_course = {}
    for r in plan:
        by_course.setdefault((r["pid"], r["p"], r["base"]), []).append(r)
    for (pid, p, base), rows in by_course.items():
        print(f"{p} {base} ({len(rows)} lectures)", flush=True)
        if p == "ocw":
            want = {r["vid"] for r in rows}
            found = crawl_ocw(base, want)
            for r in rows:
                f = found.get(r["vid"])
                rec = {"pid": pid, "p": p, "src": None, "status": 404, "words": 0}
                text = ""
                if f:
                    if f["srt"]:
                        st, data, _ = get(f["srt"])
                        if st == 200 and data:
                            text, rec["src"], rec["status"] = srt_text(data), f["pdf"] or f["srt"], 200
                    if not text and f["pdf"]:
                        st, data, _ = get(f["pdf"])
                        if st == 200 and data:
                            try:
                                text = pdf_text(data)
                            except Exception as e:   # noqa: BLE001
                                print("PDF fail", f["pdf"], e, file=sys.stderr)
                            rec["src"], rec["status"] = f["pdf"], 200
                    rec["page"] = f["page"]
                    if f["pdf"]:
                        rec["pdf"] = f["pdf"]
                if text:
                    rec["words"] = len(text.split())
                    texts.setdefault(pid, {})[r["vid"]] = {"src": rec["src"], "text": text}
                checked[r["vid"]] = rec
                print(f"  {r['vid']} {rec['status']} {rec['words']}w {rec.get('src') or ''}", flush=True)
        else:
            for r in rows:
                st, data, _ = get(r["url"])
                rec = {"pid": pid, "p": p, "src": r["url"], "status": st, "words": 0}
                text = ""
                if st == 200 and data:
                    if not sample_saved:
                        open(P("work", "transcripts", "oyc_sample.html"), "wb").write(data)
                        sample_saved = True
                    text = oyc_transcript(data)
                if text:
                    rec["words"] = len(text.split())
                    texts.setdefault(pid, {})[r["vid"]] = {"src": r["url"], "text": text}
                checked[r["vid"]] = rec
                print(f"  {r['vid']} {st} {rec['words']}w {r['url']}", flush=True)
    json.dump(checked, open(P("work", "transcripts", "checked.json"), "w", encoding="utf-8"), indent=0)
    for pid, d in texts.items():
        json.dump(d, open(P("work", "transcripts", "text", f"{pid}.json"), "w", encoding="utf-8"), ensure_ascii=False)
    ok = sum(1 for s in checked.values() if 200 <= s["status"] < 400)
    print(f"{ok}/{len(checked)} present; text for {sum(len(d) for d in texts.values())} lectures in {len(texts)} courses")


if __name__ == "__main__":
    main()
