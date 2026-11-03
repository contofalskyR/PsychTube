#!/usr/bin/env python3
"""Fetch the providers' official transcripts listed in work/transcripts/plan.json (runs in the transcripts workflow,
on a machine that can reach ocw.mit.edu and oyc.yale.edu; the build machine cannot).

    python3 pipeline/fetch_transcripts.py [--limit N]

Writes work/transcripts/checked.json            {url: http_status}
       work/transcripts/text/<pid>.json          {video_id: {"src": url, "text": "...", "words": n}}   (plain text, paragraphs by blank line)
       work/transcripts/oyc_sample.html          one Open Yale Courses page as fetched, to check the extraction against

MIT OCW transcripts are PDFs (text extracted with pypdf); Open Yale Courses transcripts are a section of the lecture
page. Both are CC BY-NC-SA; the site shows them with that attribution. One request at a time, a short pause between.
"""
import html
import io
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
UA = "PsychTube transcript fetch (github.com/contofalskyR/PsychTube; one request at a time)"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read(), r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
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
    # OCW transcript PDFs: a header block (course, term, "The following content is provided under a Creative Commons
    # license...") then the speech. Keep the speech; normalise whitespace; paragraphs where the PDF had blank lines.
    txt = re.sub(r"\r", "", txt)
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt.strip()


def oyc_transcript(page):
    """The transcript section of an Open Yale Courses lecture page, as text. The page carries the transcript inline
    (a 'Transcript' heading followed by the speech, with speaker names in bold); everything after the heading and
    before the page footer is kept."""
    h = page.decode("utf-8", "replace")
    m = re.search(r"(?is)<h\d[^>]*>\s*Transcript\s*</h\d>(.*)", h) or re.search(r'(?is)id="transcript"[^>]*>(.*)', h) or re.search(r'(?is)class="[^"]*transcript[^"]*"[^>]*>(.*)', h)
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
    checked = {}
    texts = {}
    sample_saved = False
    for i, r in enumerate(plan):
        st, data, ctype = get(r["url"])
        checked[r["url"]] = st
        text = ""
        if st == 200 and data:
            if r["p"] == "ocw" and (b"%PDF" in data[:8] or "pdf" in ctype):
                try:
                    text = pdf_text(data)
                except Exception as e:           # noqa: BLE001
                    print("PDF fail", r["url"], e, file=sys.stderr)
            elif r["p"] == "oyc":
                if not sample_saved:
                    open(P("work", "transcripts", "oyc_sample.html"), "wb").write(data)
                    sample_saved = True
                text = oyc_transcript(data)
        if text:
            texts.setdefault(r["pid"], {})[r["vid"]] = {"src": r["url"], "text": text, "words": len(text.split())}
        print(f"{i + 1}/{len(plan)} {st} {len(text.split())}w {r['url']}", flush=True)
        time.sleep(0.4)
    json.dump(checked, open(P("work", "transcripts", "checked.json"), "w", encoding="utf-8"), indent=0)
    for pid, d in texts.items():
        json.dump(d, open(P("work", "transcripts", "text", f"{pid}.json"), "w", encoding="utf-8"), ensure_ascii=False)
    ok = sum(1 for s in checked.values() if 200 <= s < 400)
    print(f"{ok}/{len(checked)} present; text for {sum(len(d) for d in texts.values())} lectures in {len(texts)} courses")


if __name__ == "__main__":
    main()
