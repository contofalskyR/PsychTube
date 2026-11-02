#!/usr/bin/env python3
"""Bundle the whole site into one self-contained file: PsychTube.html (CSS, data and app inlined).

Open it directly, email it, drop it on any host. Thumbnails hotlink to YouTube's image CDN and the
player embeds from youtube-nocookie.com, so it needs internet but no server.
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)

html = open(P("site", "index.html"), encoding="utf-8").read()
css = open(P("site", "styles.css"), encoding="utf-8").read()
data = open(P("site", "data.js"), encoding="utf-8").read()
app = open(P("site", "app.js"), encoding="utf-8").read()

# </script> inside a JSON string would end the inline script early; escape defensively
safe = lambda s: s.replace("</script", "<\\/script")

html = html.replace('<link rel="stylesheet" href="styles.css">', "<style>\n" + css + "\n</style>")
html = html.replace('<script src="data.js"></script>', "<script>\n" + safe(data) + "\n</script>")
html = html.replace('<script src="app.js"></script>', "<script>\n" + safe(app) + "\n</script>")
assert "styles.css" not in html and 'src="data.js"' not in html and 'src="app.js"' not in html

out = P("PsychTube.html")
open(out, "w", encoding="utf-8").write(html)
print(f"wrote {out} ({os.path.getsize(out) / 1e6:.1f} MB)")
