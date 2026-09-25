# REPORT

## 1. Architecture

![system architecture](./docs/figures/architecture.svg)

**Figure 1.1 — One capability's path.**

**Key decisions.**

- **The shape is record-and-replay**, after PreAct from Li et al.<sup>[1]</sup> and
  AgentRR from Feng et al.<sup>[2]</sup>: an LLM-driven Discovery module that captures a trace, a
  deterministic Recorder that turns the trace into an Artifact, a Replay Engine that
  executes whichever Artifact it is handed, and an Artifact Store that every Calling Agent
  and every Tenant draws from.
- **RBAC for the agent.** When the Contract is proposed from the goal, the narrowest
  Role that can do it is chosen with it ([config/roles/](./config/roles/)):
  `balance_reader` may "click" only to navigate, never to cause an irreversible
  consequence (open a sub-account, move money).
- **Policy is four files, four owners.**
  - **Baseline**, owned by the agent vendor: not a grant but the floor the product never
    crosses for any Tenant, which a Tenant's file can narrow and never widen.
  - **Role**, written by a Reviewer (agent vendor) once per app, before any discovery:
    the pages, actions, secrets and Service Account one job needs.
  - **Tenant Policy**, owned by the institution, the access authority: which Roles it
    grants, its origins and which of them is the test copy, and any further narrowing of
    pages.
  - **Needs**, derived from the Discovery Run: a declaration from discovery, "these are
    what I need to finish this capability", checked against the Tenant's grant before
    each replay, so a capability that cannot run here is Refused with nothing touched.
- **Review Gate.** The Reviewer is presented with the drafted Artifact and has two
  responsibilities: declare each click Safe or Consequential/risky (a click is risky by
  default), and add the error handling (a prebuilt error handling list) the capability
  needs.
- **Verify Replay before finalizing.** After the Reviewer's decisions, a Verify
  Replay runs the candidate with no model on a member discovery never saw; only a pass is
  saved, as a new version.

**Left out.** Automatic error recording and building.
In PreAct<sup>[1]</sup>, a failed replay during discovery goes back to the LLM, which
adds the failed run as error handling automatically.

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

The schema every Artifact conforms to, adapted from PreAct<sup>[1]</sup>. For the
block-by-block description see §S1 of [REPORT_SUPPLEMENT.md](./REPORT_SUPPLEMENT.md).

## 3. Determinism & error handling

**How replay runs.** The Replay Engine uses the
Artifact as its guidance and Python plus Playwright as its hands and feet. It walks the
Artifact's transition list in a `while` loop; for each transition it asks Playwright
narrow questions about the live page and acts, in this order: (1) am I in the right
place? the from-state's Checkpoint; (2) find the spot I need to act on: the Target's
ladder; (3) may I, and is it risky? the Policy check, then the risk gate, where a
Consequential/risky click waits for an Operator's approval; (4) act: the transition's
Action, one of "click", "type", "select", "read"; (5) did I arrive? the to-state's
Checkpoint, and if it holds, the next transition. If a Checkpoint does not pass, the
engine goes down the Watcher list, and the first match decides: recover and continue,
return a business outcome, hand to a human, or stop. If no Watcher matches it is an
Unknown State: verify the effect if the action was a commit, hand over if a person is
present, otherwise quit with a screenshot. Waiting is never a sleep: a Checkpoint is
polled until it holds or the transition's `timeout_ms` runs out, and every retry has a
budget.

**Error handling.** There are two kinds of error. An **app-level** error is well known
and pre-established, such as a timeout, a session expiry or a system notice; it is
recorded in the App Profile, by an engineer stress-testing the app ahead of time. A
**capability-level** error is derived from runs: an engineer builds the edge cases for
that capability (one member number per condition here) and uses the LLM to derive what
each one looks like and what to do about it. Both kinds become Watchers on one list, a
Watcher being what a screen means (its trigger) and what to do about it (its Condition
and reaction), and at the Review Gate the Reviewer chooses which to add to the
capability (Figure S5). See Figures S4 and S5 in
[REPORT_SUPPLEMENT.md](./REPORT_SUPPLEMENT.md) for the error handling tables: every
Condition with its reaction and Run Result, and where each Watcher lives.

**Improvement on error handling.** We acknowledge the current approach is very manual
and requires prior knowledge of the system and the workflow. See §7, Cuts, for the
suggested improvement.

## 4. Heterogeneity & multi-tenant

**Layout drift.** We use the accessibility tree. A button is found by its name. If a
control has no name, like a box, it is found by a nearby object with a name, "Member
number", then a relative location, "right of". So if there is a layout drift, we can
still find it.

**Name change between tenants.** If a name changes between institutions, we patch it in
an overlay file that says: in institution A, look for "Find member by #" instead of
"Member number".

## 5. Escalation & handoff

**What "stuck" means.** Every stop starts the same way: a Checkpoint does not match the
live screen within the transition's `timeout_ms` (6 s by default). Then there are two
cases:

- **Intentional error handling**: the screen matches one of the known errors, a Watcher,
  and that Watcher's Condition decides. A business outcome, a recoverable and a hard
  failure are all handled or ended without a person; only a Watcher whose Condition is
  `escalate`, a known screen that only a person can clear, counts as stuck.
- **Surprise**: the screen matches no Watcher, an Unknown State. Always stuck.

Both hand over the live session only when an Operator is present: the run waits
`--wait` seconds (240 by default) for the Operator to resume or abort, then fails on
timeout, and no State may escalate more than twice. Unattended, the run fails as
`escalation_required` or `unknown_state`.

**Handoff.** The run pauses, writes an intervention request (capability, State,
reason, live URL, screenshot, the Reviewer's instruction) and gives the lease to the
Operator, who works in the same browser window, on the same page. Control comes back
on Resume, on Abort, or when the engine sees the blocking screen is gone. Resume
re-checks which Checkpoint holds and continues from there. Recorded: who acted, the
decision, and whether the URL changed.

## 6. Safety

**What the LLM can access.** A model is only ever in the loop during discovery, and three
walls bound it there:

1. **Non-production only.** Discovery runs against a separate server with no access to
   real data.
2. **A least-privilege Role, chosen from the goal.** The Role (§1) fixes the pages, the
   action types, the secrets and the Service Account the model may use, and nothing
   outside it is available whatever the goal says.
3. **Network and per-tenant limits, per Policy (see §1).** Checked on every action the
   model proposes during the discovery run; the browser itself aborts any request to an
   origin outside the allowlist, including ones the page starts.

**What the LLM can see.** (Drawn as a decision chain in [README.md](./README.md#8-discovery--where-the-artifact-came-from).) Every observation passes through layers of redaction before it
reaches the model, as text and again as pixels:

1. **A secret is never read at all.** A password field's contents are never read,
   whatever the declarations say. Beyond that, secrets are declared by name in the Role
   ([config/roles/](./config/roles/)) and referenced by name in the Artifact; the value
   is substituted at the keystroke and never enters the observation, the trail or the
   file.
2. **A value is hidden unless its region is declared readable.** Readable Regions are
   declared per app in the App Profile
   ([config/profiles/demo-core-servicing.yaml](./config/profiles/demo-core-servicing.yaml));
   every other value, and every field nobody has reviewed yet, is `(hidden)`.
3. **A pattern net** catches what comes through: SSN, card, email, phone, date, currency.
4. **The screenshot is redacted too.** Undeclared value cells, declared Sensitive Regions
   and declared text patterns are painted black at capture, before crop and downscale.

**At replay there is no LLM**, so the gate is on the Artifact instead. Its Needs, the
pages, actions and secrets the discovery run was seen to use, are declared in the file
and checked against the Baseline, the Role and the Tenant's grant before a browser opens
and again before every action. Every click was unsafe until the Reviewer declared it Safe,
and a Consequential/risky one never runs without an Operator present. And some actions
are not allowed at all: the engine implements only "click", "type", "select" and "read",
and the Baseline names what was considered and refused, download, upload, script
execution, new tabs, and any route with `delete`, `admin`, `wire` or `transfer` in it
([config/baseline.yaml](./config/baseline.yaml)).

**Limits.** Two things this does not fully protect against:

- **Screenshots can still leak.** Buttons and fields are never blacked out, because the
  model has to see what it clicks, so a value shown inside a control can reach it.
- **Prompt injection is contained, not solved.** Text on a page can try to instruct the
  model. The model can only propose, and code checks every action, so the worst case is
  a wasted discovery run, never a production one.

## 7. Cuts

**Cut**:

1. **Money movement.** The current product does not support it: any route with `wire`,
   `transfer` or `payment` is refused at the Baseline, and the `funds_mover` Role is kept
   in the roles file only as the shape of that future feature.
2. **Automatic error handling from production.** A production error does not route
   itself back to a non-production LLM agent to create its own error handling. Runtime
   error handling uses pre-established error lists: Watchers derived at discovery time
   and tested by an engineer. An automatic route, where an error goes back to the
   non-production path and the LLM records the handling itself, is promising, as
   PreAct<sup>[1]</sup> suggests, and is the first thing we would build next.
3. **UI drift.** We did not run an intensive drift test. The ladder logs which rung
   matched and the second skin exercises a rename and a move, but nothing beyond that.
4. **Model comparison and optimisation.** Only one model ran discovery
   (`DISCOVERY_MODEL`, default `claude-opus-5`); no model was compared against another
   and the discovery success rate was not tracked.

**Next, in order**:

1. **Production errors route back automatically** to the non-production LLM agent,
   which records the error handling as a proposed Watcher for a Reviewer to approve.
2. **A money-handling protocol**: the `funds_mover` Role, a Verification Check asked
   *before* every commit so a rewind can never pay twice, and an idempotency key the
   caller supplies.
3. **Test more drift**: replay across more skins and versions, and read the Fallback
   Match rate across runs so a tenant's drift is seen before it breaks.

## References

1. Bojie Li et al. *PreAct: Computer-Using Agents that Get Faster on Repeated Tasks.*
   Pine AI, 2026. [arXiv:2606.17929](https://arxiv.org/abs/2606.17929).
2. Feng et al. *Get Experience from Practice: LLM Agents with Record & Replay (AgentRR).*
   IPADS, Shanghai Jiao Tong University, 2025.
   [arXiv:2505.17716](https://arxiv.org/abs/2505.17716).
