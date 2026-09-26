# Error taxonomy: detection and reactions

Terms are defined in [CONTEXT.md](./CONTEXT.md); this file holds the operational detail.

## The order of checks for every Transition

```
1. PRECONDITION   does the screen match what this Transition expects?
2. POLICY CHECK   is this page + action type allowed by the Tenant's Policy?
3. RESOLVE TARGET try the ladder; record which way matched; stop if none do
4. RISK GATE      Consequential? Unattended -> Refuse. Attended -> Operator approval
5. ACT            click / type / select / read
6. OBSERVE        until the Transition's timeout:
                    a. Checkpoint holds            -> next Transition
                    b. a Watcher matches           -> that Condition's reaction
                    c. neither                     -> go to 7
7. NOTHING MATCHED
     Safe Action          -> wait, reload, redo, up to the retry budget, then Unknown State
     Consequential Action -> Verification Check: done / not done / can't tell -> Escalate
```

Policy is asked *before* acting ("may I?"). Checkpoints and Watchers are asked *after* ("what happened?").

## Reactions in detail

| Condition | Retry? | Budget | Notes |
|---|---|---|---|
| Business Outcome | never | — | same inputs always give the same answer; retrying creates the loop the Calling Agent cannot escape |
| Recoverable, interstitial | dismiss once, then re-check | 2 per Transition | if the same interstitial returns after dismissal, it is an Unknown State |
| Recoverable, transient | wait + retry the action | 3 per Transition, backoff | **Safe Actions only**; never repeats a Consequential action |
| Escalate | never automatically | 2 escalations per Transition | bounded so escalate -> resume -> escalate cannot loop; an unanswered request times out to Failed |
| Hard Failure | never | — | evidence captured, run stops |
| Unknown State | never | — | Attended: Escalate. Unattended: Failed. Always captures a screenshot + page snapshot |

Budgets are **engine defaults**. A Transition may override them (`retry: {max, backoff_ms}`, `timeout_ms`) when a screen is genuinely slower, and the override is visible in review — a Transition quietly granted thirty retries should look suspicious.

Division of labour: the **engine** owns the Conditions, the order of checks, budgets, Consequential rules, the write-ahead log and the Run Result envelope. The **App Profile** and **Artifact** own which screens count as what: a trigger Predicate, its Condition, the reaction (outcome code or recovery), and its Provenance.

## Consequential Actions

1. Never retried automatically, in any Condition.
2. Never reloaded after submit (a browser resubmit is the duplicate we are avoiding); verification navigates somewhere read-only instead.
3. Unattended: an Artifact containing one is Refused before the run starts. No person, no commit.
4. Attended: the engine pauses before it and raises an approval request naming the Target and which rung matched, with a screenshot, so a wrong Fallback Match is visible before the click. The Operator approves (the engine then performs the action itself) or aborts; an unanswered request times out to Failed with nothing committed.
5. On an unclear outcome afterwards, the Verification Check decides: done -> Succeeded; not done -> safe to act again; can't tell -> Escalate, or Outcome Unknown when nobody answers.

## Crash safety

A write-ahead line is appended before and after every action:

```
10:31:05  run_abc  about_to  step=commit  risk=consequential
10:31:06  run_abc  done      step=commit  observed=confirmation_number_visible
```

On restart, a run whose last line is `about_to` on a Consequential Action is closed as **Outcome Unknown**. Safe Actions are simply re-run from the beginning.

The production answer, not built here: the caller supplies an idempotency key per invocation, and the Verification Check looks that key up in the app, turning "unknown" into a definite answer.

## Evidence, by audience

| | Escalate | Hard Failure / Unknown State |
|---|---|---|
| Reader | the Operator, live | the Reviewer, later |
| Purpose | take over this run | fix the Artifact |
| Contents | capability, current state, reason, live screenshot, session link | failed state, predicate expected vs observed, which Target matched, step trail, screenshot, page snapshot |

Both are written through the one redaction chokepoint.

## Outcome Codes

Specific codes are declared in the Contract for rules already seen (`AMOUNT_EXCEEDS_BALANCE`, `MAX_ACCOUNTS_REACHED`). `VALIDATION_REJECTED` is the catch-all, carrying the field and the on-screen message (redacted) so the Calling Agent can explain the refusal. A Reviewer promotes recurring catch-all cases into specific codes, which is a Contract change and therefore a new Artifact version.

## The result envelope

Every run returns the same shape: `status` first, then the fields that status implies.

```json
{"status":"succeeded","outputs":{…},"evidence_id":"…"}
{"status":"business_outcome","outcome":{"code":…,"resolver":…,"caller_hint":…,
  "retry_same_inputs":"never","data":{…}},"evidence_id":"…"}
{"status":"failed","step":…,"expected":…,"observed":…,"evidence_id":"…"}
{"status":"refused","reason":…}                      // nothing was touched
{"status":"aborted","by":"operator:…","at_step":…}
{"status":"outcome_unknown","step":…,"guidance":"Do not retry…","evidence_id":"…"}
```

A Watcher detects the screen and names the Outcome Code; the Contract declares what that code means and what it carries. Detection is per app and patchable by an Overlay; the declaration is stable across Tenants.
