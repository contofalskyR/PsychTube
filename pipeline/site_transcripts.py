#!/usr/bin/env python3
"""Turn the fetched official transcripts (work/transcripts/text/<pid>.json, from the transcripts workflow) into what the
site serves and what the build indexes.

    python3 pipeline/site_transcripts.py

Writes site/data/tr/<pid>.json      {video_id: {"src": url, "p": [paragraph, ...]}}   fetched by the watch page on demand
       work/transcripts/tkw.json    {video_id: [term, ...]}  the lecture's most distinctive terms (TF-IDF against the other
                                    transcripts), which build_catalog.py puts on the lecture as `tkw` for search and similarity
       work/transcripts/index.json  {pid: {"n": lectures with text, "words": total}}

Paragraphing: OCW PDFs come out as one long run with occasional blank lines; the speech is cut at sentence ends into
paragraphs of about 90–140 words so a reader can scan it. The OCW header ("The following content is provided under a
Creative Commons license...") is kept in the attribution line, not in the text.
"""
import collections
import glob
import json
import math
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)

OCW_HEADER = re.compile(r"^.*?(?:Your support will help MIT OpenCourseWare continue to offer high[- ]quality educational resources for free\.?\s*"
                        r"(?:To make a donation,? or (?:to )?view additional materials from hundreds of MIT courses,? visit MIT OpenCourseWare at ocw\.mit\.edu\.?)?)", re.S | re.I)
STOP = set("""a about above after again against all also am an and any are as at be because been before being below between both but by can
could did do does doing don down during each few for from further had has have having he her here hers herself him himself his how i if in
into is it its itself just let's like me more most my myself no nor not now of off on once only or other ought our ours ourselves out over
own same she should so some such than that the their theirs them themselves then there these they this those through to too under until up
very was we were what when where which while who whom why will with would you your yours yourself yourselves yeah okay ok right really
thing things kind sort going get got lot lots say said says see look looks mean means way ways one two three know think thought actually
basically little bit good well much many make made want wants people something anything everything nothing somebody anybody course lecture
question questions answer answers example examples called call talk talking talked today next last first second time times year years
professor students student class slide slides audience inaudible laughter applause um uh yes yep hmm let put take gets goes come comes
different same another back still even ever never always maybe probably pretty quite sure course""".split())


def paragraphs(text, lo=90, hi=140):
    text = re.sub(r"\s+", " ", text).strip()
    sents = re.split(r"(?<=[.!?])\s+(?=[A-Z\"“])", text)
    out, cur, n = [], [], 0
    for s in sents:
        w = len(s.split())
        if n and n + w > hi:
            out.append(" ".join(cur)); cur, n = [], 0
        cur.append(s); n += w
        if n >= lo:
            out.append(" ".join(cur)); cur, n = [], 0
    if cur:
        out.append(" ".join(cur))
    return out


def clean_ocw(text):
    text = OCW_HEADER.sub("", text, count=1) if "OpenCourseWare" in text[:1200] else text
    text = re.sub(r"\[?(SQUEAKING|RUSTLING|CLICKING|MUSIC PLAYING|LAUGHTER|APPLAUSE|INAUDIBLE)\]?", " ", text)
    return text.strip()


def tokens(text):
    return [t for t in re.findall(r"[a-z][a-z'-]{2,}", text.lower()) if t not in STOP and not t.endswith("'s") or (t.endswith("'s") and t[:-2] not in STOP and len(t) > 5)]


def main():
    files = sorted(glob.glob(P("work", "transcripts", "text", "*.json")))
    if not files:
        raise SystemExit("no transcripts in work/transcripts/text/ (download the workflow artifact first)")
    os.makedirs(P("site", "data", "tr"), exist_ok=True)
    docs = {}          # vid -> token list
    index = {}
    for f in files:
        pid = os.path.basename(f)[:-5]
        d = json.load(open(f, encoding="utf-8"))
        out = {}
        words = 0
        for vid, r in d.items():
            text = clean_ocw(r["text"]) if "ocw.mit.edu" in r["src"] else re.sub(r"\s+", " ", r["text"]).strip()
            if len(text.split()) < 200:
                continue
            paras = paragraphs(text)
            out[vid] = {"src": r["src"], "p": paras}
            docs[vid] = tokens(text)
            words += len(text.split())
        if out:
            json.dump(out, open(P("site", "data", "tr", f"{pid}.json"), "w", encoding="utf-8"), ensure_ascii=False)
            index[pid] = {"n": len(out), "words": words}
    # distinctive terms: tf-idf over the transcript corpus, unigrams; keep terms that occur at least 3 times in the lecture
    df = collections.Counter()
    for toks in docs.values():
        df.update(set(toks))
    N = len(docs)
    tkw = {}
    for vid, toks in docs.items():
        tf = collections.Counter(toks)
        scored = sorted(((c * math.log((N + 1) / (df[t] + 0.5)), t) for t, c in tf.items() if c >= 3), reverse=True)
        tkw[vid] = [t for _, t in scored[:12]]
    json.dump(tkw, open(P("work", "transcripts", "tkw.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    json.dump(index, open(P("work", "transcripts", "index.json"), "w", encoding="utf-8"), indent=1)
    print(f"{len(docs)} lectures with text in {len(index)} courses; {sum(v['words'] for v in index.values()):,} words; site/data/tr/ "
          f"{sum(os.path.getsize(P('site', 'data', 'tr', f'{pid}.json')) for pid in index) / 1e6:.1f} MB")
    for vid in list(tkw)[:3]:
        print(" ", vid, tkw[vid])


if __name__ == "__main__":
    main()
