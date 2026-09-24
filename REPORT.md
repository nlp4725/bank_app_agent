# REPORT

An LLM works out how a task is done in a legacy bank application **once**, against a
non-production copy. That run becomes a reviewable **Artifact**. From then on the **Replay
Engine** runs it with typed inputs and **no model in the decision loop**.

Vocabulary: [CONTEXT.md](./CONTEXT.md) · worked runs: [evidence/](./evidence/) · decisions:
[docs/adr](./docs/adr) · modules: [docs/modules.md](./docs/modules.md).

## 1. Architecture

![system architecture](./docs/figures/architecture.svg)

*Figure 1.1 — One capability's path. A Reviewer states a goal and confirms the Contract the
LLM proposes. The Discovery Run drives a non-production app once, one policy-checked action
per turn. The Recorder turns the trace into a draft; the Reviewer decides which clicks are
safe and which screens are Watchers; the Verify Replay runs that candidate with no model on
a member discovery never saw, and only a pass enters the store. In production a Calling
Agent invokes the capability by name with typed inputs, the engine replays it with Policy
checked before every action, and returns one Run Result. When it cannot safely continue it
hands the live session to an Operator and resumes on a re-checked Checkpoint.*

![read_savings_balance as a state machine](./docs/figures/state_chain.svg)

*Figure 1.2 — What an Artifact is: the smaller capability, `member.read_savings_balance`,
as its state machine. A State is believed only when its Checkpoint holds, asked after every
Action; the two Watchers can fire from any State, and are consulted only when a Checkpoint
misses. Every id is read from
[read_savings_balance.1.0.0.yaml](./artifacts/read_savings_balance.1.0.0.yaml) by
`docs/figures/make_state_chain.py`, so the figure cannot drift.*

- **The boundaries are code.** Only [`cua/surface.py`](./cua/surface.py) imports Playwright;
  only [`cua/discovery.py`](./cua/discovery.py) imports a model SDK, and an import-graph test
  asserts the engine cannot reach it.
- **The Artifact is data interpreted by one engine, not generated code** (ADR 0001). The
  engine holds four actions, four predicates, three ways to find a control, the policy check,
  risk gate, retry budgets and redaction; an Artifact can only name them.
- **The Contract is fixed before discovery** (ADR 0004): the goal says what, the Role bounds
  what may be touched, discovery finds only how.

## 2. Artifact schema

```jsonc
{
  "capability": {"id", "version", "vendor_app", "role",
                 "status": "draft|approved", "approvals": []},

  "contract": {                         // all a Calling Agent depends on
    "inputs":   {"<name>": {"type", "pattern?", "sensitive", "required"}},
    "outputs":  {"<name>": {"type", "sensitive"}},     // what Succeeded returns
    "outcomes": [{"code", "meaning", "resolver": "member|institution_staff|nobody",  // business outcomes
                  "caller_hint", "retry_same_inputs": "never", "data"}]},

  "needs": {"pages": [], "actions": [], "secrets": []},   // checked against Policy

  "states":      [{"id", "checkpoint": <predicate>, "terminal?": "succeeded"}],
  "transitions": [{"from_state", "to_state",
                   "action": {"type": "click|type|select|read", "target",
                              "value?|value_ref?|into?"},
                   "risk": "safe|consequential",
                   "verify_effect?": {"goto", "predicate": <predicate>},
                   "timeout_ms?"}],

  "targets":  {"<name>": {"frame?", "rungs": [<role_name | label_anchor | picture>]}},
  "watchers": [{"id", "trigger": <predicate>, "provenance",
                "condition": "business_outcome|recoverable|escalate|hard_failure",
                "outcome?|recovery?|budget?|resume_at?|operator_instruction?"}],

  "provenance": {"discovered_by", "contract_by", "example_values"}
}

<predicate> ::= element_present | text_present | field_value | url_matches | all | any
```

*Figure 2.1 — The schema ([`cua/domain/artifact.py`](./cua/domain/artifact.py)): PreAct's
Listing 1 plus a **contract** the caller depends on, **targets** as ladders, **watchers** for
screens that interrupt any state, and **needs** so policy can refuse before the run starts.*

```json
{
  "capability": {"id": "member.read_savings_balance", "version": "1.0.0",
                 "vendor_app": "demo-core-servicing", "role": "balance_reader",
                 "status": "approved", "approvals": ["reviewer:nasi"]},

  "contract": {
    "inputs":  {"member_number": {"type": "string", "pattern": "^[0-9]{5}$", "max_length": 5,
                                  "sensitive": true, "required": true}},
    "outputs": {"savings_balance": {"type": "money", "sensitive": false}},
    "outcomes": [
      {"code": "MEMBER_NOT_FOUND", "meaning": "No member exists with that number.",
       "resolver": "member", "retry_same_inputs": "never",
       "caller_hint": "Confirm the 5-digit member number with the member and try again."},
      {"code": "NOT_AUTHORIZED", "meaning": "This login may not view that member.",
       "resolver": "institution_staff", "retry_same_inputs": "never",
       "caller_hint": "Have staff grant this login access to the member's records."}]},

  "needs": {"pages":   ["/login", "/members/*", "/search"],
            "actions": ["click", "read", "type"],
            "secrets": ["login_password", "login_username"]},

  "states": [
    {"id": "s1_login",                "checkpoint": {"type": "element_present", "target": "t_user_id"}},
    {"id": "s2_user_id_entered",      "checkpoint": {"type": "field_value", "target": "t_user_id", "non_empty": true}},
    {"id": "s3_password_entered",     "checkpoint": {"type": "field_value", "target": "t_password", "non_empty": true}},
    {"id": "s4_search",               "checkpoint": {"type": "element_present", "target": "t_member_number"}},
    {"id": "s5_member_number_entered","checkpoint": {"type": "field_value", "target": "t_member_number", "non_empty": true}},
    {"id": "s6_members_id",           "checkpoint": {"type": "element_present", "target": "t_savings_balance"}},
    {"id": "s7_savings_balance_read", "checkpoint": {"type": "element_present", "target": "t_savings_balance"},
                                      "terminal": "succeeded"}],

  "transitions": [
    {"from_state": "s1_login",                 "to_state": "s2_user_id_entered",
     "action": {"type": "type",  "target": "t_user_id",       "value_ref": "login_username"},  "risk": "safe"},
    {"from_state": "s2_user_id_entered",       "to_state": "s3_password_entered",
     "action": {"type": "type",  "target": "t_password",      "value_ref": "login_password"},  "risk": "safe"},
    {"from_state": "s3_password_entered",      "to_state": "s4_search",
     "action": {"type": "click", "target": "t_sign_in"},                                       "risk": "safe"},
    {"from_state": "s4_search",                "to_state": "s5_member_number_entered",
     "action": {"type": "type",  "target": "t_member_number", "value": "{{member_number}}"},   "risk": "safe"},
    {"from_state": "s5_member_number_entered", "to_state": "s6_members_id",
     "action": {"type": "click", "target": "t_member_number_button"},                          "risk": "safe"},
    {"from_state": "s6_members_id",            "to_state": "s7_savings_balance_read",
     "action": {"type": "read",  "target": "t_savings_balance", "into": "savings_balance"},    "risk": "safe"}],

  "targets": {
    "t_user_id":       {"rungs": [{"kind": "label_anchor", "anchor": "User ID",  "role": "textbox", "relation": "right_of"}]},
    "t_password":      {"rungs": [{"kind": "label_anchor", "anchor": "Password", "role": "textbox", "relation": "right_of"}]},
    "t_sign_in":       {"rungs": [{"kind": "role_name", "role": "button", "name": "Sign in"},
                                  {"kind": "picture", "asset": "artifacts/assets/member.read_savings_balance/03_target.png", "threshold": 0.94}]},
    "t_member_number": {"rungs": [{"kind": "label_anchor", "anchor": "Member number", "role": "textbox", "relation": "right_of"}]},
    "t_member_number_button":
                       {"rungs": [{"kind": "label_anchor", "anchor": "Member number", "role": "button", "relation": "right_of"},
                                  {"kind": "picture", "asset": "artifacts/assets/member.read_savings_balance/05_target.png", "threshold": 0.94}]},
    "t_savings_balance": {"frame": {"url_contains": "/panel"},
                       "rungs": [{"kind": "label_anchor", "anchor": "Savings balance", "relation": "right_of"}]}},

  "watchers": [
    {"id": "w_not_found",      "trigger": {"type": "text_present", "value": "No records found"},
     "condition": "business_outcome", "outcome": "MEMBER_NOT_FOUND", "provenance": "reuse:member.open_sub_account"},
    {"id": "w_not_authorized", "trigger": {"type": "text_present", "value": "not authorized to view"},
     "condition": "business_outcome", "outcome": "NOT_AUTHORIZED",   "provenance": "reuse:member.open_sub_account"}],

  "provenance": {"discovered_by": "disc_5d0cdc53", "contract_by": "reviewer",
                 "example_values": {"member_number": "12345"}}
}
```

*Figure 2.2 — A whole approved Artifact, verbatim from
[read_savings_balance.1.0.0.yaml](./artifacts/read_savings_balance.1.0.0.yaml). One
approval, because nothing in it commits. Success is not an Outcome Code: it is the Run
Result `Succeeded` carrying `outputs`, reached at the State marked `terminal: succeeded`;
Outcome Codes are only the legitimate non-happy answers. The Watchers were borrowed from `open_sub_account`
on the same app, which is what their provenance says. The balance is in an iframe, hence
the `frame` on its Target.*

- **One State per step** (ADR 0007): after a `type`, the field is non-empty; after a
  `click`, the next control is there. A field that did not take its text is caught right there.
- **A state machine, not a step list.** The engine can always ask "which State holds now?",
  and recovery, Operator resume and re-login after a session expiry all reduce to that.
- **Interruptions are Watchers, not steps.** A Watcher can fire from any State and is consulted
  only when a Checkpoint misses; the ones shared by every
  capability on the app live in the App Profile.
- **Closed vocabulary, checked twice.** The schema rejects `download` by parsing; the lint
  ([`cua/lint.py`](./cua/lint.py)) rejects a leftover discovery literal, an outcome no watcher
  can produce, Needs outside the Role, a commit with no Verification Check. The Capability
  Store ([`cua/governance/store.py`](./cua/governance/store.py)) is the one answer to "which
  Artifact is live?"; nothing under `runs/` is ever replayed.

## 3. Determinism & error handling

```
  1 PRECONDITION  does the from-state's checkpoint hold?
  2 RESOLVE       walk the ladder; record the rung; stop rather than guess
  3 POLICY        this route, this action type, right now
  4 RISK GATE     consequential? unattended without a Verification Check → refused
  5 ACT           click / type / select / read
  6 OBSERVE       to-state's checkpoint holds? else a Watcher? else Unknown State
```

*Figure 3.1 — One Transition in [`cua/engine.py`](./cua/engine.py). Policy is asked before
acting, Checkpoints and Watchers after. Determinism is: no model, a closed vocabulary, the
matched rung recorded, a Checkpoint after every action, placeholders enforced by lint, waits
through the browser, a loop guard.*

```
          SCREEN AFTER AN ACTION
                  │
         ┌────────▼─────────┐
         │ to-state's       │──yes──► next Transition
         │ Checkpoint holds?│
         └────────┬─────────┘
                  │ no
         ┌────────▼─────────┐              attended:   Escalate to an Operator
         │ a Watcher fires? │──no───► UNKNOWN STATE   unattended: Failed
         └────────┬─────────┘              after a commit: Verification Check looks,
                  │ yes                                    never clicks again
    ┌─────────────▼────────────────────────────────────────────────────┐
    │ Business Outcome   nobody acts, it is the answer  → stop, code   │
    │ Recoverable        the system, within a budget    → fix, re-check│
    │ Escalate           an Operator, during the run    → pause, resume│
    │ Hard Failure       nobody in time                → stop, evidence│
    └──────────────────────────────────────────────────────────────────┘
```

*Figure 3.2 — Every surprise becomes one of four Conditions; the test is who can act.
Budgets in [docs/error-taxonomy.md](./docs/error-taxonomy.md).*

![read_savings_balance under four runs](./docs/figures/read_savings_balance_paths.svg)

*Figure 3.3 — Figure 1.2 under four real replays, drawn from their trails. The happy path
never leaves the chain. The other three miss the same Checkpoint and get three answers:
`99999` is a Business Outcome, stop with `MEMBER_NOT_FOUND`; `88888` is Recoverable, the
engine finds the login State holds and runs the chain again from there; `44444` is an
Escalate, a supervisor acts in the live browser and the run resumes at the State that now
holds.*

- **One Run Result**: Succeeded, Business Outcome, Failed, Aborted, Refused (nothing
  touched), or Outcome Unknown: a commit happened and could not be confirmed, so do not
  retry, a person must look.
- **Every commit carries a Verification Check.** When the screen after a consequential click
  does not resolve, the engine looks for the effect instead of clicking again. Member 33333
  hits a held-out condition, `MAX_ACCOUNTS_REACHED`, and the check confirms the commit did
  not take effect. Adding that Watcher and code is a new version: the learning loop.
- **The hole I know about.** The check runs only on the unrecognised route, so a Recoverable
  firing *after* a commit would rewind and commit again. Not reachable in this app; fix is
  item 0 of §7.

## 4. Heterogeneity & multi-tenant

![one turn, three representations](./docs/figures/three_representations.svg)

*Figure 4.1 — One turn three ways, after AgentRR's Figure 3: the masked screenshot the model
saw, the accessibility list it read, the recorded Target. This is the unlabelled search icon:
an `<img>` in a `<button>` with no alt, so it has no accessible name and a text-only agent
cannot see it.*

- **A Target is a ladder**: computed name, then caption plus layout, then a picture. Each
  breaks for a different reason, replay records which rung matched, and a Target stores a
  relationship, never a measurement. The picture rung is recorded but not matched (§7).
- **The Surface seam.** The engine speaks nine verbs to `Surface`; Predicates are evaluated
  above that line, so a second surface implements nine methods, not the Predicate language.
  The three rungs exist off the web too (UI Automation, AX). Web-shaped: `url_matches` and
  `frame`.

```
   App Profile     per vendor app     shared Watchers, Readable and Sensitive Regions
        +
   Artifact        recorded once      the flow; its own Watchers win on a clash
        +
   Tenant Overlay  per institution    how a control is FOUND: labels, anchors, relations
                                      never what the flow DOES: transitions, contract, needs
        =
   what replays at this Tenant
```

*Figure 4.2 — Three-level composition ([`cua/overlay.py`](./cua/overlay.py)). The
Artifact recorded at First Credit Union fails honestly at Lakeside Savings, `unknown_state`
at the first Checkpoint because the field is called "Find member by #", and runs unchanged
with a 20-line Overlay ([overlays/lakeside.yaml](./overlays/lakeside.yaml)). An Overlay that
adds a transition, changes the contract or widens needs is refused. The Fallback Match
rate, how often a ladder got past rung 1, is the per-tenant drift alarm.*

## 5. Escalation & handoff

```
  automation ──► awaiting_operator ──► operator_in_control ──► resuming ──► automation
       │                 │                     │                   │
       └─────────────────┴─────────────────────┴───────────────────┴──────► done
```

*Figure 5.1 — Control is a lease ([`cua/handoff.py`](./cua/handoff.py)): one holder
at a time, illegal moves raise.*

- **Stuck is detected** by a Watcher whose Condition is `escalate`, an Unknown State in an
  attended run, or during discovery the model calling `ask_human`, and a stuck detector. An
  `Intervention` file carries the State, the reason, the live URL, a screenshot and the
  instruction a Reviewer wrote once on the Watcher.
- **Same browser, same page.** Handback is Resume or Abort in the console, or the engine
  noticing the blocking screen is gone. Resume never assumes they finished: it asks which
  Checkpoint holds, so a wandered-off Operator gets `resume_checkpoint_missed`. Two
  escalations per State. Recorded: who, what decision, whether they navigated; never what
  they typed.
- **The demo's escalation is the honest shape**: member 44444 needs a supervisor's own ID
  and PIN, held in no Role's secrets. The console is a mock Flask page; the lease, transfer,
  recording and auto-resume are real.

## 6. Safety

```
   Baseline        ∩   Role            ∩   Tenant grant     ∩   Needs
   the provider        per vendor app      the institution      what the run used
   config/baseline     config/roles/       config/policies/     derived by the Recorder
   ─────────────────────────────────────────────────────────────────────────────
   each layer may narrow the one above; none may widen; disagreement → Refused
   before a browser opens, naming the layer that refused
```

*Figure 6.1 — Permissions ([`cua/governance/policy.py`](./cua/governance/policy.py),
ADR 0005). `bank_b` does not grant `account_opener`, so the Artifact that works for `bank_a`
is Refused there, no browser opened. Enforced on every request the browser makes: `/leaky`
renders a 1×1 image pointing off-origin with member data in the query string, and the
allowlist aborts it before it leaves.*

- **Every click arrives Consequential.** Only a Reviewer may downgrade one to Safe. An
  Artifact with one needs two named approvals; an unattended run whose commit has no
  Verification Check is Refused. The Service Account follows from the Role: `balance_reader`
  signs in as `svc_read`, which the bank app itself refuses at the sub-account form.

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

*Figure 6.2 — Redaction ([`cua/redact.py`](./cua/redact.py)): structural, origin,
pattern, pixels. Origin is the only layer that can hide a name, because no pattern finds one.
Default-deny fails safe: a screen added next year hides its values until a Reviewer declares
otherwise.*

- **The strongest control is not masking.** Evidence records only identifiers we generated,
  never page text. Outputs reach the caller in full and are masked in the record. NER is not
  in the data path: 90–95% recall is a disclosure rate, not a gate.
- **Limits** ([docs/security-model.md](./docs/security-model.md)): pixels are the residual
  risk, since controls are never painted; route keyword deny-lists are a weak second net;
  prompt injection is mitigated by the model only proposing; there is no identity system
  behind approvals. Above all: discovery runs against non-production only, and replay calls
  no model.

## 7. Cuts

**Cut deliberately**: the operator console is a mock over the run directory; no catalog API
beyond `--list`; one vendor app and one surface, so §4 is an argument; **no LLM fallback on
replay**, by design; the picture rung is a stub; no drift dashboard or identity system;
versioning is one-deep, so re-approving replaces the live capability, and the Store's
"highest version" is a string sort.

**Next, in order**: (0) ask the Verification Check *before* a commit and skip it when the
effect is already there, so a rewind can never open a second account; (1) `NO_SAVINGS_ACCOUNT`
as an Outcome Code with its Watcher; (2) the drift alarm, reading evidence across runs;
(3) replay N times and report flakiness ([docs/evaluation.md](./docs/evaluation.md)); (4) a
second `Surface`, so the seam is proven.

## References

- **PreAct** (Li, [arXiv:2606.17929](https://arxiv.org/abs/2606.17929)): the Artifact's
  shape, executing the state machine rather than regenerating a script, verify-before-store.
  Departure: no model fallback at replay, so Watchers are global and an unrecognised screen stops.
- **AgentRR** (Feng et al., [arXiv:2505.17716](https://arxiv.org/abs/2505.17716)): record →
  summary → replay, check functions as the safety boundary, "untrusted record, trusted
  replay", which is why discovery runs against non-production only (ADR 0003).
- The ordered ladder and stop-rather-than-guess come from RPA practice: UiPath's ranked
  selectors with a Computer Vision fallback, OpenAdapt's halt-instead-of-guessing
  ([docs/targeting.md](./docs/targeting.md)).
