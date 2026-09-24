"""One turn of a Discovery Run, three ways — after AgentRR's Figure 3 (record phase).

    python docs/figures/make_representations.py

AgentRR's record panel shows the same moment as a screenshot, as parsed elements
(OCR/OmniParser) and as API calls. This system has counterparts for the first two and
none for the third, by the brief's premise: the app has no API, so the recorded Target
— a ladder of ways to find the control — is what stands in its place. Everything shown
is taken from evidence/08 turn 5, the unlabelled search icon, as recorded — a run made
under the current masking and crop rules.
"""

import base64
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

RUN = ROOT / "evidence/08-discovery-read-balance"
ARTIFACT = ROOT / "artifacts/read_savings_balance.1.0.0.yaml"
OUT = Path(__file__).resolve().parent / "three_representations.svg"
TURN, TARGET = 5, "t_member_number_button"

INK, MUTED, RULE = "#1a1a1a", "#6f6f6f", "#d4d2cc"
BLUE, BLUE_BG = "#2b5fd9", "#eaf0fd"
AMBER, AMBER_BG = "#a1670a", "#fbf0d9"
GREEN, GREEN_BG = "#1b7450", "#e4f2ec"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

W, H = 1240, 540
PANEL_W, PANEL_H, GAP, TOP = 372, 370, 34, 96
out = []
add = out.append


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, *, size=11, fill=INK, font=SANS, weight="normal", anchor="start"):
    add(f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" fill="{fill}" '
        f'font-weight="{weight}" text-anchor="{anchor}">{esc(s)}</text>')


def b64(path):
    return "data:image/png;base64," + base64.standard_b64encode(Path(path).read_bytes()).decode()


# ── the recorded moment ─────────────────────────────────────────────────────
observed = proposed = None
for line in (RUN / "trail.jsonl").read_text().splitlines():
    e = json.loads(line)
    if e.get("turn") == TURN and e["event"] == "observed":
        observed = e
    if e.get("turn") == TURN and e["event"] == "proposed":
        proposed = e
action = next(a for a in json.loads((RUN / "actions.json").read_text()) if a["turn"] == TURN)
target = yaml.safe_load(ARTIFACT.read_text())["targets"][TARGET]
shot = RUN / "screens" / f"{TURN:02d}.png"
crop = RUN / "screens" / f"{TURN:02d}_target.png"
matched = None
import urllib.request
from cua.replay import RunContext, replay
from cua.governance.store import load_capability, origin_for
_art = load_capability("member.read_savings_balance")
_origin = origin_for("bank_a", _art.capability.vendor_app)
urllib.request.urlopen(f"{_origin}/reset", timeout=5).read()
for e in replay(_art, {"member_number": "12345"}, RunContext(origin=_origin)).trail:
    if e["event"] == "about_to" and e.get("target") == TARGET:
        matched = e["matched_by"]

add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" '
    f'height="{H}" font-family="{SANS}">')
add('<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
    f'markerHeight="7" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="{MUTED}"/></marker></defs>')
add(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
text(58, 44, "One turn, three representations — the unlabelled search icon, discovery turn 5",
     size=17, weight="700")
text(58, 66, "what the model saw · what the model read · what code recorded — all from "
             "evidence/08-discovery-read-balance, as recorded", size=11.5, fill=MUTED)

xs = [58 + i * (PANEL_W + GAP) for i in range(3)]
titles = [("SCREENSHOT", "what the model saw — Sensitive Regions painted at capture", AMBER, AMBER_BG),
          ("ACCESSIBILITY LIST", "what the model read — values (hidden), one number per control", BLUE, BLUE_BG),
          ("RECORDED TARGET", "what code kept — a ladder, strongest rung first; no API exists", GREEN, GREEN_BG)]
for x, (t, sub, colour, bg) in zip(xs, titles):
    add(f'<rect x="{x}" y="{TOP}" width="{PANEL_W}" height="{PANEL_H}" rx="9" fill="{bg}" '
        f'stroke="{colour}" stroke-width="1.4"/>')
    text(x + 16, TOP + 24, t, size=11.5, weight="700", fill=colour)
    text(x + 16, TOP + 41, sub, size=9.5, fill=MUTED)

# panel 1: the screenshot, and the crop that became the picture rung
#
# The page is 1100x800 and almost all of it is empty: the header, the nav and the
# search form sit in the top 170px. Shown whole at panel width, the form is a
# thumbnail nobody can read, so the panel shows the region that matters at a scale
# where its text is legible, and boxes the icon the turn is about.
x = xs[0]
img_w = PANEL_W - 32
REGION = (0, 0, 470, 170)                    # page px: header, nav, the form
ICON = (263, 111, 32, 32)                    # page px: the unlabelled search button
rw, rh = REGION[2], REGION[3]
img_h = int(img_w * rh / rw)
add(f'<svg x="{x + 16}" y="{TOP + 56}" width="{img_w}" height="{img_h}" '
    f'viewBox="{REGION[0]} {REGION[1]} {rw} {rh}" preserveAspectRatio="xMinYMin meet">')
add(f'<image href="{b64(shot)}" x="0" y="0" width="1100" height="800"/>')
add(f'<rect x="{ICON[0]}" y="{ICON[1]}" width="{ICON[2]}" height="{ICON[3]}" fill="none" '
    f'stroke="{AMBER}" stroke-width="2.5" stroke-dasharray="4 3"/>')
add('</svg>')
add(f'<rect x="{x + 16}" y="{TOP + 56}" width="{img_w}" height="{img_h}" fill="none" '
    f'stroke="{RULE}" stroke-width="1"/>')
text(x + 16, TOP + 56 + img_h + 14, f"the top-left {rw}×{rh}px of a 1100×800 page; the rest is empty",
     size=9, fill=MUTED)
cy = TOP + 56 + img_h + 40
text(x + 16, cy, "the control, cropped before the click — the picture rung:", size=10, fill=MUTED)
add(f'<image href="{b64(crop)}" x="{x + 16}" y="{cy + 8}" width="96" height="60" '
    f'preserveAspectRatio="xMidYMid meet"/>')
add(f'<rect x="{x + 16}" y="{cy + 8}" width="96" height="60" fill="none" stroke="{AMBER}" '
    f'stroke-width="1.2" stroke-dasharray="3 2"/>')
text(x + 124, cy + 30, "05_target.png", size=10, font=MONO, fill=INK)
text(x + 124, cy + 46, "a picture of a control, never of a value", size=9.5, fill=MUTED)

# panel 2: the observation, with the chosen line marked, and the proposal
x = xs[1]
y = TOP + 62
import textwrap
# Every line in full: a line that names the caption the model used must not be cut
# off at the caption. Long ones wrap, with the continuation indented under the text.
for line in observed["controls"].splitlines()[:12]:
    chosen = line.startswith("[1]")
    parts = textwrap.wrap(line, 54, subsequent_indent="      ") or [""]
    if chosen:
        add(f'<rect x="{x + 10}" y="{y - 11}" width="{PANEL_W - 20}" height="{16 * len(parts)}" '
            f'rx="3" fill="#ffffff" stroke="{BLUE}" stroke-width="1"/>')
    for part in parts:
        text(x + 16, y, part, size=9.5, font=MONO, fill=INK if part.strip() else MUTED,
             weight="600" if chosen else "normal")
        y += 16
y += 10
add(f'<line x1="{x + 16}" y1="{y}" x2="{x + PANEL_W - 16}" y2="{y}" stroke="{RULE}"/>')
y += 22
text(x + 16, y, "model →", size=10, fill=MUTED)
text(x + 74, y, f'{proposed["tool"]}(element=1)', size=10.5, font=MONO, weight="600")
y += 16
text(x + 74, y, f'"{proposed["reason"]}"', size=10, fill=MUTED)
y += 26
text(x + 16, y, "the button has no accessible name; the model found it by the caption", size=9.5, fill=MUTED)
y += 14
text(x + 16, y, "beside it — which is exactly what the recorded rung says.", size=9.5, fill=MUTED)

# panel 3: the target as recorded, then approved
x = xs[2]
y = TOP + 62
text(x + 16, y, f"{TARGET}:", size=10.5, font=MONO, weight="600"); y += 18
for i, r in enumerate(target["rungs"], 1):
    text(x + 30, y, f"rung {i}: {r['kind']}", size=9.5, font=MONO, weight="600"); y += 15
    for k in ("role", "name", "anchor", "relation", "asset", "threshold"):
        if k in r:
            v = str(r[k]).split("/")[-1] if k == "asset" else r[k]
            text(x + 52, y, f"{k}: {v}", size=9.5, font=MONO, fill=MUTED); y += 15
    y += 4
y += 6
add(f'<line x1="{x + 16}" y1="{y}" x2="{x + PANEL_W - 16}" y2="{y}" stroke="{RULE}"/>')
y += 22
text(x + 16, y, "a replay, no model, resolved it by:", size=10, fill=MUTED); y += 16
text(x + 16, y, matched or "?", size=10.5, font=MONO, weight="600", fill=GREEN); y += 24
text(x + 16, y, "AgentRR's third column is API calls. This app has", size=9.5, fill=MUTED); y += 14
text(x + 16, y, "none — the brief's premise — so the ladder is what", size=9.5, fill=MUTED); y += 14
text(x + 16, y, "stands in its place: the same control, three ways to", size=9.5, fill=MUTED); y += 14
text(x + 16, y, "find it, tried strongest first.", size=9.5, fill=MUTED)

# arrows between panels
for i, label in enumerate(("the model reads both", "code records, never the model")):
    x1 = xs[i] + PANEL_W + 4; x2 = xs[i + 1] - 4
    add(f'<path d="M {x1} {TOP + PANEL_H / 2} L {x2} {TOP + PANEL_H / 2}" stroke="{MUTED}" '
        f'stroke-width="1.4" fill="none" marker-end="url(#a)"/>')
    text((x1 + x2) / 2, TOP - 10, label, size=8.5, fill=INK, anchor="middle")

text(58, H - 14, "Generated by docs/figures/make_representations.py from evidence/08 (turn 5), "
     "artifacts/read_savings_balance.1.0.0.yaml and one live replay", size=9.5, fill=MUTED)
add("</svg>")
OUT.write_text("\n".join(out))
print(f"wrote {OUT.relative_to(ROOT)}")
