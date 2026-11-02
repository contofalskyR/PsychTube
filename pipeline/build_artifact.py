#!/usr/bin/env python3
"""Build the hosted (claude.ai artifact) variant of the site into site/hosted/.

The hosted frame forbids third-party iframes and images, so this variant embeds small
mid-video thumbnails as data URIs (raw/youtube/thumbs_*.json) and links out to YouTube
instead of embedding a player. Everything else is the same app.js.
"""
import glob
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
OUT = P("site", "hosted")
os.makedirs(OUT, exist_ok=True)

index = open(P("site", "index.html"), encoding="utf-8").read()
css = open(P("site", "styles.css"), encoding="utf-8").read()
body = re.search(r"<body>(.*)</body>", index, re.S).group(1)
body = re.sub(r"\s*<script src=\"[^\"]+\"></script>", "", body)
fonts = re.search(r'<link href="(https://fonts.googleapis.com/[^"]+)" rel="stylesheet">', index).group(1)

# sticky header respects the phone's top inset in the hosted frame
css = css.replace("position: sticky; top: 0; z-index: 20;", "position: sticky; top: env(safe-area-inset-top, 0px); z-index: 20;")
css = css.replace("position: sticky; top: 60px; align-self: start; height: calc(100vh - 60px);",
                  "position: sticky; top: calc(60px + env(safe-area-inset-top, 0px)); align-self: start; height: calc(100vh - 60px - env(safe-area-inset-top, 0px));")

page = f"""<meta charset="utf-8">
<title>PsychTube</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link href="{fonts}" rel="stylesheet">
<style>
{css}
body::before {{ content: ""; position: fixed; inset: 0 0 auto; height: env(safe-area-inset-top, 0px); z-index: 30; background: var(--bg); }}
</style>
<script>window.PT_ARTIFACT = true;</script>
{body.strip()}
<script src="data.js" charset="utf-8"></script>
<script src="thumbs.js" charset="utf-8"></script>
<script src="app.js" charset="utf-8"></script>
"""
open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(page)

thumbs = {}
for f in sorted(glob.glob(P("raw", "youtube", "thumbs_*.json"))):
    thumbs.update(json.load(open(f)))
catalog_ids = {v["id"] for v in json.load(open(P("site", "data", "psychtube.json")))["videos"]}
thumbs = {k: v for k, v in thumbs.items() if k in catalog_ids}
with open(os.path.join(OUT, "thumbs.js"), "w", encoding="utf-8") as f:
    f.write("window.PT_THUMBS = ")
    json.dump(thumbs, f, separators=(",", ":"))
    f.write(";\n")
for name in ("app.js", "data.js"):
    open(os.path.join(OUT, name), "w", encoding="utf-8").write(open(P("site", name), encoding="utf-8").read())

total = sum(os.path.getsize(os.path.join(OUT, n)) for n in os.listdir(OUT))
print(f"hosted variant: {len(thumbs)}/{len(catalog_ids)} thumbnails embedded, {total/1e6:.1f} MB total in site/hosted/")
