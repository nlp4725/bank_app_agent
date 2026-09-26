"""Defence in depth, read outside in: from the model to the Member's record.

    python docs/figures/make_defence_in_depth.py

One band per layer of Figure 6.1 in REPORT.md. The left column is the threat that
arrives at that band, the band names the layer, its principle and the code that
enforces it, and the right column is what a failure there becomes. Terms in docs/CONTEXT.md.
"""

from pathlib import Path

OUT = Path(__file__).resolve().parent / "defence_in_depth.svg"

INK, MUTED = "#1a1a1a", "#6f6f6f"
BLUE, BLUE_BG = "#2f5597", "#e8edf6"
GREEN, GREEN_BG = "#1b7450", "#e4f2ec"
AMBER, AMBER_BG = "#9a6a12", "#faf0d8"
RED, RED_BG = "#a8251e", "#fae9e6"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

# (layer, principle, enforced by, threat that arrives here, what a failure becomes, tone)
LAYERS = [
    ("Environment", "no model near production",
     "cua/discovery/run.py · import-graph test",
     "a model that is wrong, or turned by what it read on the page",
     "Refused before the browser opens", RED),
    ("Execution integrity", "an Artifact is data; the engine is the only interpreter",
     "cua/domain/artifact.py · cua/governance/overlay.py · cua/replay/engine.py",
     "an Artifact or Overlay that is wrong or was tampered with",
     "rejected at load; at run, stop, never a guess", RED),
    ("Network", "allowlisted origins, on every request",
     "cua/surface/driver.py",
     "a page that sends Member data off-site by itself",
     "request aborted and logged", RED),
    ("Authorization", "Baseline ∩ Role ∩ Tenant grant ∩ Needs",
     "cua/governance/policy.py, at approval and before every action",
     "a capability run where its Tenant never granted it",
     "Refused, naming the layer", RED),
    ("Identity", "least privilege inside the app itself",
     "the Tenant's app · cua/secrets.py",
     "every layer above this one failing at once",
     "the app refuses; Failed with evidence", AMBER),
    ("Change control", "Consequential by default; two named approvals",
     "cua/authoring/lint.py · cua/authoring/review.py · cua/governance/store.py",
     "one person approving an unreviewed commit",
     "not approved; unattended commit Refused", RED),
    ("Data", "default-deny at one chokepoint",
     "cua/evidence/redact.py",
     "Member data on its way to a model, a log or an Artifact",
     "hidden; a Secret never read", GREEN),
    ("Audit", "append-only, write-ahead",
     "cua/evidence/writer.py",
     "a crash mid-commit, or a silent action",
     "Outcome Unknown: look, never retry", AMBER),
]

W = 1240
BAND_H, GAP = 46, 6
X_THREAT, W_THREAT = 30, 300
X_BAND, W_BAND = 350, 600
X_FAIL, W_FAIL = 970, 250
Y0 = 72
H = Y0 + len(LAYERS) * (BAND_H + GAP) + 74

out = []
add = out.append


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, *, size=11, fill=INK, font=SANS, weight="normal", anchor="middle",
         style="normal"):
    add(f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" fill="{fill}" '
        f'font-weight="{weight}" font-style="{style}" text-anchor="{anchor}">{esc(s)}</text>')


add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" '
    f'height="{H}" font-family="{SANS}">')
add("<defs>")
for c in (INK, RED, MUTED):
    add(f'<marker id="h{c[1:]}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        f'markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" '
        f'fill="{c}"/></marker>')
add("</defs>")
add(f'<rect width="{W}" height="{H}" fill="white"/>')

# column headings
text(X_THREAT, 30, "WHAT ARRIVES", size=10, fill=MUTED, weight="600", anchor="start")
text(X_BAND + W_BAND / 2, 30, "THE LAYER, AND THE CODE THAT IS THE WALL", size=10,
     fill=MUTED, weight="600")
text(X_FAIL + W_FAIL, 30, "WHAT A FAILURE BECOMES", size=10, fill=MUTED, weight="600",
     anchor="end")
text(X_BAND + W_BAND / 2, 44, "read outside in: the model is above the first band, the Member's record below the last",
     size=9.5, fill=MUTED, style="italic")

# the model, above the stack
text(X_BAND + W_BAND / 2, Y0 - 4, "the Discovery LLM — proposes, never performs",
     size=10, fill=MUTED, style="italic")

for i, (name, principle, code, threat, becomes, tone) in enumerate(LAYERS):
    y = Y0 + 6 + i * (BAND_H + GAP)
    # the band, nested a little more each step in
    inset = i * 4
    add(f'<rect x="{X_BAND + inset}" y="{y}" width="{W_BAND - 2 * inset}" height="{BAND_H}" '
        f'rx="5" fill="{BLUE_BG}" stroke="{BLUE}" stroke-width="1.4"/>')
    cx = X_BAND + W_BAND / 2
    text(X_BAND + inset + 14, y + 19, f"{i + 1}", size=12, weight="700", fill=BLUE,
         anchor="start")
    text(X_BAND + inset + 32, y + 19, name, size=12, weight="700", anchor="start")
    text(X_BAND + inset + 32 + 7.2 * len(name) + 8, y + 19, f"— {principle}", size=11,
         fill=BLUE, anchor="start")
    text(X_BAND + inset + 32, y + 36, code, size=9.5, fill=MUTED, font=MONO, anchor="start")
    # the threat arriving from the left
    text(X_THREAT, y + BAND_H / 2 + 4, threat, size=10.5, fill=INK, style="italic",
         anchor="start")
    add(f'<path d="M{X_THREAT + W_THREAT + 2},{y + BAND_H / 2} L{X_BAND + inset - 4},{y + BAND_H / 2}" '
        f'stroke="{MUTED}" stroke-width="1.2" fill="none" marker-end="url(#h{MUTED[1:]})"/>')
    # what a failure becomes, to the right
    bg = {RED: RED_BG, AMBER: AMBER_BG, GREEN: GREEN_BG}[tone]
    add(f'<rect x="{X_FAIL}" y="{y + 9}" width="{W_FAIL}" height="{BAND_H - 18}" rx="4" '
        f'fill="{bg}" stroke="{tone}" stroke-width="1.2"/>')
    text(X_FAIL + W_FAIL / 2, y + BAND_H / 2 + 4, becomes, size=10, fill=tone, weight="600")
    add(f'<path d="M{X_BAND + W_BAND - inset + 4},{y + BAND_H / 2} L{X_FAIL - 4},{y + BAND_H / 2}" '
        f'stroke="{tone}" stroke-width="1.2" fill="none"/>')

# the asset, below the stack
y_asset = Y0 + 6 + len(LAYERS) * (BAND_H + GAP) + 8
inset = len(LAYERS) * 4
add(f'<rect x="{X_BAND + inset}" y="{y_asset}" width="{W_BAND - 2 * inset}" height="36" '
    f'rx="5" fill="{INK}" stroke="{INK}"/>')
text(X_BAND + W_BAND / 2, y_asset + 16, "the Member's record · money movement on a real account",
     size=11, fill="white", weight="600")
text(X_BAND + W_BAND / 2, y_asset + 29, "reached only by a replay that passed every band above",
     size=9.5, fill="#cfcfcf", style="italic")

add("</svg>")
OUT.write_text("\n".join(out) + "\n")
print(f"wrote {OUT}")
