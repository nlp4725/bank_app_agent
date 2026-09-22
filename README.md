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

No API key is needed for steps 1–7. Step 8 needs one.

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
HEADED=1 python -m tools.replay 12345
```

A browser opens and drives itself. Drop `HEADED=1` to run it headless in about 3 seconds.
The capability is `member.open_sub_account`: sign in → search → read the savings balance out
of the iframe → open a sub-account → confirm → read back the new account number.

Each line is one Transition, and **`rung=` is which way of finding the control worked**:

```
  s1_login         -> s1_login         type   t_user_id                secret:login_username    rung=label_anchor risk=safe
  s1_login         -> s1_login         type   t_password               secret:login_password    rung=label_anchor risk=safe
  s1_login         -> s2_search        click  t_sign_in                                         rung=role_name risk=safe
  s2_search        -> s2_search        type   t_member_number          {{member_number}}        rung=label_anchor risk=safe
  s2_search        -> s4_members_id    click  t_member_number_button                            rung=label_anchor risk=safe
  s4_members_id    -> s4_members_id    read   t_savings_balance                                 rung=label_anchor risk=safe
  ...
  s6_members_id    -> s7_members_id    click  t_continue                                        rung=role_name risk=consequential
  s7_members_id    -> s7_members_id    read   t_new_account_number                              rung=label_anchor risk=safe

RESULT  succeeded
OUTPUTS {'savings_balance': '$4210.00', 'new_account_number': 'SA-2001'}
TIME    3.6s     evidence: runs/run_5a4c9085
```

Three things to notice. The password was never a literal — `secret:login_username` is a
reference resolved at the keystroke. `t_member_number_button` is the **unlabelled icon
button**: rung 1 (accessibility name) finds nothing, so rung 2 finds it by the caption
beside it, and the log records which rung won. And exactly one Transition is
`consequential` — the click that actually opens the account.

### 2. The conditions, one command each

Every one of these is the *same approved Artifact* meeting a different screen.

```bash
python -m tools.replay 99999    # Business Outcome — the app's legitimate answer
python -m tools.replay 54321    # Recoverable — dismisses an interstitial, carries on
python -m tools.replay 88888    # Recoverable — session expires, the system signs in again
python -m tools.replay 44444    # Escalate — nobody on shift, so it stops
python -m tools.replay 33333    # the held-out condition, on purpose
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
  stopped at    s2_search  (w_approval_required)
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
python -m tools.operator_console     # http://127.0.0.1:5010
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
front door refuses an undeclared origin, an unapproved Artifact, a consequential action in an
unattended run with no Verification Check, and an input that fails its Contract:

```bash
python - <<'PY'
from cua.engine import RunContext, replay
from cua.store import load_capability, origin_for

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

### 5. One Artifact, two institutions

Lakeside Savings runs the same vendor product with renamed controls and the search icon
moved. The same approved Artifact, unchanged:

```bash
python -m tools.demo_b2
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
python -m tools.demo_b1
```

Prints the accessibility view of the search control (it has no name at all), then the ladder
recorded for it, then a replay showing which rung actually resolved each Target. A rising
rate of fallback matches for a tenant is the signal that their app has drifted —
see [docs/targeting.md](./docs/targeting.md).

### 7. Read any run afterwards

```bash
python -m tools.show_run                  # the most recent
python -m tools.show_run runs/run_8de312d4
```

Every run leaves an append-only redacted trail: each policy decision, each action, which rung
matched, every Watcher that fired, and a screenshot on failure with the declared Sensitive
Regions already painted black — look at
[`evidence/06-replay-unknown-state/screen_1.png`](./evidence/06-replay-unknown-state/) and
you will see the member's name and date of birth blacked out while the balances, which are
the answer, remain.

Seven runs are committed in **[evidence/](./evidence/)** with a guide to reading them. The
five replays regenerate from the current code with `python -m tools.make_evidence`.

### 8. Discovery — where the Artifact came from

This is the half with a model in it, and it only ever runs against a non-production
environment (the code refuses otherwise).

```bash
ANTHROPIC_API_KEY=... python -m tools.discover 54321
```

The model gets a masked accessibility list plus a screenshot and proposes **one action per
turn**; code checks it against policy and performs it. It never sees a password, never sees a
value from a field that is not a declared Readable Region, and cannot name an action outside
the vocabulary. On success the Recorder compiles a draft Artifact immediately.

**Without a key**, the same chain runs from a saved discovery run:

```bash
python -m tools.show_run evidence/01-discovery-goal-reached   # what the model saw and asked for
python -m tools.record   evidence/01-discovery-goal-reached   # compile the draft + suggestions
python -m tools.review   evidence/01-discovery-goal-reached   # apply decisions, verify, approve
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
python -m pytest -q          # 148 passing, ~4½ minutes
```

Nothing is mocked: the demo app is the fixture, and each test reads as "replay for 99999 and
expect `MEMBER_NOT_FOUND`". Some assert structure rather than behaviour — that replay cannot
transitively reach a model SDK, that only one module imports Playwright, that the engine
cannot reach past the acting interface of the Surface.

> The suite starts its own demo apps on ports 5099 and 5100 and refuses to run if either is
> already taken — a shared server would have its state reset by another session mid-test.
> If it stops at startup, clear the port: `pkill -f fake_bank.app`.

---

## Where things live

| Path | What |
|---|---|
| `cua/engine.py` | the Replay Engine and the `Run` module — the interpreter, and every guarantee |
| `cua/artifact.py` | the Artifact schema: the closed vocabulary an Artifact may name |
| `cua/predicates.py` | the four Predicates, their rendering and evaluation |
| `cua/surface.py` | the only module that touches a browser |
| `cua/discovery.py` | the only module that touches a model |
| `cua/recorder.py` · `cua/review.py` | run → draft Artifact → approved Artifact |
| `cua/policy.py` · `cua/roles.py` · `cua/profile.py` · `cua/store.py` | permissions, and which Artifact is live |
| `cua/redact.py` | the Redaction Chokepoint — every channel passes through it |
| `config/` | the Baseline, the Roles, each Tenant's Policy, each app's Profile |
| `artifacts/` | the draft, the Reviewer's decisions, and the approved capability |
| `evidence/` | seven committed runs, with a guide |
