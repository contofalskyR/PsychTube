def hx(h):
    h = h.lstrip('#'); return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
def lin(c):
    c = c / 255; return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
def L(rgb): r, g, b = (lin(x) for x in rgb); return 0.2126*r + 0.7152*g + 0.0722*b
def cr(a, b):
    la, lb = L(a), L(b); hi, lo = max(la, lb), min(la, lb); return (hi + .05) / (lo + .05)
def mix(fg, bg, a): return tuple(round(f*a + b*(1-a)) for f, b in zip(fg, bg))
T = {
 "dark": dict(bg="#14121d", bg2="#1c1928", bg3="#252136", bg4="#2f2a45", ink="#eeeaf6", ink2="#b5aecb", ink3="#857da0", amber="#e8b04b", amber_text="#f3cc7a", amber_ink="#2a1f05", violet="#a091e0", coral="#f07a5e", mint="#7bd1be", mint_ink="#0a2a24", inst="#86b6e8", focus="#f3cc7a"),
 "light": dict(bg="#f4f3f8", bg2="#ffffff", bg3="#ecebf3", bg4="#e0ddeb", ink="#1a1726", ink2="#4a4560", ink3="#777190", amber="#8f6508", amber_text="#8f6508", amber_ink="#fff6dc", violet="#5b49ae", coral="#be4a33", mint="#1e8a78", mint_ink="#ffffff", inst="#2f6aa8", focus="#5b49ae"),
}
for th, c in T.items():
    C = {k: hx(v) for k, v in c.items()}
    rows = [
      ("faint text (.faint, subs, vouch line) on bg", C["ink3"], C["bg"]),
      ("faint text on bg-2 (boxes)", C["ink3"], C["bg2"]),
      ("faint text on bg-3 (chips/btn)", C["ink3"], C["bg3"]),
      ("muted text on bg", C["ink2"], C["bg"]),
      ("tag: white on coral (thumbnail status tag)", (255,255,255), C["coral"]),
      ("tag.good: mint-ink on mint", C["mint_ink"], C["mint"]),
      ("primary btn: amber-ink on amber", C["amber_ink"], C["amber"]),
      ("chip.reddit: mint on 16% mint over bg", C["mint"], mix(C["mint"], C["bg"], .16)),
      ("chip.hn: amber-text on 18% amber over bg", C["amber_text"], mix(C["amber"], C["bg"], .18)),
      ("chip.se: violet on 16% violet over bg", C["violet"], mix(C["violet"], C["bg"], .16 if th=="dark" else .12)),
      ("chip.inst: inst on 16% inst over bg", C["inst"], mix(C["inst"], C["bg"], .16 if th=="dark" else .12)),
      ("status.s-failed: coral on coral-soft over bg", C["coral"], mix(C["coral"], C["bg"], .16 if th=="dark" else .12)),
      ("box.care h2: coral on coral-soft over bg-2", C["coral"], mix(C["coral"], C["bg2"], .16 if th=="dark" else .12)),
      ("focus ring vs bg (non-text, needs 3:1)", C["focus"], C["bg"]),
      ("search placeholder (ink-3 on bg-3)", C["ink3"], C["bg3"]),
    ]
    print(f"== {th}")
    for name, fg, bg in rows:
        r = cr(fg, bg); print(f"   {r:5.2f}  {'FAIL' if r < 4.5 else 'ok  '}  {name}")

print("\n== proposed")
P = [
 ("dark tag: white on #c9563d", (255,255,255), hx("#c9563d")),
 ("dark tag: #2a0d06 on coral #f07a5e", hx("#2a0d06"), hx("#f07a5e")),
 ("dark ink-3 #8f88aa on bg-3", hx("#8f88aa"), hx("#252136")),
 ("dark ink-3 #8f88aa on bg", hx("#8f88aa"), hx("#14121d")),
 ("light ink-3 #66607e on bg", hx("#66607e"), hx("#f4f3f8")),
 ("light ink-3 #66607e on bg-3", hx("#66607e"), hx("#ecebf3")),
 ("light mint #17705f on 16% mix", hx("#17705f"), mix(hx("#17705f"), hx("#f4f3f8"), .16)),
 ("light amber-text #6f4c03 on 18% amber(#8f6508) mix", hx("#6f4c03"), mix(hx("#8f6508"), hx("#f4f3f8"), .18)),
 ("light inst #28598f on 12% mix", hx("#28598f"), mix(hx("#28598f"), hx("#f4f3f8"), .12)),
 ("light coral #a33d28 on 12% mix", hx("#a33d28"), mix(hx("#a33d28"), hx("#f4f3f8"), .12)),
 ("light coral #a33d28 on 12% mix over white", hx("#a33d28"), mix(hx("#a33d28"), hx("#ffffff"), .12)),
 ("light tag.good: white on #17705f", (255,255,255), hx("#17705f")),
 ("light tag: white on #a33d28", (255,255,255), hx("#a33d28")),
]
for name, fg, bg in P:
    r = cr(fg, bg); print(f"   {r:5.2f}  {'FAIL' if r < 4.5 else 'ok  '}  {name}")
print("\n== proposed 2")
for name, fg, bg in [
 ("light mint #13624f on 16% mix", hx("#13624f"), mix(hx("#13624f"), hx("#f4f3f8"), .16)),
 ("light mint #13624f as text on bg", hx("#13624f"), hx("#f4f3f8")),
 ("light tag.good white on #13624f", (255,255,255), hx("#13624f")),
 ("dark tag white on #b84a32", (255,255,255), hx("#b84a32")),
]:
    r = cr(fg, bg); print(f"   {r:5.2f}  {'FAIL' if r < 4.5 else 'ok  '}  {name}")
