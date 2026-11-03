# Prompt used for each triage subagent (round 5 onwards)

You are judging candidate YouTube playlists for PsychTube, a catalog of psychology lectures that universities,
research institutes and scientific societies put online. Read `/home/claude/psychtube/pipeline/classify/INSTRUCTIONS_triage.md`
first and follow it exactly. Then read the input file `/home/claude/psychtube/work/triage/batch_NN.jsonl` with the Read
tool and write `/home/claude/psychtube/work/triage/out_NN.jsonl` with the Write tool: one JSON object per input row, in
the same order, with the keys `pid`, `keep`, `inst`, `kind`, `english`, `confidence`, `why`. Judge every card yourself from
the fields given; do not write code to classify, do not look anything up. This round aims at developmental psychology
and cognitive science (infancy, language acquisition, theory of mind, conceptual development, core knowledge, numerical
cognition, psycholinguistics, perception, computational cognitive science, philosophy of mind) alongside the usual
subjects; a society's conference sessions, a department's colloquium series or a lab's talk series count as `talks`.
General university channels ("Harvard University", "Nobel Prize", "The Royal Society", "MIT OpenCourseWare") carry
playlists on every subject: keep only the ones whose title is within the subject rule (psychology, neuroscience,
cognitive science, linguistics of the mind, behavioural economics, philosophy of mind, child development), and for the
Nobel Prize channel keep lecture collections in economic sciences and physiology/medicine only when the title names a
mind/brain/behaviour subject or a laureate of those fields. Playlists titled "<channel> — all uploads" are a channel's
whole upload stream offered because the channel has no playlists: keep them when the channel itself is an institution
or society in the subject and `count` suggests lectures rather than clips. When done, reply with exactly one line:
`kept K of N`.
