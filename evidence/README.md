# Evidence

Eight runs, chosen to show the whole thread once: a real LLM discovery run, the draft it
compiled, and five replays of the approved capability — one clean, one business outcome, one
escalation a person resolves, one held-out condition, one refused before the browser opened.
Folders 9–11 add a second capability made the current way: its Business Outcome Watchers
learnt by probing rather than typed in review, used at replay, and a flag cleared by a person
at the keyboard rather than a scripted Operator.

The five replay folders are regenerated from the code as it stands with
`python -m tools.replay.make_evidence`, so what they show is what the system does now rather
than what it did when somebody last copied a folder. The two discovery folders are real
model runs and stay as recorded.

Every folder holds `trail.jsonl`, the append-only redacted record of that run. Replay folders
also hold `console.txt`, which is the most readable view: one line per transition naming the
target, **which rung of the ladder matched**, and the risk label.

Capability under test: [`artifact/open_sub_account.1.0.0.yaml`](./artifact/) — approved,
role `account_opener`, 13 states, 12 transitions, 7 watchers, 1 consequential action. Beside
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
| 8 | `08-discovery-read-balance` | a second capability, discovered from a goal typed in words, under the current masking and crop rules | `goal_reached`, 7 turns |
| 9 | `09-discovery-learnt-outcomes` | `read_savings_balance` from an empty store: the happy path, then one probe per outcome | `goal_reached` + `report_outcome` ×2 |
| 10 | `10-replay-learnt-outcomes` | that Artifact at replay with no model: clean, and the Watchers the probes taught | `Succeeded`; `Business Outcome` MEMBER_NOT_FOUND, NOT_AUTHORIZED |
| 11 | `11-replay-human-handoff` | member 44444 cleared by a person in the live browser | `Succeeded` after handoff |

## 1 — discovery, goal reached

14 turns: `observed → proposed → policy_allow → acted`, repeated. The model signed in with
secrets it never saw, found the unlabelled search icon by its neighbouring caption, dismissed
an interstitial itself, read a value out of an iframe, and stopped at the confirmation screen.

Redaction was on throughout, with one exception found afterwards and corrected in place: the *visible text* block of each `observed` event went through the pattern net only, so the member's name reached the model five times in this run. Page text now goes through origin masking like the cells do (`Redactor.page_text`), and the five occurrences in this trail were replaced with `(hidden)` on 23 Sep 2026 — the one edit ever made to a recorded run, made because a name in a public repository outranks "stays as recorded". Another thing these two folders predate: the screenshots here paint only the two declared Sensitive Regions (member name, member since). Since then the image channel took the text channel's default-deny — every value cell not declared readable, and the member number in the heading, are painted too (see `03`–`06`, regenerated) — and target crops are taken before acting and only for clicks. These two runs are real model runs and stay as recorded rather than being re-bought; the values visible in them are the demo app's seed data.

In the `observed` events the model is reading things like
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

The production path, attended: a capability that commits never runs with nobody on shift.
`console.txt` shows every transition and its rung: `t_sign_in` by `role_name`, every text
field by `label_anchor` (rung 1 finds nothing on this app's inputs). Before the consequential
`t_continue` the trail shows `approval_requested` naming the control and its rung, the
Operator's `operator_acted decision=approve`, then `approved`, and only then the click.
`approval.json` is that request as the Operator saw it, with the screenshot taken before
anything was committed.

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
intervention_raised  s5_member_number_entered   + intervention.json + screen_1.png
operator_acted       by=operator:callback  decision=resume  navigated=true
resumed              s7_members_id
approval_requested   s12_members_id   t_continue (role_name)   + approval.json + screen_2.png
operator_acted       by=operator:callback  decision=approve
approved             s12_members_id
result               succeeded
```

Two requests reached the same Operator in this run: the escalation, because a screen only
a person could clear; and the approval, because the click that opens the account is
Consequential and never happens without a person saying so.

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
checkpoint_missed    s13_members_id   expected=t_new_account_number
verification_check   s12_members_id   took_effect=false
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

## 8 — discovery, a second capability

`member.read_savings_balance`, from the goal "look up a member and read their savings
balance" typed at `tools.start`; the model proposed the Contract and the `balance_reader`
Role, a Reviewer approved both, and this run followed. Seven turns, no consequential action.
It is the run recorded after every masking rule was in place: the page text the model read
carries no name (`grep -c "Jane" trail.jsonl` → 0), the screenshots paint every undeclared
value, and the two crops (`03_target.png`, `05_target.png`) are of the Sign in button and the
search icon, taken before the click. The figure "one turn, three representations" in the
REPORT is drawn from turn 5 of this folder.

## 9 — discovery, outcomes learnt by probing

Recorded with no approved Artifact on disk, so there was no Watcher to borrow. Three real
model runs from one `tools.start` sitting:

| Run | Input | Ending |
|---|---|---|
| `disc_e21d888a` | member 12345, the happy path | `goal_reached`, 7 turns — `draft.yaml` compiled |
| `disc_c8ec23aa` | member 99999, probing MEMBER_NOT_FOUND | `report_outcome`, quote "No records found" |
| `disc_f07651e8` | member 22222, probing NOT_AUTHORIZED | `report_outcome`, quote "You are not authorized to view member 22222." |

The probe inputs come from `outcome_examples` in
[`contracts/read_savings_balance.yaml`](../contracts/read_savings_balance.yaml).
`disc_e21d888a/probes.json` names which run probed what. The Recorder's `watcher_from_run`
checked each quote against the last screen that run observed, and wrote the probed member
back as a placeholder, so the second trigger is
`You are not authorized to view member {{member_number}}.` and matches any member. The
Reviewer accepted both with a yes, and dropped NO_SAVINGS_ACCOUNT, which the demo bank never
shows. Result: [`artifact/read_savings_balance.1.0.0.yaml`](./artifact/), each Watcher's
`provenance` naming the probe run it came from. The review can be redone from these folders
with no model call: `python -m tools.start --review evidence/09-discovery-learnt-outcomes/disc_e21d888a`.

## 10 — replay, the learnt Watchers

The approved Artifact with no model. `succeeded`: member 12345, the balance returned to the
caller and absent from the trail. Then the two probed members:
`member-not-found` matches `w_member_not_found` → `business_outcome MEMBER_NOT_FOUND`;
`not-authorized` matches `w_not_authorized` → `business_outcome NOT_AUTHORIZED`. Each with
its resolver, caller hint and `retry_same_inputs: never`.

## 11 — replay, a person takes the live session

The same escalation as `05`, with a person rather than a scripted Operator: the run paused
on the supervisor screen (`intervention_raised` + `intervention.json` + `screen_1.png`), a
person signed off in the browser the automation was using, and the engine saw the blocking
screen gone, re-oriented and finished `succeeded`. The trail records
`operator_acted by=auto:blocker cleared`, the URL before and after, and nothing typed —
no supervisor ID or PIN appears in this folder. Resuming from the console
(`python -m tools.operator resume`) instead records the Operator's own name.

## Reproducing these

```bash
python -m fake_bank.app                       # http://127.0.0.1:5001
python -m tools.replay 12345 --attended       # 3 — succeeded; you approve the commit
python -m tools.replay 99999 --attended       # 4 — business outcome
python -m tools.replay 33333 --attended       # 6 — unknown state
HEADED=1 python -m tools.replay 44444 --attended   # 5 — watch it pause for a person
python -m tools.replay.make_evidence          # all of 3–7 with a scripted Operator
```

Discovery needs `ANTHROPIC_API_KEY` and costs a few cents:
`python -m tools.start`. Runs land in `runs/<run_id>/`; the folders here are copies.
