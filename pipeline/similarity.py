#!/usr/bin/env python3
"""Content similarity between videos and courses, so an institutional lecture is not an island.

96% of the catalog has no co-recommendation data (nobody linked two course lectures in the same comment), so the
`rel` graph connects almost nothing in the institutional tier. This adds a second graph from the content itself:
TF-IDF over each video's title, summary, keywords, topic names, series name and lecturer (unigrams and bigrams),
cosine similarity, and for every video the nearest other videos and the nearest other *courses*. Watch a Chomsky
lecture in an intro cognitive-science course and the linguistics courses come up.

Called by build_catalog.py before the export; also runnable alone on the built export for a look:

    python3 pipeline/similarity.py            # prints neighbours for a few sample videos

Design notes:
- plain TF-IDF rather than a neural embedding: it needs no model download (the build runs offline), it is
  reproducible, and its reasons are legible — the site shows the shared terms next to each suggestion;
- diversity over raw nearest: at most two neighbours from the same series and at least half from other
  series/channels when available, so the list continues the subject rather than listing the next lectures
  of the same course (the series page already does that);
- indices, not ids, in the export: `sim` is a list of indices into `videos[]`, `simc` into `series[]`
  (about 1 MB for 16,000 videos instead of 2.5 MB of 11-character ids).
"""
import json
import os
import re
import sys

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)

K_VIDEOS = 8          # neighbours kept per video
K_SERIES = 3          # related courses kept per video
MIN_SIM = 0.12        # below this a neighbour is noise
PER_SERIES_CAP = 2    # at most this many neighbours from one series

STOP = set("""a an and are as at be been being but by can could did do does for from had has have he her hers him his how i if in into is it
its just me more most my no nor not of off on once only or other our ours out over own same she should so some such than that the their theirs
them then there these they this those through to too under until up us very was we were what when where which while who whom why will with
would you your yours lecture lectures lec part session class week introduction intro video full course module unit talk talks seminar
psychology psychological dr prof professor university college""".split())


def tok(s):
    return [t for t in re.findall(r"[a-z][a-z0-9'-]+", (s or "").lower()) if t not in STOP and len(t) > 2]


def video_text(v, series_by_id, topics):
    sd = series_by_id.get(v.get("series")) if v.get("series") else None
    parts = [v.get("title", "")] * 3 + [v.get("why", ""), v.get("summary", ""), " ".join(v.get("kw") or [])]
    parts += [topics.get(t, {}).get("name", "") for t in v.get("topics", [])] * 2
    if sd:
        parts += [sd.get("name", ""), sd.get("lecturer", "")]
    if v.get("orig"):
        parts += [v["orig"].get("what", "") or "", v["orig"].get("people", "") or ""]
    return " ".join(tok(" ".join(parts)))


def series_text(sd, by_id, topics):
    parts = [sd.get("name", "")] * 2 + [sd.get("lecturer", ""), sd.get("note", "") or "", sd.get("unit", "") or ""]
    parts += [topics.get(t, {}).get("name", "") for t in sd.get("topics", [])]
    parts += [by_id[i]["title"] for i in sd.get("vids", [])[:60] if i in by_id]
    return " ".join(tok(" ".join(parts)))


GLOVE_GZ = P("work", "sim", "glove-wiki-gigaword-300.gz")       # gensim-data release of GloVe (Wikipedia + Gigaword, 300-d, 400k words)
GLOVE_SUBSET = P("work", "sim", "glove300.subset.npz")           # the rows our vocabulary uses, cached after the first pass
GLOVE_URL = "https://github.com/piskvorky/gensim-data/releases/download/glove-wiki-gigaword-300/glove-wiki-gigaword-300.gz"


def load_glove(vocab):
    """Word vectors for the words we use, from the cached subset or by streaming the 394 MB release once.
    Returns (word -> row index, matrix) or None when neither file is there (the build then uses TF-IDF alone)."""
    import gzip
    if os.path.exists(GLOVE_SUBSET):
        z = np.load(GLOVE_SUBSET, allow_pickle=False)
        words = [w for w in z["words"].tolist()]
        idx = {w: i for i, w in enumerate(words)}
        missing = [w for w in vocab if w not in idx]
        if len(missing) < 0.02 * max(1, len(vocab)) or not os.path.exists(GLOVE_GZ):
            return idx, z["vectors"]
    if not os.path.exists(GLOVE_GZ):
        return None
    want = set(vocab)
    rows, words = [], []
    with gzip.open(GLOVE_GZ, "rt", encoding="utf-8") as f:
        first = f.readline().split()
        if len(first) > 2:                                # no header line in this release: the first line is a word
            if first[0] in want:
                words.append(first[0]); rows.append(np.array(first[1:], dtype=np.float32))
        for line in f:
            sp = line.find(" ")
            w = line[:sp]
            if w in want:
                words.append(w); rows.append(np.fromstring(line[sp + 1:], sep=" ", dtype=np.float32))
    M = np.vstack(rows) if rows else np.zeros((0, 300), dtype=np.float32)
    np.savez_compressed(GLOVE_SUBSET, words=np.array(words), vectors=M)
    return {w: i for i, w in enumerate(words)}, M


def doc_vectors(texts, vec, glove):
    """IDF-weighted mean of word vectors per document, L2-normalised (rows of zeros for documents with no known word)."""
    idx, M = glove
    vocab = vec.vocabulary_
    idf = vec.idf_
    out = np.zeros((len(texts), M.shape[1]), dtype=np.float32)
    for i, t in enumerate(texts):
        acc = np.zeros(M.shape[1], dtype=np.float32); wsum = 0.0
        for w in t.split():
            j = idx.get(w)
            if j is None:
                continue
            wt = idf[vocab[w]] if w in vocab else 1.0
            acc += wt * M[j]; wsum += wt
        if wsum > 0:
            acc /= wsum
            nrm = np.linalg.norm(acc)
            if nrm > 0:
                out[i] = acc / nrm
    return out


def compute(videos, series, areas):
    """Annotate videos[i]["sim"], videos[i]["simc"] and series[j]["sim"] in place. Returns a stats dict."""
    topics = {t["id"]: t for a in areas for t in a["topics"]}
    by_id = {v["id"]: v for v in videos}
    series_by_id = {s["id"]: s for s in series}
    vtexts = [video_text(v, series_by_id, topics) for v in videos]
    stexts = [series_text(s, by_id, topics) for s in series]
    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_df=0.4, sublinear_tf=True, dtype=np.float32)
    X = vec.fit_transform(vtexts)                         # videos × terms, L2-normalised rows
    S = vec.transform(stexts) if series else None         # series × terms
    # semantic half: GloVe word vectors averaged per document (IDF-weighted), so "Chomsky" sits near "linguistics" and
    # "syntax" even when the words differ. Blended 50/50 with the lexical TF-IDF cosine; TF-IDF alone when the vectors
    # are not on disk (work/sim/, see GLOVE_URL), so the build never depends on a download.
    glove = load_glove(sorted({w for t in vtexts + stexts for w in t.split()}))
    if glove is not None:
        E = doc_vectors(vtexts, vec, glove)               # videos × 300
    else:
        E = None
    BLEND = 0.35                                           # videos: mostly lexical, a semantic nudge
    # courses are matched lexically only: averaging a whole course's titles into one word vector drifts to a generic
    # "brain" centroid, and big talk collections then win everywhere. A taught course counts a little more than a talk
    # collection, so "courses that go deeper" prefers courses.
    s_kind = np.array([1.0 if sd.get("kind") in ("course", "series") else 0.85 for sd in series], dtype=np.float32) if series else None
    v_series = np.array([series_by_id[v["series"]]["_j"] if v.get("series") in series_by_id else -1 for v in videos]) if series else np.full(len(videos), -1)
    # a gentle legitimacy factor on the ordering of neighbours (not on who qualifies): an institution's own lecture or a
    # shelf copy before an unverified lecturer's channel or a podcast when the text similarity is close
    def legit(v):
        if v.get("inst") and v["inst"].get("ok") is False:
            return 0.8
        if v.get("inst") or v.get("orig"):
            return 1.0
        return 0.9
    w = np.array([legit(v) for v in videos], dtype=np.float32)
    norm_title = [re.sub(r"\W+", " ", (v.get("title") or "").lower()).strip() for v in videos]
    n = len(videos)
    stats = {"sim_videos": 0, "sim_series": 0, "sim_empty": 0}
    CH = 1500
    for start in range(0, n, CH):
        block = X[start:start + CH]
        sims = (block @ X.T).toarray()                    # chunk × n
        if E is not None:
            sims = (1 - BLEND) * sims + BLEND * (E[start:start + CH] @ E.T)
        for r in range(sims.shape[0]):
            i = start + r
            row = sims[r] * w
            row[i] = -1.0
            cand = np.argpartition(-row, min(60, n - 1))[:60]
            cand = cand[np.argsort(-row[cand])]
            picked, per_series, other, seen_titles = [], {}, 0, {norm_title[i]}
            for j in cand:
                if row[j] < MIN_SIM:
                    break
                if norm_title[j] in seen_titles:
                    continue                                  # the same talk under another upload is not a neighbour
                seen_titles.add(norm_title[j])
                sj = v_series[j]
                same = sj >= 0 and sj == v_series[i]
                if sj >= 0 and per_series.get(sj, 0) >= PER_SERIES_CAP:
                    continue                                  # two per course at most, including another run of the same course
                if sj >= 0:
                    per_series[sj] = per_series.get(sj, 0) + 1
                picked.append(int(j))
                if not same:
                    other += 1
                if len(picked) >= K_VIDEOS:
                    break
            if picked:
                videos[i]["sim"] = picked
                stats["sim_videos"] += 1
            else:
                stats["sim_empty"] += 1
        if S is not None:
            ssims = (block @ S.T).toarray() * s_kind       # chunk × series
            for r in range(ssims.shape[0]):
                i = start + r
                row = ssims[r]
                if v_series[i] >= 0:
                    row[v_series[i]] = -1.0
                top = np.argsort(-row)[:K_SERIES]
                top = [int(j) for j in top if row[j] >= MIN_SIM and series[j].get("inst")]   # related *courses*: the institutional tier
                if top:
                    videos[i]["simc"] = top
                    stats["sim_series"] += 1
    stats["sim_semantic"] = int(E is not None)
    if S is not None and len(series) > 1:
        ss = (S @ S.T).toarray() * s_kind
        np.fill_diagonal(ss, -1.0)
        for j, sd in enumerate(series):
            top = np.argsort(-ss[j])[:6]
            sd["sim"] = [int(k) for k in top if ss[j][k] >= MIN_SIM]
    return stats


if __name__ == "__main__":
    data = json.load(open(P("site", "data", "psychtube.json"), encoding="utf-8"))
    for j, s in enumerate(data["series"]):
        s["_j"] = j
    st = compute(data["videos"], data["series"], data["areas"])
    print(st)
    by_idx = data["videos"]
    want = [v for v in by_idx if re.search(r"chomsky", v["title"], re.I)][:2] + [v for v in by_idx if re.search(r"prosopagnosia", v["title"], re.I)][:1] + [v for v in by_idx if re.search(r"placebo", v["title"], re.I)][:1]
    for v in want:
        print("\n##", v["title"][:70], "|", v.get("ch"))
        for j in v.get("sim", []):
            print("   ~", by_idx[j]["title"][:60], "|", by_idx[j].get("ch"))
        for j in v.get("simc", []):
            print("   course:", data["series"][j]["name"][:60], "|", data["series"][j].get("inst"))
