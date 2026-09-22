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

## 2026-09-21 — step 2: schema + lint, test first
28 tests, written before the models. Two kinds of check, deliberately separate:

- the **schema** is a whitelist — an action, predicate or target rung outside the
  closed vocabulary cannot be expressed, so `download` is rejected by parsing, not
  by a rule someone has to remember to write.
- the **lint** catches artifacts that are well-formed and still wrong: a discovery
  literal surviving in a step, checkpoint or watcher; a placeholder with no input;
  an outcome declared but unreachable; a watcher naming an outcome the contract
  never promised; needs outside the declared role; a consequential step with no
  verification check when the run is unattended.

Bug caught by my own tests: the first transition uses `value_ref` (the password),
so a test that set `value` on it was rejected by the schema before the lint ever
ran. Moved those tests to the member-number step. The schema was right.

## 2026-09-22 — step 3: the Replay Engine
13 scenario tests against the live Flask app, no mocking: the member number picks
the scenario, so a test reads "replay 99999, expect MEMBER_NOT_FOUND".

Findings that changed the design:

- **Every rung-1 lookup fails on the text fields.** Dumping the accessibility tree
  showed `textbox` with an empty name everywhere, because the captions live in
  neighbouring table cells with no `<label for>`. The hand-written artifact now uses
  `label_anchor` for every field, and the replay log proves which rung matched:
  t_signin by role_name, t_member_field and t_search by label_anchor.
- **The balance is in an iframe** and simply is not in the main document. Targets
  gained a `frame`.
- **Recovery has two modes, and I only built one.** Dismissing the interstitial left
  us on the member page, but the engine rewound to "type the member number" and then
  could not find the field — reported as an unknown state on a member that works fine.
  A recovery now either rewinds to a declared `resume_at` (the app-error watcher goes
  back to Member Search) or simply re-observes where it landed (the interstitial).
  Default is re-observe: dismissing an interruption usually leaves you where you were
  heading.

Member 33333 stays failed-with-unknown-state on purpose: MAX_ACCOUNTS_REACHED is the
held-out condition, and the run's verification check confirms the commit did not take
effect rather than clicking again.
