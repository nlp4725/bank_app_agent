# REPORT

An LLM works out how a task is done in a legacy bank application **once**, against a
non-production copy. That run becomes a reviewable **Artifact**. From then on the **Replay
Engine** runs it with typed inputs and **no model in the decision loop**.

Vocabulary: [CONTEXT.md](./CONTEXT.md) · worked runs: [evidence/](./evidence/) · decisions:
[docs/adr](./docs/adr) · modules: [docs/modules.md](./docs/modules.md).

## 1. Architecture

![system architecture](./docs/figures/architecture.svg)

**Figure 1.1 — One capability's path.** *A Reviewer states a goal and confirms the
Contract the LLM proposes. The Discovery Run drives a non-production app once, one
policy-checked action per turn. The Recorder turns the trace into a draft; the Reviewer
decides which clicks are safe and which screens are Watchers; the Verify Replay runs that
candidate with no model on a member discovery never saw, and only a pass enters the store.
In production a Calling Agent invokes the capability by name with typed inputs, the engine
replays it with Policy checked before every action, and returns one Run Result. When it
cannot safely continue it hands the live session to an Operator and resumes on a
re-checked Checkpoint.*

## 2. Artifact schema

![read_savings_balance as a state machine](./docs/figures/state_chain.svg)

**Figure 2.1 — The core of an Artifact is a state machine, adapted from the PreAct paper
from Li et al.<sup>[1]</sup>.** *A box is a State, the amber box under it is the
Checkpoint that must hold on the live screen before the engine believes it is there, and
an arrow is a Transition holding one Action. Read the top row left to right, then the
bottom row right to left. The engine executes this graph directly. Drawn from
[read_savings_balance.1.0.0.yaml](./artifacts/read_savings_balance.1.0.0.yaml), listed in
full as Figure S1 of [REPORT_SUPPLEMENT.md](./REPORT_SUPPLEMENT.md).*

```jsonc
{
  "capability": {"id", "version", "vendor_app", "role",
                 "status": "draft|approved", "approvals": []},

  "contract": {                         // all a Calling Agent depends on
    "inputs":   {"<name>": {"type", "pattern?", "sensitive", "required"}},
    "outputs":  {"<name>": {"type", "sensitive"}},     // what Succeeded returns
    "outcomes": [{"code", "meaning", "resolver": "member|institution_staff|nobody",  // business outcomes
                  "caller_hint", "retry_same_inputs": "never", "data"}]},

  "needs": {"pages": [], "actions": [], "secrets": []},   // the access this flow needs, derived from discovery, checked against Policy

  "states":      [{"id", "checkpoint": <predicate>, "terminal?": "succeeded"}],   // a state between actions, checked against its checkpoint (what the screen must show)
  "transitions": [{"from_state", "to_state",                                     // one action, from one state to the next
                   "action": {"type": "click|type|select|read", "target",
                              "value?|value_ref?|into?"},
                   "risk": "safe|consequential",
                   "verify_effect?": {"goto", "predicate": <predicate>},
                   "timeout_ms?"}],

  "targets":  {"<name>": {"frame?", "rungs": [<role_name | label_anchor | picture>]}},   // where an action lands: the control, found by a ladder
  "watchers": [{"id", "trigger": <predicate>, "provenance",                      // this flow's own triggers, mostly business outcomes;
                                                                                   // app-level ones (session expiry, notices, errors) come from the App Profile
                "condition": "business_outcome|recoverable|escalate|hard_failure",
                "outcome?|recovery?|budget?|resume_at?|operator_instruction?"}],

  "provenance": {"discovered_by", "contract_by", "example_values"}
}

<predicate> ::= element_present | text_present | field_value | url_matches | all | any
```

**Figure 2.2 — The schema every Artifact conforms to, adapted from the PreAct paper from
Li et al.<sup>[1]</sup>.** *Four blocks are additions the bank setting forces. The
contract is all a Calling Agent depends on: typed inputs validated before a browser opens,
outputs that a Succeeded result carries, and business outcomes, the legitimate non-happy
answers such as MEMBER_NOT_FOUND, each with who can resolve it. Needs is the access the
flow was seen to use during discovery, and Policy must grant every item or the run is
Refused. Targets are ladders, so a control is found by its accessible name, then by the
caption beside it, then by a picture, and replay records which rung matched. Watchers are
the flow's own triggers, while app-wide ones such as session expiry arrive from the App
Profile at load time. The last line is the grammar for every predicate in the file: the
only four questions the engine can ask a screen, or a combination of them, and never free
text. Models in [`cua/domain/artifact.py`](./cua/domain/artifact.py); an unknown key or
action type is rejected by parsing.*

## 3. Determinism & error handling

```
  1 PRECONDITION  does the from-state's checkpoint hold?
  2 RESOLVE       walk the ladder; record the rung; stop rather than guess
  3 POLICY        this route, this action type, right now
  4 RISK GATE     consequential? unattended without a Verification Check → refused
  5 ACT           click / type / select / read
  6 OBSERVE       to-state's checkpoint holds? else a Watcher? else Unknown State
```

**Figure 3.1 — One Transition in [`cua/engine.py`](./cua/engine.py).** *Policy is asked
before acting, Checkpoints and Watchers after. Determinism is: no model, a closed
vocabulary, the matched rung recorded, a Checkpoint after every action, placeholders
enforced by lint, waits through the browser, a loop guard.*

| Example on screen | Condition | Who acts | Reaction | Run Result if unresolved |
|---|---|---|---|---|
| Input fails its Contract type/pattern/enum | — (caught before the run) | nobody needed | never started | **Refused** |
| "No records found" | Business Outcome | nobody — it is the answer | stop | **Business Outcome** `MEMBER_NOT_FOUND` (resolver: Member) |
| "You are not authorized to view this member" | Business Outcome | institution staff, later | stop | **Business Outcome** `NOT_AUTHORIZED` (resolver: institution staff) |
| "Amount exceeds available balance", "maximum accounts reached" | Business Outcome | the Member, by supplying different input | stop | **Business Outcome** `VALIDATION_REJECTED` or a specific code |
| "System notice" interstitial | Recoverable | system | dismiss, re-check, continue | — (invisible when it works) |
| Slow or blank page, transient error | Recoverable | system | wait, retry, bounded, Safe Actions only | **Failed** when the budget runs out |
| Session expired, login page returns | Recoverable | system | sign in again with the Service Account, re-observe, continue | **Failed** when the budget runs out |
| A screen only a person's own credential clears (supervisor ID and PIN) | Escalate | Operator, live | pause, hand over the session, resume on the Checkpoint | **Aborted**, **Failed** on timeout — or **Outcome Unknown** if a Consequential Action was already in flight |
| "Application error" / stack trace | Hard Failure | nobody | stop with evidence | **Failed** |
| A screen matching neither Checkpoint nor Watcher | Unknown State | Operator if Attended; Reviewer later | never guess through | **Failed** (Unattended) |
| Frozen screen after a Consequential Action | Unknown State | system first (Verification Check), else Operator | look, never click again | **Outcome Unknown** |
| System died mid-Consequential Action | — | a person, afterwards | write-ahead log detects it on restart | **Outcome Unknown** |

**Figure 3.2 — Every surprise becomes one of four Conditions, and the test is who can
act.** *The system alone within a budget, a person during the run, or nobody in time. The
table is the one in [CONTEXT.md](./CONTEXT.md); budgets are in
[docs/error-taxonomy.md](./docs/error-taxonomy.md).*

![read_savings_balance under four runs](./docs/figures/read_savings_balance_paths.svg)

**Figure 3.3 — Figure 2.1 under four real replays, drawn from their trails.** *The happy
path never leaves the chain. The other three miss the same Checkpoint and get three
answers: `99999` is a Business Outcome, stop with `MEMBER_NOT_FOUND`; `88888` is
Recoverable, the engine finds the login State holds and runs the chain again from there;
`44444` is an Escalate, a supervisor acts in the live browser and the run resumes at the
State that now holds.*

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

**Figure 4.1 — One turn three ways, adapted from the AgentRR paper from Feng et
al.<sup>[2]</sup>.** *The masked screenshot the model saw, the accessibility list it read,
and the recorded Target. This is the unlabelled search icon: an `<img>` in a `<button>`
with no alt, so it has no accessible name and a text-only agent cannot see it.*

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

**Figure 4.2 — Three-level composition
([`cua/governance/overlay.py`](./cua/governance/overlay.py)).** *The Artifact recorded at
First Credit Union fails honestly at Lakeside Savings, `unknown_state` at the first
Checkpoint because the field is called "Find member by #", and runs unchanged with a
20-line Overlay ([overlays/lakeside.yaml](./overlays/lakeside.yaml)). An Overlay that adds
a transition, changes the contract or widens needs is refused. The Fallback Match rate,
how often a ladder got past rung 1, is the per-tenant drift alarm.*

## 5. Escalation & handoff

```
  automation ──► awaiting_operator ──► operator_in_control ──► resuming ──► automation
       │                 │                     │                   │
       └─────────────────┴─────────────────────┴───────────────────┴──────► done
```

**Figure 5.1 — Control is a lease ([`cua/handoff.py`](./cua/handoff.py)): one holder at a
time, illegal moves raise.** *Figure 5.1 — Control is a lease
([`cua/handoff.py`](./cua/handoff.py)): one holder at a time, illegal moves raise.*

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

**Figure 6.1 — Permissions ([`cua/governance/policy.py`](./cua/governance/policy.py), ADR
0005).** *`bank_b` does not grant `account_opener`, so the Artifact that works for
`bank_a` is Refused there, no browser opened. Enforced on every request the browser makes:
`/leaky` renders a 1×1 image pointing off-origin with member data in the query string, and
the allowlist aborts it before it leaves.*

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

**Figure 6.2 — Redaction ([`cua/evidence/redact.py`](./cua/evidence/redact.py)):
structural, origin, pattern, pixels.** *Origin is the only layer that can hide a name,
because no pattern finds one. Default-deny fails safe: a screen added next year hides its
values until a Reviewer declares otherwise.*

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

1. Bojie Li et al. *PreAct: Computer-Using Agents that Get Faster on Repeated Tasks.* Pine AI,
   2026. [arXiv:2606.17929](https://arxiv.org/abs/2606.17929). Taken: the Artifact's shape,
   executing the state machine rather than regenerating a script, verify-before-store.
   Departure: no model fallback at replay, so Watchers are global and an unrecognised screen
   stops the run.
2. Feng et al. *Get Experience from Practice: LLM Agents with Record & Replay (AgentRR).*
   IPADS, Shanghai Jiao Tong University, 2025.
   [arXiv:2505.17716](https://arxiv.org/abs/2505.17716). Taken: record → summary → replay,
   check functions as the safety boundary, "untrusted record, trusted replay", which is why
   discovery runs against non-production only (ADR 0003).
3. RPA practice: UiPath's ranked selectors with a Computer Vision fallback, and OpenAdapt's
   halt-instead-of-guessing, for the ordered Target ladder and stop-rather-than-guess
   ([docs/targeting.md](./docs/targeting.md)).
