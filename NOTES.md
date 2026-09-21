# Build notes

What broke, why, and what I changed. This file becomes REPORT.md and the interview answers.

## 2026-09-21 — design settled before any code
Worked the whole journey end to end before building: discovery -> recorder -> review -> replay -> escalation.
Language in CONTEXT.md, decisions in docs/adr, error handling and safety in docs/.

## 2026-09-21 — step 1: the fake bank app
Flask, ~250 lines. Hostile on purpose: table layout, no ids, session-scoped control
names (ctl00_member_3928) that change every session, an unlabelled <img> search button,
"Open Accounts" as a heading next to an <input value="Open"> button (the text-match trap
from the notes), balances inside an iframe, 3s panel for member 66666.

Two service accounts, so least-privilege is demonstrable rather than described: svc_read
gets "not permitted to perform this action" from the app itself when it reaches the
sub-account form.

Checked every scenario through the Flask test client before writing a line of engine code.
