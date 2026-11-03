# Publisher check: whose channel is this, and who teaches?

PsychTube lists lectures "published by" an institution. For most collections the channel *is* the institution
(MIT OpenCourseWare, Yale Courses, a department's channel). This pass covers the rest: collections on a person's own
channel ("Independent lecturer") and a few publishers whose channel name is all we know. The question is narrow and
factual. It is **not** about whether the lectures are good or on topic.

For each channel in the batch, answer:

1. **Whose channel is it?** A named person, a lab, a company, a student society, an unknown party.
2. **Who teaches in these collections?** Name the lecturer if it can be established.
3. **Where do they hold (or did they hold) an academic or clinical appointment?** Name the institution in its usual
   English form ("University of Toronto", not "UofT"). Give the role if known (professor, lecturer, PhD student,
   licensed therapist, no appointment found).
4. **Is that affiliation verified?** `verified: true` only when you found a page that ties **this person** to **that
   institution** (a faculty page, a department listing, a lab page, a Google Scholar profile with a verified
   institutional email, a university news item about them) **and** something that ties the channel to the person (the
   channel name is their name, the "about" text, their faculty page linking the channel, or the lectures themselves
   naming them as the instructor). A channel name that merely *contains* a university's name is not verification.
   An affiliation stated only in the video description or the channel's own blurb is `verified: false` with
   `self_described: true`.
5. **Is this a personal channel?** `personal: true` when it belongs to one person (or a person's teaching brand), not to
   an institution, department, society or lab.

Use web search. Search the lecturer's name with "psychology" or the course title, the channel name, the channel URL.
Two or three searches per channel are usually enough; stop when the answer is clear or when it is clearly not
findable. Do not guess. "Not found" is a correct answer.

Write one JSON object per **channel** (not per collection) to the output file, one per line:

```json
{"chid": "UC...", "channel": "as given", "owner_kind": "person|lab|department|institution|company|society|unknown",
 "lecturer": "Full Name or null", "role": "professor|lecturer|instructor|clinician|student|unknown",
 "institution": "University of X or null", "unit": "department or lab, or null",
 "verified": true, "self_described": false, "personal": true,
 "evidence": ["https://...", "https://..."],
 "note": "one line: what the evidence shows, and anything a cautious editor should know (retired, left academia, course taught for an online university, etc.)"}
```

Rules:
- `evidence` must be real URLs you opened or saw in search results. No invented URLs. Empty list if nothing found.
- If the channel has several lecturers (a lab channel with many speakers), name the owner in `lecturer` and say so in
  `note`; `institution` is the owner's.
- If the person is a licensed clinician with no academic appointment, `institution` is null, `role` is `clinician`, and
  the note says what you found (licence, practice).
- If the "institution" is an unaccredited or purely online outfit, say so in the note; still report it as found.
- Keep notes under 200 characters. Plain statements, no hedging phrases.
