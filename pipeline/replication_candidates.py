#!/usr/bin/env python3
"""Keyword pass for replication badges: which catalog videos might present or critique one of the contested findings.

Reads  site/data/psychtube.json          (the built catalog: titles, summaries, keywords)
       pipeline/taxonomy.json            (contested_findings)
       work/replication/tags*.jsonl      (candidates already judged; skipped)
Writes work/replication/candidates_<date>.jsonl  one row per video with the finding ids its text matches,
       for Claude to judge one by one into work/replication/tags_<date>.jsonl ({vid, contested, role, confidence});
       the build merges every tags*.jsonl onto videos that have no badge from a labeler or a shelf.

The patterns are deliberately broad (recall over precision): a human judgement follows. Run after a build.
Usage: python3 pipeline/replication_candidates.py [--all]   (--all: include videos that already carry a badge)
"""
import datetime as dt
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)

PATTERNS = {
    "power-posing": r"power.?pos(e|ing)|amy cuddy|body language shapes who",
    "stanford-prison": r"stanford prison|zimbardo",
    "marshmallow-test": r"marshmallow",
    "ego-depletion": r"ego.?depletion|willpower (is|as) a muscle|baumeister",
    "social-priming": r"social priming|behavio(u)?ral priming|elderly.?words|florida effect|money priming|bargh",
    "facial-feedback": r"facial feedback|pen.in.(the.)?(mouth|teeth)|strack",
    "growth-mindset": r"growth mindset|fixed mindset|carol dweck|dweck",
    "learning-styles": r"learning styles?|visual learner|auditory learner|kinesthetic learner|VAK\b",
    "10000-hours": r"10,?000.?hours?|ten thousand hours|deliberate practice|ericsson|gladwell",
    "grit": r"\bgrit\b|duckworth",
    "left-right-brain": r"left.?brain(ed)?|right.?brain(ed)?|hemispher(e|ic) dominan",
    "milgram-nuance": r"milgram|obedience (to authority|experiment|study)",
    "bystander-genovese": r"genovese|38 witnesses|thirty.eight witnesses",
    "bystander-effect": r"bystander (effect|apathy|intervention)|diffusion of responsibility|darley|latan[ée]",
    "dunning-kruger-artifact": r"dunning.?kruger",
    "implicit-bias-iat": r"implicit association test|\bIAT\b|implicit bias|banaji|greenwald",
    "mozart-effect": r"mozart effect|listening to mozart",
    "little-albert": r"little albert|watson and rayner|watson & rayner",
    "serotonin-depression": r"chemical imbalance|serotonin (theory|hypothesis|deficien)|low serotonin|moncrieff",
    "stereotype-threat": r"stereotype threat|claude steele|steele and aronson",
    "mirror-neurons": r"mirror neurons?|broken mirror|rizzolatti|ramachandran.*(neurons|civili[sz]ation)",
    "huberman-protocols": r"huberman",
    "nofap-porn": r"nofap|porn (addiction|induced|rewires)|your brain on porn|wilson.*porn",
    "amy-cuddy-ted": r"single study|ted talks? (are|is) (wrong|misleading)|tedx? psychology",
    "mbti": r"myers.?briggs|\bMBTI\b|16 personalities|INTJ|ENFP|personality types? test",
    "rat-park": r"rat park|bruce alexander|everything you think you know about addiction",
    "multiple-intelligences": r"multiple intelligences|howard gardner|gardner's intelligences",
    "polyvagal": r"polyvagal|stephen porges|porges|vagal tone",
    "body-keeps-score": r"body keeps the score|van der kolk|repressed memor|recovered memor|body memor",
    "attachment-styles-pop": r"attachment styles?|anxious.?avoidant|avoidant attachment|anxious attachment|secure attachment|\battached\b.*(levine|heller)",
    "dopamine-detox": r"dopamine (detox|fast(ing)?|reset)|dopamine nation",
    "choice-overload": r"choice overload|paradox of choice|jam (study|experiment)|iyengar|barry schwartz|too many choices",
    "goal-announcing": r"(announc|tell(ing)?|shar(e|ing)) (your )?goals?|keep your goals to yourself|derek sivers|gollwitzer",
    "stress-mindset": r"stress (mindset|is good for you|as your friend)|kelly mcgonigal|mcgonigal",
    "asch-conformity": r"\basch\b|line.?judg(e)?ment|conformity experiment",
    "robbers-cave": r"robbers cave|sherif|eagles and rattlers|realistic conflict",
    "ape-language": r"ape language|koko|kanzi|washoe|nim chimpsky|chimp(anzee)?s? (learn|use|sign) language|signing (ape|gorilla|chimp)|savage.rumbaugh|terrace",
    "universal-emotions": r"universal (facial )?(expressions|emotions)|basic emotions|ekman|facial expressions? (of emotion|are universal)|lisa feldman barrett|feldman barrett",
    "cognitive-dissonance": r"cognitive dissonance|festinger|when prophecy fails|forced compliance",
    "anchoring": r"anchoring (effect|bias|heuristic)|\banchor(s|ed|ing)\b.*(estimate|number|price|judg)",
    "framing-effect": r"framing effect|asian disease|loss frame|gain frame|prospect theory|loss aversion",
    "macbeth-effect": r"macbeth effect|moral (cleansing|purity).*(wash|soap)|lady macbeth",
    "terror-management": r"terror management|mortality salience|denial of death|becker.*death",
    "precognition-bem": r"precognition|\bpsi\b|daryl bem|feeling the future|parapsycholog|\bESP\b|extrasensory|telepath|remote viewing|ganzfeld|psychic",
    "hungry-judges": r"hungry judges|judges.*(parole|lunch)|parole.*(lunch|break)|danziger",
    "oxytocin-trust": r"oxytocin|love hormone|cuddle hormone|trust hormone|paul zak|moral molecule",
    "brain-training": r"brain.?training|lumosity|cogmed|dual.?n.?back|working memory training|train(ing)? your brain",
    "bilingual-advantage": r"bilingual (advantage|brain|benefit)|bilingualism|bialystok",
    "rosenhan": r"rosenhan|being sane in insane places|pseudopatients?|on being sane",
    "subliminal-advertising": r"subliminal",
    "ten-percent-brain": r"(10|ten) ?(%|percent) of (your|our|the) brain",
    "hot-hand": r"hot hand|gilovich|streak shooting",
    "birth-order": r"birth order|first.?born|middle child|only child|youngest child",
    "pygmalion": r"pygmalion|rosenthal|teacher expectation|expectancy effect|self.fulfilling prophec",
    "mindfulness-hype": r"mindfulness (revolution|cure|will|changes? (the|your) brain|for everything|movement)|benefits of (mindfulness|meditation)|meditation (changes|rewires|alters) (the|your) brain|mbsr|kabat.zinn|mindful(ness)? (nation|schools)|science of (mindfulness|meditation)",
    "microexpressions-lies": r"micro.?expressions?|lie to me|lie detect|detect(ing)? (lies|deception)|spot(ting)? a liar|body language of (liars|lying)",
    "nlp-eye-movements": r"neuro.?linguistic programming|\bNLP\b|eye (movement|access)(ing)? cues|eye accessing",
    "media-violence": r"(video ?game|media|tv|television) violence|violent (video )?games|violent media|bobo|bandura",
    "inattentional-blindness": r"inattentional blindness|invisible gorilla|gorilla (experiment|test|video)|selective attention test|daniel simons|chabris|change blindness",
    "mcgurk-effect": r"mcgurk",
    "rubber-hand": r"rubber hand|body ownership illusion|botvinick",
    "stroop-effect": r"stroop",
    "split-brain-consciousness": r"split.?brain|corpus callosum|callosotomy|gazzaniga|sperry|two minds|alien hand",
    "learned-helplessness": r"learned helplessness|seligman.*(dogs|shock|helpless)|helpless(ness)? (dogs|experiment)",
    "pavlov-bell": r"pavlov",
    "phineas-gage": r"phineas gage|\bgage\b.*(iron|rod|frontal)",
    "ariely-dishonesty": r"ariely|dishonesty|honest(y)? (pledge|research)|truth about dishonesty|predictably irrational|why we lie|cheat(ing)?.*(ariely|experiment|study|honest)|francesca gino",
}

tax = json.load(open(P("pipeline", "taxonomy.json"), encoding="utf-8"))
ids = {c["id"] for c in tax["contested_findings"]}
missing = ids - set(PATTERNS)
if missing:
    print("no pattern for:", sorted(missing))
rx = {k: re.compile(v, re.I) for k, v in PATTERNS.items() if k in ids}
judged = set()
for f in glob.glob(P("work", "replication", "tags*.jsonl")):
    judged |= {json.loads(l)["vid"] for l in open(f, encoding="utf-8") if l.strip()}
data = json.load(open(P("site", "data", "psychtube.json"), encoding="utf-8"))
include_badged = "--all" in sys.argv
rows = []
for v in data["videos"]:
    if v["id"] in judged or (v.get("badge") and not include_badged):
        continue
    text = " ".join([v.get("title") or "", v.get("summary") or "", v.get("why") or "", " ".join(v.get("kw") or []), v.get("ch") or ""])
    hits = [k for k, r in rx.items() if r.search(text)]
    if hits:
        rows.append({"vid": v["id"], "title": v.get("title"), "ch": v.get("ch"), "summary": (v.get("summary") or v.get("why") or "")[:200],
                     "already": v.get("badge", {}).get("id") if v.get("badge") else None, "candidates": hits})
stamp = dt.date.today().isoformat()
out = P("work", "replication", f"candidates_{stamp}.jsonl")
with open(out, "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
from collections import Counter
print(f"{len(rows)} candidates -> {out}")
print(Counter(k for r in rows for k in r["candidates"]).most_common())
