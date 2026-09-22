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

## 2026-09-22 — step 4: safety
Permissions are now four files owned by four different parties, and a run is refused
at the front door when they disagree: Baseline (ours) ∩ Role (per vendor app) ∩ Tenant
grant (theirs) ∩ Needs (derived from the run). bank_b does not grant account_opener,
so the same artifact that works for bank_a is refused for bank_b before a browser opens
— and the refusal names the layer that refused.

The Service Account follows from the Role, so the credential used is a consequence of
the capability's intent rather than a separate setting: a balance_reader signs in as
svc_read, which the application itself will not let open an account.

Route interception was the piece I would have missed. A check before we act cannot see
a request the *page* starts: /leaky renders a 1x1 <img> pointing at attacker.example
with member data in the query string. Nobody clicks anything. The allowlist is enforced
on every request the browser makes, so it is aborted before it leaves.

Redaction: the balance reaches the caller as $4210.00 because that is the answer, and
the trail.jsonl records it as $*,***.**. A test asserts both, and another asserts no
secret value appears in any evidence file.

Two tests are controls rather than checks: no module in cua/ imports a model SDK, and
nothing but surface.py imports playwright.

## 2026-09-22 — smoke test: one real model call before building the loop
Twenty lines, fractions of a cent, and it settled the premise the whole B1 demo rests
on. Shown the accessibility list, the member-number field and the search icon are both
`(no accessible name)` — indistinguishable. Claude answered `type "12345" into [4]`,
which it can only know from the screenshot.

Cost: in=1854 out=132 tokens for one turn. A full discovery run is a few of these.

## 2026-09-22 — PII: origin first, patterns second, default-deny
The question that reshaped this: how do you redact a name or a birthday? You cannot —
no pattern finds them. So masking is decided by *which field a value came from*, and a
value is hidden unless its Target is declared a Readable Region in the App Profile.
A screen nobody has reviewed is therefore safe rather than exposed.

Three consequences:
- Watchers may only extract a declared capture group ("maximum of (\\d+)" -> 3), never
  free page text, so the last unbounded path from screen to output is closed.
- Screenshots mask declared regions at capture time (Playwright paints the boxes),
  cropped and downscaled. Still the residual risk, and documented as such.
- The strongest control turned out not to be masking at all: evidence records only
  identifiers we generated, so page text never enters it.

NER (Presidio and friends) is deliberately not in the data path: ~90-95% recall is a
disclosure rate, not a gate. It belongs as a canary over evidence, if at all.

17 tests, including a name and a birthday that no regex could catch.

## 2026-09-22 — the two masking channels want opposite defaults
Wiring the declared regions into screenshots exposed the mistake in treating pixels
like values. Default-deny on values is free: the model needs structure, not contents.
Default-deny on pixels blacked out the OK button and the navigation link — controls
the model has to use. So values are an allowlist (Readable Regions) and pixels are a
deny-list (Sensitive Regions), which is honest about the image channel being the
weaker one.

Also found while testing it: the member header put the name and "Member since" in one
table cell, so there was no anchor text beside the name and the region could not be
declared at all. Split into label/value cells, which is how a real screen is built
anyway — and a reminder that a control you cannot name is a control you cannot protect.

## 2026-09-22 — step 5: a real discovery run, and two bugs it found
13 turns, goal reached, outputs correct: savings_balance "$1250.00" and
new_account_number "SA-2001". The model signed in with secrets it never saw, found
the unlabelled search icon by anchor, dismissed the interstitial itself, read a value
out of an iframe, and stopped at the confirmation screen.

**Bug 1 — the guardrail was right, the list was wrong.** The interstitial renders at
/members, and the allowlist had only /members/*. The model was refused twice and said
"OK button blocked by policy; navigate via Member Search instead" before the stuck
detector ended the run. Two lessons: a policy that is too narrow looks exactly like a
broken agent, and the refusal text has to be good enough for the next reader to
diagnose it. Also found that watcher recovery actions bypassed the policy check — now
they go through the same gate.

**Bug 2 — it could see the value but not point at it.** Our observation listed only
interactive controls, so the savings balance (a table cell) had no [n]. The model
quoted "$1250.00" in its reason while `read` returned an empty string, and on the next
read grabbed a navigation link called "Member Search". Fixed by adding label/value
pairs to the observation. The general lesson: anything the goal asks the model to
*read* has to be addressable, not merely visible.
