# Review tools

The scripts behind the numbers in `review/REVIEW.md`. All of them run offline against the repo.

## Data checks

```bash
python3 review/tools/audit_data.py
```

Prints one line per check on `site/data/psychtube.json`, `raw/` and `work/`: collections by kind, cross-channel items,
watch-list playlists, podcasts with an institutional badge, triage confidence, the channel-name parse slip, non-Latin
titles, vouch semantics, replication coverage, metadata quality, canon overlap and the Courses hub order. Re-run it
after a rebuild to see what a change did.

## Browser checks

These need Node with Playwright and Chromium. Serve the site first:

```bash
python3 -m http.server 8765 --directory site
```

| script | measures |
|---|---|
| `perf_cpu.js [cpuRate] [base]` | Moto G4 profile with CPU throttling (default 4×). Prints parse and init times, heap, and render time, DOM nodes and cards per route, plus search keystroke cost. |
| `perf_net.js <fast4g\|slow4g\|3g> [cpuRate]` | Time until the catalog is visible on a throttled network. Needs `node gzserve.js site 8766`, a gzipping static server like GitHub Pages. |
| `ui_checks.js` | The UI bugs in the review: Clips markup, shelf status link, skip link, canon row, vouch wording, Debunk tag, malformed hash, channel names, provenance copy, hash-route injection, focus, filter links, clear history, theme flash, arrow keys on `<video>`. |
| `player_tab_switch.js` | Whether hiding the page destroys the YouTube player. Uses a stub of the IFrame API, so it needs no network. |
| `search_checks.js` | Search results for `placebo`, `neurons`, `history`, `ai`, `is iq real?`. |

The browser scripts block every request that isn't to localhost, so thumbnails and fonts don't load. That's
deliberate: the timings are for the app alone.

## Contrast

```bash
python3 review/tools/contrast.py
```

Computes WCAG contrast ratios for the token pairs in `site/styles.css`, both themes, and for the proposed replacements.
