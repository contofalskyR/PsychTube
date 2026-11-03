#!/usr/bin/env python3
"""Re-run the data checks behind review/REVIEW.md against the current export. Offline; reads site/data/psychtube.json,
raw/ and work/. Usage: python3 review/tools/audit_data.py  (prints one line per check; nothing is written)."""
import collections
import glob
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
P = lambda *a: os.path.join(ROOT, *a)
D = json.load(open(P("site", "data", "psychtube.json"), encoding="utf-8"))
V, C = D["videos"], D["contested"]
S = {s["id"]: s for s in D["series"]}
byId = {v["id"]: v for v in V}
meta = {}
for f in sorted(glob.glob(P("raw", "youtube", "meta_*.json"))):
    meta.update(json.load(open(f, encoding="utf-8")))
courses = json.load(open(P("raw", "institutional", "courses.json"), encoding="utf-8"))["courses"]
by_pid = {c["pid"]: c for c in courses}
out = lambda k, v: print(f"{k:58s} {v}")

inst_series = [s for s in D["series"] if s.get("inst")]
out("institutional collections by kind", dict(collections.Counter(s["kind"] for s in inst_series)))
out("institutional lectures by kind", {k: sum(s["n"] for s in inst_series if s["kind"] == k) for k in ("course", "series", "talks")})
ind = [s for s in inst_series if s["inst"].startswith("Independent lecturer")]
out("'Independent lecturer' series / lectures / channels", (len(ind), sum(s["n"] for s in ind), len({s.get("chid") or s.get("ch") for s in ind})))

# provenance: items on a channel other than the playlist owner's
other = [v for v in V if (S.get(v.get("series")) or {}).get("chid") and v.get("chid") and not v.get("p") and v["chid"] != S[v["series"]]["chid"]]
out("lectures on another channel than their playlist owner", f"{len(other)} from {len({v['chid'] for v in other})} channels")
wl = 0
for s in inst_series:
    vs = [byId[x] for x in s["vids"] if not byId[x].get("p")]
    if s.get("chid") and vs and sum(1 for v in vs if v.get("chid") and v["chid"] != s["chid"]) / len(vs) >= 0.5:
        wl += 1
out("playlists where >= half the videos are other channels'", wl)
PODCAST = re.compile(r"podcast|huberman|lex fridman|rogan|tim ferriss|dwarkesh|chris williamson", re.I)
out("long-form podcast items carrying an institutional badge", sum(1 for v in V if v.get("inst") and (v.get("len") or 0) >= 1500 and (PODCAST.search(v.get("ch") or "") or "podcast" in v["title"].lower())))

# triage confidence of what was kept
low = [s for s in inst_series if "list=" in s.get("url", "") and ((by_pid.get(s["url"].split("list=")[-1]) or {}).get("triage") or {}).get("confidence", 1) <= 0.6]
out("collections kept at triage confidence <= 0.6 / lectures", (len(low), sum(s["n"] for s in low)))
unv = re.compile(r"unverif|not evident|ambiguous", re.I)
out("collections whose triage note says unverified/ambiguous", sum(1 for s in inst_series if "list=" in s.get("url", "") and unv.search(((by_pid.get(s["url"].split("list=")[-1]) or {}).get("triage") or {}).get("why") or "")))

# parse slip, language, vouch semantics
out("videos whose channel name is a number (parse slip)", sum(1 for v in V if re.fullmatch(r"[\d.,]+\s*[KMB]?", v.get("ch") or "")))
nonlatin = [v for v in V if re.search(r"[Ѐ-ӿ؀-ۿऀ-ॿ一-鿿]", v["title"])]
out("titles in Cyrillic/Arabic/Devanagari/CJK script", f"{len(nonlatin)} e.g. {[v['title'][:30] for v in nonlatin[:3]]}")
out("videos with mentions but no recommender (cards said N vouches)", sum(1 for v in V if not v.get("nrec") and v.get("nmention") and not v.get("inst") and not v.get("orig")))
out("critique badges on findings that replicated (were Debunk)", sum(1 for v in V if v.get("badge") and v["badge"]["role"] == "critique" and C[v["badge"]["id"]].get("status") == "replicated"))
out("findings with status 'fraud'", sum(1 for c in C.values() if c.get("status") == "fraud"))
tax_md = open(P("pipeline", "classify", "TAXONOMY.md"), encoding="utf-8").read()
out("contested findings the labelers' TAXONOMY.md lists", f"{sum(1 for k in C if '`' + k + '`' in tax_md)} of {len(C)}")

# metadata quality
cat = set(byId)
out("meta playability for catalog videos (keyless fetch)", dict(collections.Counter(meta[i].get("st") for i in cat if i in meta)))
out("unlisted videos in the catalog (where known)", sum(1 for i in cat if (meta.get(i) or {}).get("unl")))
ap = [v for v in V if v.get("approx")]
out("approximate dates / of which = a build month", (len(ap), collections.Counter(v.get("pub") for v in ap).most_common(1)))
out("course/series items under 4 minutes", sum(1 for v in V if v.get("inst") and not v["inst"].get("loose") and (v.get("len") or 999) < 240 and (S.get(v.get("series")) or {}).get("kind") != "talks"))

# canon and ranking
def tier(v):
    if not v.get("len") or v["len"] < 1500: return 0
    if v.get("inst") or v.get("orig"): return 0
    return 2 if v.get("type") == "podcast" or PODCAST.search(v.get("ch") or "") else 1
rank = lambda v: max(v["score"], 1) * [1, .5, .25][tier(v)]
canon_page = [v["id"] for v in sorted([v for v in V if v.get("nrec")], key=lambda v: -(v.get("cscore") or v["score"]))[:12]]
home_row = [v["id"] for v in sorted(V, key=lambda v: (-rank(v), -v["score"]))[:12]]
out("top 12 by legitimacy rank vs by community score, overlap", len(set(canon_page) & set(home_row)))
grp = collections.defaultdict(float)
for s in inst_series:
    if s["kind"] != "talks":
        grp[s["inst"]] += s["pop"] + 0.01 * s["n"]
out("first institution groups on the Courses hub", [g for g, _ in sorted(grp.items(), key=lambda kv: -kv[1])[:3]])
print("\ndone")
