# bank_app_agent

An LLM discovers how a task is done in a legacy bank application **once**, against a
non-production copy. That run is compiled into a reviewable **Artifact**. Thereafter the
**Replay Engine** executes it with given inputs and **no model in the decision loop** — the
only way a capability runs in production.

Write-up: **[REPORT.md](./REPORT.md)** · worked runs: **[evidence/](./evidence/)** ·
language: [CONTEXT.md](./CONTEXT.md) · decisions: [docs/adr](./docs/adr)

---

## Setup

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

Start the demo bank — two instances, the same product configured as two institutions:

```bash
python -m fake_bank.app &                        # First Credit Union  :5001
SKIN=bank2 PORT=5002 python -m fake_bank.app &   # Lakeside Savings    :5002
```

Open <http://localhost:5001> and sign in as `svc_officer` / `officer-pw` to see what the
automation is working against. `GET /reset` restores the seed data, and every tool below
calls it first, so the walkthrough is repeatable in any order.

No API key is needed for steps 1–7. Step 8 needs one: export `ANTHROPIC_API_KEY`, or put
`ANTHROPIC_API_KEY=...` in a `.env` file in this folder (gitignored; `tools.discovery` reads it).

---

## The target application

`fake_bank/` is a deliberately hostile stand-in for a legacy member-servicing console:
server-rendered with full page reloads, nested table layout, no ids or test ids,
session-scoped generated control names, an unlabelled icon button, duplicate "Open" text,
and the balances inside an iframe.

Two service accounts: `svc_read` / `read-only-pw` (cannot open accounts — the application
itself refuses) and `svc_officer` / `officer-pw`.

The member number selects the scenario:

| Member | Behaviour | Condition it exercises |
|---|---|---|
| 12345 | normal | success |
| 99999 | "No records found" | Business Outcome |
| 22222 | "not authorized to view" | Business Outcome |
| 54321 | system notice once, then normal | Recoverable (interstitial) |
| 77777 | application error once, then normal | Recoverable (transient) |
| 88888 | session expires | Recoverable — the system signs in again |
| 66666 | balances panel takes 3s | Recoverable (slow load) |
| 44444 | flagged: needs a supervisor ID + PIN | Escalate — automation holds no such credential |
| 33333 | already holds 3 sub-accounts | held out: Unknown State on commit |

---

## Walkthrough

### 1. Watch one capability run

```bash
python -m tools.replay --list                 # the catalog: every capability, and whether it is approved
python -m tools.replay 12345 --headed --attended     # asks which capability when more than one is approved
python -m tools.replay 12345 --headed --attended --slowmo 2000    # slower, to follow along
python -m tools.replay 12345 --headed --attended --capability member.open_sub_account
python -m tools.replay 12345 --headed --capability member.read_savings_balance   # reads only: needs nobody
```

`--attended` means an Operator is on shift: you. A capability that commits something pauses
before the click that commits and asks you at this terminal (`--console` sends the question
to the Operator console instead). Without `--attended` such a capability is **Refused** before a
browser opens: no person, no commit. A read-only capability needs nobody.

Which artifact runs is the Capability Store's answer: the highest **approved** version of the
capability id — a draft never replays. A browser opens and drives itself. Drop `HEADED=1` to run it headless in about 3 seconds.
The capability is `member.open_sub_account`: sign in → search → read the savings balance out
of the iframe → open a sub-account → confirm → read back the new account number.

Each line is one Transition, and **`rung=` is which way of finding the control worked**:

```
  s1_login         -> s2_user_id_entered type   t_user_id                secret:login_username    rung=label_anchor risk=safe
  s2_user_id_entered -> s3_password_entered type   t_password               secret:login_password    rung=label_anchor risk=safe
  s3_password_entered -> s4_search        click  t_sign_in                                         rung=role_name risk=safe
  s4_search        -> s5_member_number_entered type   t_member_number          {{member_number}}        rung=label_anchor risk=safe
  s5_member_number_entered -> s7_members_id    click  t_member_number_button                            rung=label_anchor risk=safe
  s7_members_id    -> s8_savings_balance_read read   t_savings_balance                                 rung=label_anchor risk=safe
  ...
  s12_members_id   -> s13_members_id   click  t_continue                                        rung=role_name risk=consequential
  s13_members_id   -> s14_new_account_number_read read   t_new_account_number                              rung=label_anchor risk=safe

RESULT  succeeded
OUTPUTS {'savings_balance': '$4210.00', 'new_account_number': 'SA-2001'}
TIME    3.4s     evidence: runs/run_a7fe58ff
```

Three things to notice. The password was never a literal — `secret:login_username` is a
reference resolved at the keystroke. `t_member_number_button` is the **unlabelled icon
button**: rung 1 (accessibility name) finds nothing, so rung 2 finds it by the caption
beside it, and the log records which rung won. And exactly one Transition is
`consequential` — the click that actually opens the account.

![one turn, three representations](./docs/figures/three_representations.svg)

*The unlabelled search icon three ways: the masked screenshot, the accessibility list
(no name, so a text-only agent cannot see it), and the recorded Target, found by the
caption beside it.*

### 2. The conditions, one command each

Every one of these is the *same approved Artifact* meeting a different screen.

```bash
python -m tools.replay 99999 --attended   # Business Outcome — the app's legitimate answer
python -m tools.replay 54321 --attended   # Recoverable — dismisses an interstitial, carries on
python -m tools.replay 88888 --attended   # Recoverable — session expires, the system signs in again
python -m tools.replay 44444 --attended --wait 5   # Escalate — nobody answers in 5 s, so it stops
python -m tools.replay 33333 --attended   # the held-out condition, on purpose
python -m tools.replay 12345              # unattended: Refused, a person is required to commit
```

What you should see:

| Command | Result | Why |
|---|---|---|
| `99999` | `business_outcome · MEMBER_NOT_FOUND` | not an error: the answer, with `retry_same_inputs: never` and a hint for the caller |
| `54321` | `succeeded` | a Watcher recognised the notice, dismissed it, re-checked, continued |
| `88888` | `succeeded` | the automation holds the service account, so it re-authenticates itself |
| `44444` | `failed · escalation_required` | a supervisor's own ID and PIN — no Role holds those |
| `33333` | `failed · unknown_state` | no Watcher covers "maximum accounts reached"; it refuses to guess |

`33333` is the point of the design: the Artifact has **never seen** this screen. It does not
guess. It runs the Verification Check, confirms the account was *not* created, and fails with
evidence.

### 3. A person takes the live session

`44444` is flagged, and only a supervisor can clear it. Run it attended:

```bash
HEADED=1 ATTENDED=1 python -m tools.replay 44444
```

The run pauses and hands over the browser it was already using. In a second terminal:

```bash
python -m tools.operator
```

```
  INTERVENTION  run_bd7f80f8
  capability    member.open_sub_account
  stopped at    s5_member_number_entered  (w_approval_required)
  because       This member is flagged; only a supervisor may clear it.
  the session   http://127.0.0.1:5001/members
```

Now act **in the browser window that is already open** — supervisor `sup_ramirez`, PIN
`4821`, then Acknowledge. You do not need to press Resume: the run watches the screen, sees
the blocking condition gone, re-checks which Checkpoint holds, and carries on to
`succeeded`. `python -m tools.operator abort` stops it instead, which returns `aborted` —
a decision, not a failure.

There is also a browser console for the same thing:

```bash
python -m tools.operator.web     # http://127.0.0.1:5010
```

The automation never types the supervisor PIN, and it is never written to the trail — only
*that* a person acted, who they were, and whether the page changed.

### 4. Safety refuses before the browser opens

```bash
python -m tools.replay 12345 bank_b
```

```
RESULT  refused · tenant 'bank_b' does not grant role 'account_opener'
```

Nothing was touched. Permissions are **Baseline ∩ Role ∩ Tenant grant ∩ Needs**, a true
intersection — each layer may narrow what the one above allows, none may widen it. The same
front door refuses an undeclared origin, an unapproved Artifact, a capability that commits
when nobody is on shift, and an input that fails its Contract:

```bash
python - <<'PY'
from cua.replay.engine import RunContext, replay
from cua.governance.store import load_capability, origin_for

art = load_capability("member.open_sub_account")
here = origin_for("bank_a", "demo-core-servicing")

print(replay(art, {"member_number": "12", "account_type": "savings", "nickname": "x"},
             RunContext(origin=here)))
print(replay(art, {"member_number": "12345", "account_type": "savings", "nickname": "x"},
             RunContext(origin="http://127.0.0.1:9999", tenant="bank_a")))
PY
```

```
refused · input 'member_number' does not match ^[0-9]{5}$
refused · origin 'http://127.0.0.1:9999' is not an instance tenant 'bank_a' declares
```

What each of the four layers contributes, by example:

- **Baseline** ([config/baseline.yaml](./config/baseline.yaml)), the agent vendor's floor.
  The engine can only "click", "type", "select" and "read", so no run on any Tenant can
  download a file or run a script; no secret is ever sent to a model; discovery never runs
  against production; no Consequential/risky Action (one whose effect cannot be undone or
  safely repeated, such as the click that opens a sub-account) runs without an Operator's
  approval, so a capability that commits is Refused unattended; a run stops after 60
  actions; and a route with `wire`, `transfer` or `payment` in it is refused, because this
  version of the product does not move money.
- **Role** ([config/roles/](./config/roles/)), one job's access. `balance_reader` may
  "type", "click" and "read" on `/login`, `/search` and `/members/*`, signed in as
  `svc_read`; a click that lands on `/admin` is refused at that action, whatever any
  Tenant says.
- **Tenant Policy** ([config/policies/](./config/policies/)), the institution's grant.
  `bank_b` grants `balance_reader` but not `account_opener`, so opening a sub-account
  there is Refused before a browser opens; and a Tenant may cut `/members/notes` from a
  Role's pages for its own instance, but cannot add `/admin` to it, because a Tenant file
  can only narrow.
- **Needs**, declared in the Artifact from what discovery used, and required to fit inside
  its Role. `read_savings_balance` was seen to use the login, search and member pages,
  three actions and the two login secrets, all inside `balance_reader`.

### 5. One Artifact, two institutions

Lakeside Savings runs the same vendor product with renamed controls and the search icon
moved. The same approved Artifact, unchanged:

```bash
python -m tools.demos.b2
```

```
1. First Credit Union — the institution it was recorded on
   succeeded

2. Lakeside Savings — same product, renamed controls, no Overlay
   failed · unknown_state · at s1_login

3. Lakeside Savings — the same artifact, with a 20-line Overlay
   succeeded   savings_balance=$4210.00 account=SA-2001
   patched: t_continue, t_member_number, t_member_number_button, t_open

4. An Overlay that tries to change behaviour
   refused · overlay rejected: [overlay_changes_behaviour] transitions: an overlay may not change 'transitions'
```

Step 4 is the one that matters: a Tenant Overlay may change how things **look** — origin,
control labels, timeouts — and is refused outright if it tries to change what the capability
**does**. A cosmetic per-tenant file cannot alter a reviewed flow.

### 6. Why the targeting survives a hostile app

```bash
python -m tools.demos.b1
```

Prints the accessibility view of the search control (it has no name at all), then the ladder
recorded for it, then a replay showing which rung actually resolved each Target. A rising
rate of fallback matches for a tenant is the signal that their app has drifted —
see [docs/targeting.md](./docs/targeting.md).

### 7. Read any run afterwards

```bash
python -m tools.inspect.show_run                  # the most recent
python -m tools.inspect.show_run runs/run_8de312d4
```

Every run leaves an append-only redacted trail: each policy decision, each action, which rung
matched, every Watcher that fired, and a screenshot on failure with the declared Sensitive
Regions already painted black — look at
[`evidence/06-replay-unknown-state/screen_1.png`](./evidence/06-replay-unknown-state/) and
you will see the member's name and date of birth blacked out while the balances, which are
the answer, remain.

Seven runs are committed in **[evidence/](./evidence/)** with a guide to reading them. The
five replays regenerate from the current code with `python -m tools.replay.make_evidence`.

### 8. Discovery — where the Artifact came from

This is the half with a model in it, and it only ever runs against a non-production
environment (the code refuses otherwise).

**Start with a goal:**

```bash
python -m tools.start
```

```
What do you want to do today?: look up a member and read their savings balance

  capability  member.read_savings_balance
  role        balance_reader — View member information and balances.
  goal        Look up member {member_number} and read their current savings balance
  input       member_number      string  ^[0-9]{5}$  (sensitive)

  returns     succeeded         -> outputs:
                                   savings_balance    money
              business_outcome  -> one of:
                                   MEMBER_NOT_FOUND   resolver: member
                                   NOT_AUTHORIZED     resolver: institution_staff
                                   NO_SAVINGS_ACCOUNT resolver: member
              failed | refused | aborted | outcome_unknown  (engine; not reviewed here)

Approve this contract? [Y/n/e]  y
member_number [54321]: 12345
Watch the browser? [Y/n]  y
```

The model proposes the Contract and the narrowest Role from the goal; the Reviewer approves
it (`e` saves it to `contracts/` for editing first; `n` saves nothing). Then the browser
opens and the run is narrated turn by turn. When it reaches the goal, the **second review**
starts in the same terminal — the Artifact, the plan of steps the Recorder compiled:

```
  member.read_savings_balance 1.0.0   role balance_reader   status draft
  7 states, 6 steps, 0 watchers

  STEP 1   at s1_login      checkpoint: target t_user_id is on screen
           type   <secret login_username>
           into   target t_user_id  =  the textbox right of the caption "User ID"   (fallback: its picture)
           then   s2_user_id_entered      checkpoint: field t_user_id holds a value

  STEP 2   at s2_user_id_entered
           type   <secret login_password>
           into   target t_password  =  the textbox right of the caption "Password"   (fallback: its picture)
           then   s3_password_entered      checkpoint: field t_password holds a value

  STEP 3   at s3_password_entered
           click  target t_sign_in  =  the button named "Sign in"   (fallback: its picture)
           then   s4_search      checkpoint: target t_member_number is on screen
           risk   CONSEQUENTIAL  <- you decide: does this click commit anything?

  STEP 4   at s4_search
           type   '{{member_number}}'
           into   target t_member_number  =  the textbox right of the caption "Member number"   (fallback: its picture)
           then   s5_member_number_entered      checkpoint: field t_member_number holds a value

  STEP 5   at s5_member_number_entered
           click  target t_member_number_button  =  the button right of the caption "Member number"   (fallback: its picture)
           then   s6_members_id      checkpoint: target t_savings_balance is on screen
           risk   CONSEQUENTIAL  <- you decide: does this click commit anything?

  STEP 6   at s6_members_id
           read   target t_savings_balance  =  the control right of the caption "Savings balance", inside frame /panel   (fallback: its picture)
           into   output savings_balance
           then   s7_savings_balance_read      checkpoint: target t_savings_balance is on screen
           done   s7_savings_balance_read is terminal: SUCCEEDED

  WATCHERS   if a checkpoint fails, which screen is it?
           none yet  <- the next questions add them

Review this artifact now? [Y/n]  y

  STEP 3  click the button named "Sign in"   (target t_sign_in, s3_password_entered -> s4_search)
          is this action safe — it only navigates, commits nothing? [Y/n]  y
  STEP 5  click the button right of the caption "Member number"   (target t_member_number_button, s5_member_number_entered -> s6_members_id)
          is this action safe — it only navigates, commits nothing? [Y/n]  y
  MEMBER_NOT_FOUND: reuse watcher w_not_found — text 'No records found' (from member.open_sub_account)? [Y/n]  y
  NOT_AUTHORIZED: reuse watcher w_not_authorized — text 'not authorized to view' (from member.open_sub_account)? [Y/n]  y
  NO_SAVINGS_ACCOUNT: no watcher can recognise it yet. [t]ext on screen that means it, or [d]rop it from the contract  d
  approve as [reviewer:nasi]:

  decisions saved to artifacts/read_savings_balance.decisions.yaml
  lint, then verify-replay on member 54321 (discovery never saw it) with no model…

  APPROVED -> artifacts/read_savings_balance.1.0.0.yaml
  it is now live — replay it with no model:
    python -m tools.replay 12345 --capability member.read_savings_balance

  Watch it replay now, in a visible browser, 2s per step? [Y/n]  y
```

The two responsibilities behind those questions:

- **Risk.** Every "click" arrives Consequential/risky by default; "type", "select" and
  "read" arrive Safe. The Reviewer changes a click to Safe (the ones that only navigate)
  and leaves the unsafe ones as they are. During replay an unsafe action requires a human
  in the loop to confirm it, and if no human is present the run is refused automatically.
- **Error handling.** The current approach is prebuilt: an engineer drives the LLM through
  the known errors ahead of time, and each error's signature and how to deal with it is
  recorded as a Watcher, either before discovery or during it. The Reviewer chooses which
  to add to the capability (see the [Error handling reference](#error-handling-reference)
  below). We acknowledge the current approach is very manual and requires prior knowledge
  of the system and the workflow.

The Recorder decides nothing; each question is one it could not answer from the run. Every
click arrives Consequential and only a person downgrades it. A declared outcome needs a
watcher that can recognise it — borrowed from another approved capability on this app when
one exists — or it is dropped, because an answer the caller is promised but can never
receive is worse than none. The answers are a file, `artifacts/<name>.decisions.yaml`,
applied mechanically; approval is refused unless the result lints clean **and** replays
successfully, with no model, on a member the discovery run never saw. To redo a review:

```bash
python -m tools.start --review runs/disc_12e097f2
``` The flag-driven equivalent, for scripts:

```bash
ANTHROPIC_API_KEY=... python -m tools.discovery                 # the sub-account request, member 54321
ANTHROPIC_API_KEY=... python -m tools.discovery 99999           # same goal; expects report_outcome
```

**A goal is stated once, by a Reviewer, at discovery.** Production callers never state
goals — they invoke an approved capability by name with typed inputs (steps 1–7). A
Discovery Request is three things, and only the first is free text:

| Part | Who owns it | What it does |
|---|---|---|
| **goal** | the Reviewer, in words | what the model reads every turn |
| **Role** | `config/roles/` | bounds the goal: pages, actions, whether it may commit |
| **Contract** | the Reviewer | fixes the capability's signature *before* any run |

`contracts/*.yaml` holds one request per capability; every flag overrides one field, and
the origin is never a flag — it comes from the Tenant's own Policy file:

```bash
# a different goal, under a Role that may not commit anything
ANTHROPIC_API_KEY=... python -m tools.discovery --contract contracts/read_balance.yaml
# or spell it out
ANTHROPIC_API_KEY=... python -m tools.discovery \
    --goal "Look up member {member_number} and read their current savings balance" \
    --contract contracts/read_balance.yaml --role balance_reader --tenant bank_a \
    --values member_number=12345
python -m tools.discovery --dry-run --contract contracts/read_balance.yaml   # no key: show the request
```

Type a goal that strays outside its Role — "wire $5,000 from member 12345" under
`balance_reader` — and every step the model proposes toward it is `policy_deny` (no
`/transfers` page in that Role, no commit allowed); three denials in a row and the run ends
`give_up`. The Role bounds the goal, not the wording.

The model gets a masked accessibility list plus a screenshot and proposes **one action per
turn**; code checks it against policy and performs it. It never sees a password, never sees a
value from a field that is not a declared Readable Region, and cannot name an action outside
the vocabulary. On success the Recorder compiles a draft Artifact immediately.

```
          A VALUE ON SCREEN
                │
       ┌────────▼─────────┐
       │ is it a password?│──yes──► (protected)      never read at all
       └────────┬─────────┘
                │ no
       ┌────────▼──────────────────┐
       │ is its Target declared a  │──no──► (hidden)  ← names, birthdays, and every
       │ Readable Region?          │                    field nobody has reviewed yet
       └────────┬──────────────────┘
                │ yes
       ┌────────▼─────────┐
       │ pattern net      │  SSN · card · email · phone · date · currency
       └────────┬─────────┘
                ▼
            recorded                and in the screenshot: undeclared value cells,
                                    Sensitive Regions and text patterns painted black
```

*Redaction: structural, origin, pattern, pixels. A value on screen reaches the model only
if it is not a password, sits in a declared Readable Region, and clears the pattern net.*

**Without a key**, the same chain runs from a saved discovery run:

```bash
python -m tools.inspect.show_run evidence/01-discovery-goal-reached   # what the model saw and asked for
python -m tools.authoring.record  evidence/01-discovery-goal-reached   # compile the draft + suggestions
python -m tools.authoring.approve evidence/01-discovery-goal-reached   # apply decisions, verify, approve
```

`record` prints what it could not decide for itself — "every click is marked Consequential:
mark the safe ones Safe", "action 6 clicks 'OK' on a page visited once: interruption or part
of the flow?". Those are questions for a person, answered in
[`artifacts/open_sub_account.decisions.yaml`](./artifacts/open_sub_account.decisions.yaml).

`review` **rewrites `artifacts/open_sub_account.1.0.0.yaml` in place** — that is what
approval means here, and it is why step 9 still passes afterwards: the regenerated artifact
is equivalent to the committed one. It refuses to approve at all unless the result lints
clean *and* replays successfully on a member the discovery run never saw:

```
after review: 12 transitions, 3 watchers, 1 consequential
verify-replay on member 12345 (discovery never saw it)...
APPROVED -> artifacts/open_sub_account.1.0.0.yaml
```

It is idempotent — re-running it reproduces the committed artifact byte for byte on values
and assets.

### 9. The tests

```bash
python -m pytest -q          # 172 passing, ~5 minutes
```

Nothing is mocked: the demo app is the fixture, and each test reads as "replay for 99999 and
expect `MEMBER_NOT_FOUND`". Some assert structure rather than behaviour — that replay cannot
transitively reach a model SDK, that only one module imports Playwright, that the engine
cannot reach past the acting interface of the Surface.

> The suite starts its own demo apps on ports 5099 and 5100 and refuses to run if either is
> already taken — a shared server would have its state reset by another session mid-test.
> If it stops at startup, clear the port: `pkill -f fake_bank.app`.

---

## Error handling reference

The same two tables as Figures S4 and S5 of [REPORT_SUPPLEMENT.md](./REPORT_SUPPLEMENT.md): every runtime condition and what the engine does about it, then where each Watcher lives and how it was learnt.

| Example on screen | Condition | Who acts | Reaction | Run Result if unresolved |
|---|---|---|---|---|
| Input fails its Contract type/pattern/enum | — (caught before the run) | nobody needed | never started | **Refused** |
| A capability that commits, with nobody on shift | — (caught before the run) | an Operator, next time | never started | **Refused** |
| The click that commits | Consequential/risky Action | Operator, live | pause, show the control and its rung, click only on approval | **Aborted**, **Failed** on timeout; nothing committed |
| "No records found" | Business Outcome | nobody — it is the answer | stop | **Business Outcome** `MEMBER_NOT_FOUND` (resolver: Member) |
| "You are not authorized to view this member" | Business Outcome | institution staff, later | stop | **Business Outcome** `NOT_AUTHORIZED` (resolver: institution staff) |
| "Amount exceeds available balance", "maximum accounts reached" | Business Outcome | the Member, by supplying different input | stop | **Business Outcome** `VALIDATION_REJECTED` or a specific code |
| "System notice" interstitial | Recoverable | system | dismiss, re-check, continue | — (invisible when it works) |
| Slow or blank page, transient error | Recoverable | system | wait, retry, bounded, Safe Actions only | **Failed** when the budget runs out |
| Session expired, login page returns | Recoverable | system | sign in again with the Service Account, re-observe, continue | **Failed** when the budget runs out |
| A screen only a person's own credential clears (supervisor ID and PIN) | Escalate | Operator, live | pause, hand over the session, resume on the Checkpoint | **Aborted**, **Failed** on timeout — or **Outcome Unknown** if a Consequential/risky Action was already in flight |
| "Application error" / stack trace | Hard Failure | nobody | stop with evidence | **Failed** |
| A screen matching neither Checkpoint nor Watcher | Unknown State | Operator if Attended; Reviewer later | never guess through | **Failed** (Unattended) |
| Frozen screen after a Consequential/risky Action | Unknown State | system first (Verification Check), else Operator | look, never click again | **Outcome Unknown** |
| System died mid-Consequential/risky Action | — | a person, afterwards | write-ahead log detects it on restart | **Outcome Unknown** |

**Every surprise becomes one of four Conditions, and the test is who can
act.** *The system alone within a budget, a person during the run, or nobody in time. The
table is the one in [CONTEXT.md](./CONTEXT.md); budgets are in
[docs/error-taxonomy.md](./docs/error-taxonomy.md).*

| Level | Lives in | Watcher | Condition (see the table above) | Learnt how |
|---|---|---|---|---|
| **App-wide** | App Profile ([`config/profiles/demo-core-servicing.yaml`](./config/profiles/demo-core-servicing.yaml)), shared by every capability on the app | `w_session_expired` | Recoverable | added by a Reviewer after watching a run recover when an Operator pressed Resume without typing |
| | | `w_system_notice` | Recoverable | discovery clicked "OK" on the notice; the Reviewer made that click a Watcher, not a step |
| | | `w_approval_required` | Escalate | added by a Reviewer: only a supervisor's own credential clears it |
| **Capability-specific** | the Artifact itself, alongside the Contract's Outcome Codes | `w_not_found` | Business Outcome `MEMBER_NOT_FOUND` | a second Discovery Run on member 99999 ended `report_outcome`; provenance `disc_0a3f513c` |
| | | `w_not_authorized` | Business Outcome `NOT_AUTHORIZED` | added by a Reviewer by hand; provenance `reviewer:nasi` |

**Watchers live at two levels, and each records where it came from.** *How a
Condition is handled is the table above; this is where the Watcher that names it lives. The
Capability Store merges the App Profile's Watchers into the Artifact at load time, so
app-wide knowledge is learnt once and reaches every capability; where both declare the
same id, the Artifact's wins. A capability-specific Watcher that names an Outcome Code
must have that code in the Contract, and every declared code must have a Watcher that can
produce it: the lint refuses either alone. An unknown condition, such as
`MAX_ACCOUNTS_REACHED` for member 33333, is an Unknown State until a Reviewer turns the
evidence into a new Watcher, which is a new Artifact version.*

---

## Code organization

Three top-level packages, one direction of dependency. `cua/` is the system and is a
library: nothing in it imports from `tools/`, and nothing in it knows about the demo app.
`tools/` are entry points that wire `cua/` together, one package per stage of a
capability's life. `fake_bank/` is the target. Everything else is data the code reads or
writes. Every boundary named below is asserted by
[`tests/unit/test_boundaries.py`](./tests/unit/test_boundaries.py), which walks the import
graph, so a file that moves cannot slip out from under a rule.

```
cua/                       the system (a library; imports nothing from tools/)
├── domain/                pure: the Artifact schema, the result shape, the rules. No I/O.
├── governance/            what a Reviewer, a Role author or a Tenant owns, read from config/
├── evidence/              the trail: one Redactor in front of one writer, and a reader
├── surface/               the browser — the only package that imports Playwright
├── replay/                production: execute an approved Artifact, no model in the loop
├── authoring/             draft → approved, with no browser and no model
├── discovery/             the one package where a model is in the loop
├── settings.py            where the data lives (CUA_ROOT) and which secrets provider (CUA_SECRETS)
└── secrets.py             secrets by reference, resolved at the keystroke, never stored
tools/                     command-line entry points, one package per stage
fake_bank/                 the deliberately hostile demo app (Flask), one scenario per member number
tests/                     unit/ (no browser, no model) and app/ (against the demo app); both mirror cua/
config/ contracts/ artifacts/ overlays/ evidence/ runs/ docs/     data, not code
```

The dependency direction, bottom up. Each package imports only from those listed after the
arrow, and `domain` imports from nothing else in `cua`:

```
domain  ←  evidence, surface, governance  ←  replay  ←  authoring  ←  discovery
```

`replay` cannot reach `discovery`, and no file on the replay path imports a model SDK. The
only file that does is `cua/discovery/model.py`. Discovery never imports `replay` either:
the verify-replay that approval requires is passed in by the tool that calls it.

### `cua/` — the system

**`domain/`** — models and rules only. A test asserts it opens no file, browser, model or
clock, and imports nothing from the rest of `cua`.

| Module | What it does |
|---|---|
| `artifact.py` | The Artifact schema: a closed vocabulary of four actions, four predicates and three target rungs, so an Artifact cannot name an action the engine has no function for (ADR 0001). `merged()` folds an App Profile into an Artifact. |
| `result.py` | `RunResult`: one shape, six statuses (`succeeded`, `business_outcome`, `failed`, `refused`, `aborted`, `outcome_unknown`). |
| `rules.py` | Rules more than one package asks: does a page list cover a route, what is the route of a URL under an origin, do these inputs satisfy their Contract. |
| `placeholders.py` | The one regex for `{{name}}`, shared by the engine (render) and the lint (check) so they cannot disagree. |
| `issue.py` · `errors.py` | A lint finding with a code and a place; `CuaError`, the base of every error raised on purpose. |

**`governance/`** — the only modules that read YAML. What a Reviewer, a Role author or a
Tenant owns, read from `config/`, `artifacts/` and `overlays/`.

| Module | What it does |
|---|---|
| `policy.py` | Permissions as an intersection, Baseline ∩ Role ∩ Tenant grant ∩ Needs (ADR 0005). `policy_for()` answers "may this Artifact run at this Tenant", and the engine asks `Policy` before every action. |
| `roles.py` | Roles per vendor app, written before any discovery: pages, actions, secrets, whether it may commit, which Service Account. |
| `profile.py` | The App Profile: Watchers, Readable and Sensitive Regions shared by every capability on one app. `redactor_for()` builds the Redactor from it. |
| `store.py` | The Capability Store, the one answer to "which Artifact is live": the highest **approved** version of a capability id, with its App Profile merged and the Tenant's origin and Overlay resolved. |
| `overlay.py` | Tenant Overlays: may change how things look (origin, labels, where a control sits) and are refused if they touch transitions, the Contract or Needs. |
| `files.py` | The one YAML reader, cached by path. |

**`evidence/`** — every log line, screenshot and result leaves through here.

| Module | What it does |
|---|---|
| `redact.py` | The Redaction Chokepoint: structural (passwords never read), origin (values outside a Readable Region are `(hidden)`), pattern (SSN, card, email, phone, date, currency), and pixels (regions painted black at capture). Serves the model and the trail alike. |
| `writer.py` | `EvidenceWriter`: the trail as append-only masked JSONL, screenshots, and a write-ahead line before and after each Consequential Action. |
| `recovery.py` | Reads a trail back to find a run that died with a Consequential Action in flight. |

**`surface/`** — the only package that touches the browser. Everything above it works in
Targets, Predicates and Actions; everything below is Playwright.

| Module | What it does |
|---|---|
| `driver.py` | Launches a hardened browser (downloads off, popups closed, every request gated to the Tenant's origins), and exposes two interfaces over one driver: `Surface` acts and observes (what replay needs) and `RecordingSurface` enumerates and describes (what discovery needs). |
| `locate.py` | The rung ladder: `role_name` asks the accessibility tree, `label_anchor` finds the caption and the nearest control by geometry, `picture` falls through. Records which rung won. See [docs/targeting.md](./docs/targeting.md). |
| `screen.py` | Record-time enumeration for discovery: every control a person could act on, every label/value pair, and the durable description of what was acted on. Also the target crop. |
| `recording.py` | The record-time interface. It cannot resolve or act on a Target; a boundary test says so. |

**`replay/`** — the production path. `replay()` is the front door.

| Module | What it does |
|---|---|
| `engine.py` | The Replay Engine and the `Run`: per Transition, checkpoint → resolve → policy → act → checkpoint; Watchers on a miss; bounded recovery; escalation; the Verification Check after a Consequential Action. Every guarantee in [REPORT.md](./REPORT.md) is enforced here. |
| `predicates.py` | The four Predicates plus `all`/`any`: rendering placeholders, Target lookup, evaluation against a Surface. Adding a Predicate means editing `artifact.py` and one case here. |
| `handoff.py` | Control transfer as a lease: one holder of the live session at a time (`automation → awaiting_operator → operator_in_control → resuming`). Writes the intervention file and waits for the decision. |
| `context.py` | `RunContext` and the four Protocols the engine is given: `ActingSurface`, `SecretsProvider`, `Operator`, `Narrator`. The seams a scripted stand-in implements. |
| `narration.py` | How a run looks to a person watching it: `Console` when somebody is, `Silent` in tests and production. |

**`authoring/`** — draft → approved, deterministic, no browser and no model. Nothing here
decides anything a person did not.

| Module | What it does |
|---|---|
| `recorder.py` | Compiles a finished Discovery Run into a draft Artifact: one State and one Checkpoint per step, example values replaced by placeholders. Where it must guess it attaches a suggestion for the Reviewer. |
| `lint.py` | What a well-formed Artifact must also satisfy: no discovery literal frozen into a checkpoint, no placeholder nothing fills, no Outcome Code without a Watcher that can produce it. |
| `review.py` | Applies a decisions file mechanically, then approves only if the result lints clean and a verify-replay on inputs discovery never saw succeeds. |

**`discovery/`** — the one package where a model is in the loop. Runs only against a
non-production environment (ADR 0003).

| Module | What it does |
|---|---|
| `model.py` | The one adapter over the model SDK. Two questions are ever asked, "what next?" and "what should this capability look like?", and both come back as plain data, so a scripted stand-in is a class with one method. |
| `propose.py` | Before any run: a Contract and the narrowest Role proposed from a goal in words, for a Reviewer to confirm (ADR 0004). |
| `request.py` | `DiscoveryRequest` and `DiscoveryResult`, and how a Contract file plus this run's values becomes one. |
| `run.py` | The loop: observe → one proposed action → policy check → act → record, until one of six endings (`goal_reached`, `report_outcome`, `ask_human`, `give_up`, step limit, stuck). Hands a successful run to the Recorder. |

**Cross-cutting.** `settings.py` names the few environment switches once (`CUA_ROOT`,
`CUA_SECRETS`); loaders read it at call time. `secrets.py` resolves `secret:<name>`
references at the moment of typing, from `SECRET_<ACCOUNT>_<NAME>` variables or, beside the
demo app only, the demo accounts.

### `tools/` — entry points, one package per stage

| Package | Command | What it does |
|---|---|---|
| `start.py` | `python -m tools.start` | The front door: a goal typed in words, both reviews, one sitting. |
| `discovery/` | `python -m tools.discovery` | `contract.py` is the first review (the Contract shown and confirmed before any run); `cli.py` builds the same request from flags; `smoke_llm.py` proves the key and image path with one turn. |
| `authoring/` | `python -m tools.authoring.record` · `.approve` | The second review. `walkthrough.py` shows the draft one step at a time, `interview.py` asks what the Recorder could not decide and writes the decisions file, `review.py` applies, verify-replays and saves; `record.py` and `approve.py` are the scripted stages. |
| `replay/` | `python -m tools.replay` | `run.py` is one replay narrated to the console; `cli.py` the flags and the `--list` catalog; `make_evidence.py` regenerates `evidence/03…07`. |
| `operator/` | `python -m tools.operator` · `.web` | The Operator's side of a handoff: show the open intervention, approve, resume or abort, as a terminal or as a page on :5010. |
| `demos/` | `python -m tools.demos.b1` · `.b2` | The unlabelled icon found by its caption; one Artifact at two institutions, with and without its Overlay. |
| `inspect/` | `python -m tools.inspect.show_run` · `.a11y_dump` | Read a saved run as a story; print the accessibility view of a page as the model would see it. |
| `_cli.py` | | What the tools share and the package does not need: the `.env` key, printing a result, resetting the demo app. |

### `fake_bank/` — the target

`app.py` is the Flask console: login, search, member page with the balances panel in an
iframe, the sub-account flow, the supervisor screen, and `GET /reset`. `data.py` is the
in-memory store where each member number selects a scenario. `templates/` holds one screen
per Condition the taxonomy names. `SKIN=bank2` is the same product branded as a second
institution.

### `tests/` — two tiers, mirroring the package

`tests/unit/` runs with no browser and no model, in seconds. `tests/app/` runs against the
demo app, which `conftest.py` starts on :5099 and :5100 and resets before every test. Both
mirror `cua/`: the tests of `cua/<package>/<module>.py` are
`tests/<tier>/<package>/test_<module>.py`, and a boundary test enforces the naming.
`tests/support/` holds the hand-written Artifact and the doubles (a scripted Surface, a
scripted model, a scripted person at the prompt).

### Data, not code

| Path | What |
|---|---|
| `config/baseline.yaml` | The provider-wide floor: allowed actions, denied route keywords, hard rules. |
| `config/roles/<app>.yaml` · `config/profiles/<app>.yaml` | Per vendor app: the Roles, and the App Profile (shared Watchers, Readable and Sensitive Regions). |
| `config/policies/<tenant>.<app>.yaml` | Per institution: origin, environment, which Roles it grants and on which Service Account. |
| `overlays/<tenant>.yaml` | Appearance-only patches for a second institution running the same product. |
| `contracts/<name>.yaml` | One Discovery Request per capability: goal, Role, Contract, example values. |
| `artifacts/` | `<name>.draft.yaml` as recorded, `<name>.decisions.yaml` as the Reviewer answered, `<name>.1.0.0.yaml` approved, the only thing that replays. `assets/` holds crops of clicked controls. |
| `evidence/` | Eight committed runs with a guide; the replays regenerate from the current code. |
| `runs/<id>/` (gitignored) | Every run's masked record: `trail.jsonl`, screenshots, `actions.json`, `intervention.json`, `decision.json`. |
| `docs/` | The error taxonomy, security model, targeting, evaluation, the ADRs, and the scripts that draw the figures. [docs/modules.md](./docs/modules.md) has every module with an in → out example. |
