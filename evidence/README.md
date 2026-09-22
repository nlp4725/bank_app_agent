# Evidence

Seven runs, chosen to show the whole thread once: a real LLM discovery run, the draft it
compiled, and five replays of the approved capability — one clean, one business outcome, one
escalation a person resolves, one held-out condition, one refused before the browser opened.

The five replay folders are regenerated from the code as it stands with
`python -m tools.make_evidence`, so what they show is what the system does now rather
than what it did when somebody last copied a folder. The two discovery folders are real
model runs and stay as recorded.

Every folder holds `trail.jsonl`, the append-only redacted record of that run. Replay folders
also hold `console.txt`, which is the most readable view: one line per transition naming the
target, **which rung of the ladder matched**, and the risk label.

Capability under test: [`artifact/open_sub_account.1.0.0.yaml`](./artifact/) — approved,
role `account_opener`, 6 states, 12 transitions, 7 watchers, 1 consequential action. Beside
it: the `draft.yaml` the Recorder produced, and `decisions.yaml`, the Reviewer's answers to
its suggestions.

| # | Folder | What it shows | Result |
|---|---|---|---|
| 1 | `01-discovery-goal-reached` | a real model driving the app, masking on | `goal_reached`, 14 turns |
| 2 | `02-discovery-business-outcome` | the model declining to force the goal | `report_outcome MEMBER_NOT_FOUND` |
| 3 | `03-replay-succeeded` | the production path, no model | `Succeeded` + outputs |
| 4 | `04-replay-business-outcome` | a legitimate non-happy answer | `Business Outcome MEMBER_NOT_FOUND` |
| 5 | `05-replay-escalation-handoff` | a person takes the live session and the run finishes | `Succeeded` after handoff |
| 6 | `06-replay-unknown-state` | a condition the artifact has never seen | `Failed unknown_state`, effect verified absent |
| 7 | `07-replay-refused-by-policy` | the same artifact at a tenant that has not granted its role | `Refused`, nothing touched |

## 1 — discovery, goal reached

14 turns: `observed → proposed → policy_allow → acted`, repeated. The model signed in with
secrets it never saw, found the unlabelled search icon by its neighbouring caption, dismissed
an interstitial itself, read a value out of an iframe, and stopped at the confirmation screen.

Redaction was on throughout. In the `observed` events the model is reading things like
`textbox (no accessible name) near text: "User ID" value: (hidden)` and a masked page text —
it works from the *label* that says which cell to read, not from the value in it.

`draft_compiled` is the Recorder running the moment the goal was reached: `draft.yaml` plus
**4 suggestions** for the Reviewer. The Recorder decides nothing; `artifact/decisions.yaml`
is where a person answered.

## 2 — discovery, business outcome

Six turns against member 99999. The app answered "No records found", and the model called
`report_outcome MEMBER_NOT_FOUND` rather than forcing the goal through. This is where that
watcher's provenance comes from.

## 3 — replay, succeeded

The production path. `console.txt` shows every transition and its rung: `t_sign_in` by
`role_name`, every text field by `label_anchor` (rung 1 finds nothing on this app's inputs),
the consequential `t_continue` flagged as such.

**Outputs returned to the caller:** `savings_balance $4210.00`, `new_account_number SA-2001`.
**What the trail records about them:** nothing. Grep it — the figure does not appear. Evidence
holds only identifiers we generated (`read t_savings_balance`), so page text never enters it.
That is the strongest data control here, and it is not masking.

## 4 — replay, business outcome

The checkpoint for the balance fails, `w_not_found` matches the screen, and the run returns
`MEMBER_NOT_FOUND` with its resolver (`member`), its caller hint, and
`retry_same_inputs: never`. Not a failure — the answer.

## 5 — replay, escalation and handoff

Member 44444 is flagged and only a supervisor may clear it. The credentials that clear it are
deliberately in **no** Role's secrets, so this is not "the automation is stuck", it is "the
automation must not be able to do this".

Read `trail.jsonl` in order:

```
watcher_matched      w_approval_required   condition=escalate
intervention_raised  s2_search             + intervention.json + screen_1.png
operator_acted       by=auto:blocker cleared  decision=resume  navigated=true
result               succeeded
```

`intervention.json` is what reaches the Operator: the capability, the state, the reason, the
live URL, a screenshot, and the `operator_instruction` a Reviewer wrote once on the watcher.
The person signed off **in the session the automation was already using**. Nobody pressed
Resume: the engine noticed the blocking screen was gone, re-oriented by asking which
Checkpoint holds, and carried on to `Succeeded`.

What the trail records: the decision, who made it, and that they navigated. Not what they
typed — no supervisor PIN appears anywhere in this folder.

## 6 — replay, the held-out condition

Member 33333 already holds the maximum sub-accounts. `MAX_ACCOUNTS_REACHED` is deliberately
**absent** from the artifact and its contract, so the right behaviour is to stop, not to
guess:

```
checkpoint_missed    s7_members_id   expected=t_new_account_number
verification_check   s6_members_id   took_effect=false
result               failed  unknown_state  (+ screen_1.png)
```

The consequential click's **Verification Check** went and looked rather than clicking again,
and confirmed the commit did *not* take effect — so this is a clean `Failed`, not an
`Outcome Unknown`. Turning this into a watcher and an outcome code is a contract change and a
new version: the learning loop, on a genuinely unseen condition.

## 7 — replay, refused by policy

The same approved artifact, run for `bank_b`:

```
result  refused  "tenant 'bank_b' does not grant role 'account_opener'"
```

One event long, because nothing else happened. No browser opened, and the refusal names the
layer that refused.

## Reproducing these

```bash
python -m fake_bank.app                       # http://127.0.0.1:5001
python -m tools.replay 12345                  # 3 — succeeded
python -m tools.replay 99999                  # 4 — business outcome
python -m tools.replay 33333                  # 6 — unknown state
HEADED=1 ATTENDED=1 python -m tools.replay 44444   # 5 — watch it pause for a person
```

Discovery needs `ANTHROPIC_API_KEY` and costs a few cents:
`python -m tools.discover`. Runs land in `runs/<run_id>/`; the folders here are copies.
