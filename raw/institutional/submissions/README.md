# Submitted courses

One file per "Submit a course" issue (`.github/ISSUE_TEMPLATE/submit-course.yml`), written by
`python3 pipeline/intake_submission.py <issue number>`. The lectures themselves come in through the
normal path (pull the playlist, `merge_pulled.py`, label, build); the file adds what only the
submitter knows: the syllabus and other materials (links only, nothing is hosted), the lecturer's
faculty page for the publisher check, and who submitted it. Set `status` to `listed` once the playlist
is in `courses.json`; the course page then shows the materials and "submitted by the lecturer".
`control_verified` stays false until the submitter has proved control of the channel (a token in the
playlist description) — not asked for yet.
