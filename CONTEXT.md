# Computer-Use Automation

Lets AI agents operate legacy bank back-office apps that have no API: an LLM discovers a task once, the result is saved as a reusable Artifact, and deterministic replay executes it thereafter.

## Language

### Capabilities

**Artifact**:
A versioned, reviewable recording of one task on one vendor app, holding both the contract (typed inputs, typed outputs, business outcomes) and the flow that fulfils it. Called a **Capability** when speaking from the Calling Agent's point of view — same object, not a separate thing.
_Avoid_: Workflow, script, macro, recording, SOP

**Capability Store**:
Where approved Artifacts live and the one answer to "which Artifact is live?". Asked by capability id, it returns the approved version with its App Profile already merged, and knows each Tenant's address and Overlay. Every caller — the Replay Engine's entry points, the demo tools, the tests — asks it rather than opening a file, so there is one model of a capability and not two, and the tests exercise the Artifact that actually ships.
_Avoid_: Registry, catalogue, repository

**Contract**:
The part of an Artifact a Calling Agent relies on: named, typed inputs; named, typed outputs; and the Outcome Codes it may return. Fixed by a Reviewer before discovery starts — never inferred from what happened during a run.
_Avoid_: Signature, interface, schema (alone)

**Discovery Request**:
A natural-language goal plus the Contract a Reviewer confirmed for it (proposed by an LLM from the goal), with the example input values this Discovery Run will use.
_Avoid_: Task, prompt, job

**Discovery Run**:
An LLM-driven run that works out how to accomplish a goal on an app and produces a draft Artifact. Only ever performed against a Non-production Environment.
_Avoid_: Recording session, training run, exploration

**Recorder**:
The code that turns a finished Discovery Run into a draft Artifact. It makes no final judgement calls — where it must guess (is a click Consequential? is this screen an interruption, i.e. a Watcher rather than a Transition?), it attaches a suggestion for the Reviewer.
_Avoid_: Compiler, trace compiler, emitter

**Replay**:
Executing an approved Artifact with given inputs, with no LLM making decisions. The only way a Capability runs in Production.
_Avoid_: Playback, execution (alone), automation run

**Replay Engine**:
The one interpreter that executes any Artifact. It holds every function — the action vocabulary, the predicate vocabulary, the Target finders — plus the Policy check, risk gate, retry budgets, write-ahead log and redaction. An Artifact names things from those vocabularies and can express nothing else, so no Artifact can bypass a guarantee.
_Avoid_: Runner, executor, generated script

**Tenant Overlay**:
A small per-Tenant patch applied on top of an Artifact that may change how things look (origin, control labels/anchors, field positions, timeouts) but never how the Artifact behaves (transitions, contract, or safety policy). If a Tenant needs different behavior, that is a different Artifact.
_Avoid_: Override, variant, fork, per-bank artifact

**Action**:
One thing done to the surface — **click, type, select, read** — and nothing else: the engine implements exactly these four, so an Artifact cannot name another. Waiting is a property of a Transition (its timeout), not an Action; scrolling is the driver's job.
_Avoid_: Step, instruction, command, operation

**State**:
The screen as it must be after one Action — one State per step, carrying exactly one Checkpoint: what that Action must have achieved (a field now holds a value, the next control is on screen). Every step is therefore verified before the next one acts (ADR 0007).
_Avoid_: Page, screen, node

**Transition**:
A move from one State to another, carrying the Action that makes it happen, that Action's risk label and, where the Action is Consequential, its Verification Check.
_Avoid_: Step, edge, arrow

**Predicate**:
A machine-checkable claim about the screen, drawn from a closed set of four (**element present, text present, field value, url matches**) plus `all` / `any`. Every Checkpoint, Watcher trigger, Precondition and Verification Check is one. Prose belongs in a description beside it, never in its place.
_Avoid_: Assertion, condition, rule

**Precondition**:
The Predicate a Transition requires *before* acting — verify first, then act, so a click never lands on an unexpected screen.
_Avoid_: Guard, entry condition

**Checkpoint**:
The Predicate that must hold for a State to be believed — asserted after every Action rather than assumed. Never contains a Discovery Run's literal values.
_Avoid_: Assertion, expectation, success check (except for the Artifact's final one)

**Verification Check**:
A Predicate, plus where to look for it, that answers "did this Consequential Action already happen?" — used when the outcome is unclear, so the system looks instead of clicking again. Required before an Artifact may be approved for Unattended runs.
_Avoid_: Idempotency check, dedupe

**Target**:
The control an Action acts on, named once and described by the frame it lives in plus an ordered ladder of ways to find it. Replay tries the rungs in order, records which one matched, and stops rather than guessing when none do. The ladder exists because each rung breaks for a different reason — see [docs/targeting.md](./docs/targeting.md):

| Rung | Reads | Survives | Breaks on |
|---|---|---|---|
| `role_name` | the accessibility tree's computed name | moving, restyling | a rename |
| `label_anchor` | visible words plus layout ("the textbox right of *Member number*") | a control being renamed | the caption moving or being renamed |
| `picture` | a crop saved at record time | renames and re-layout | re-skinning |

A Target stores the relationship, never a measurement: distances are recomputed from the live page every run.
_Avoid_: Selector, locator (alone), element

**Fallback Match**:
A Target found by any way other than the first in its list. Allowed on any Action, always logged, and a rising rate of them for a Tenant is the signal that its app has drifted.
_Avoid_: Retry, fuzzy match

**Consequential Action**:
An Action whose effect cannot safely be repeated or undone (e.g. the click that actually opens an account). Every click starts out Consequential; only a Reviewer may mark it **Safe**, with the discovery LLM's suggestion as advice, never as the decision.
_Avoid_: Risky action, destructive action, irreversible action, dangerous step

**Secret**:
A credential (password, token) referenced only by name and substituted at the moment it is typed. Never seen by the LLM, never written to logs, evidence or Artifacts.
_Avoid_: Sensitive input, private param, password field

**Needs**:
The pages and action types an Artifact uses, derived from what its Discovery Run actually did; a Replay may start only if every Need is granted by the Tenant's Policy.
_Avoid_: Permissions, scopes, requirements

**Watcher**:
A recognisable surprise screen — a trigger Predicate, the Condition it represents, how to react, and where it came from. Consulted only when a Checkpoint misses, and can fire from any State, so it does not belong to any one Transition.
_Avoid_: Handler, trap, exception rule

**App Profile**:
The Watchers shared by every Artifact on one vendor app (session expiry, notices, app errors), so app-wide knowledge is learnt once and reaches every capability. An Artifact carries only the Watchers specific to its own flow, and those win when both match the same screen.
_Avoid_: Common watchers, shared config

**Provenance**:
Where each part of an Artifact came from — which Discovery Run, added by a named Reviewer, or learnt from a named intervention. Recorded per Watcher so a reader can tell what was discovered from what was assumed.
_Avoid_: Source, origin, history

### Conditions (what a Watcher detects mid-run)

**Business Outcome**:
The app worked correctly and returned a legitimate non-happy-path answer (e.g. member not found, not authorized). Identified by an **Outcome Code** and never retried with the same inputs.
_Avoid_: Error, not-found (as a synonym for the whole category)

**Outcome Code**:
The specific name of a Business Outcome (e.g. `MEMBER_NOT_FOUND`), declared in the Contract with its meaning, its **resolver** (the Member, institution staff, or nobody), a hint for the Calling Agent, `retry_same_inputs: never`, and any data it returns. `VALIDATION_REJECTED` is the catch-all for app-side business rules; recurring cases are promoted to specific codes, which is a Contract change and so a new version. Every declared code must have a Watcher that can produce it, and every Watcher's code must be declared.
_Avoid_: Error code, status code

**Recoverable**:
A known, transient or dismissible condition (popup, slow load, one-off app error) the system fixes **by itself** within the run, by a bounded recovery, invisible to the caller if it succeeds. If a person must act, it is an Escalate, not a Recoverable.
_Avoid_: Retryable error, soft failure

**Escalate**:
A condition only a person can resolve **during this run** (e.g. re-authenticating an expired session); the run pauses and an Operator takes control of the live session. If nobody can fix it within the run's lifetime, it is a Business Outcome or a Hard Failure instead.
_Avoid_: Handoff (that is what happens after), stuck

**Hard Failure**:
The system or app is broken in a way retrying will not fix; the run stops with debuggable evidence.
_Avoid_: Crash, exception

**Unknown State**:
A screen that matches neither the expected Checkpoint nor any Watcher. Escalated in Attended runs, Failed in Unattended runs — never guessed through.
_Avoid_: Unexpected page, drift

### The error table

Every runtime surprise is classified into one Condition. The test is **who can act**: the system alone, a person during the run, or nobody in time.

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

### Run Results (what the caller receives)

**Run Result**:
The single final answer a run returns to its caller: **Succeeded** (with outputs), **Business Outcome** (with Outcome Code), **Failed** (with step, expected, observed, evidence), **Aborted** (an Operator chose to stop), **Refused**, or **Outcome Unknown**.
_Avoid_: Bucket, status (when meaning the final answer)

**Outcome Unknown**:
A Run Result meaning a Consequential Action was performed but its effect could never be confirmed (the system died, or the screen never resolved and no Verification Check settled it). Means *do not retry* — a person must check whether it took effect.
_Avoid_: Partial failure, timeout

**Refused**:
A Run Result meaning the run was rejected before touching the app (Needs not granted by Policy, Artifact not approved, a Consequential Action in an Unattended run, invalid inputs) — a guarantee of no side effects.
_Avoid_: Blocked, denied, rejected (as result names)

### Safety

**Policy**:
The Tenant-owned rules for what automation may do on one of its apps: its Allowlist, its Environment tag, and how Consequential Actions are handled. Separate from any Artifact; owned by the institution, not the automation provider.
_Avoid_: Config, rules, guardrails (as a noun for this file)

**Baseline Policy**:
The provider-wide floor, hand-written and versioned, that governs every run on every Tenant from the first click — including Discovery Runs, which have no Needs yet and are instead bounded by their Role. A Tenant Policy may narrow it, never widen it.
_Avoid_: Global config, defaults

**Allowlist**:
The part of a Policy stating where automation may act (origins, routes) and which action types it may use. A Tenant declares every instance of its app that automation may reach — the production one and the non-production copies — and a run against any other origin is Refused before the browser opens. Enforced by code before every action, never by instructing the LLM. Effective permissions are **Baseline ∩ Role ∩ Tenant grant ∩ Needs**, a true intersection: each layer may narrow what the one above allows and none may widen it (Needs apply at Replay only).
_Avoid_: Whitelist, permitted list

**Role**:
A named permission bundle for one intent on one vendor app (e.g. `balance_reader`, `account_opener`), written before any discovery: the pages and action types it may use, whether it may perform Consequential Actions, and the Service Account it signs in as. An Artifact declares exactly one Role, and its Needs must fit inside it — checked at approval, not only at run time.
_Avoid_: Permission set, profile, persona

**Service Account**:
The login the automation uses on a Tenant's app, holding the narrowest role that the capability requires — so a read-only capability cannot move money even if every layer above it fails.
_Avoid_: Bot user, robot account, credentials

**Redaction Chokepoint**:
The single module every log line, evidence file, screenshot and returned output passes through, and the same gate on the outbound path before screen content reaches a model. Built from the App Profile, so the four layers below apply identically to a Discovery Run's captures and to a replay's failure and intervention screenshots — no caller can capture around it. How it decides what to hide is below.

**Readable Region**:
A Target whose **value** may be seen — by the model, and in evidence. Everything else is hidden, so a screen nobody has reviewed is safe by default. Declared in the App Profile, because what is sensitive is a property of the app, not of one capability.
_Avoid_: Whitelist, visible field

**Sensitive Region**:
A Target whose **pixels** are painted black when a screenshot is captured, on top of the default: every value cell whose caption is not a Readable Anchor is painted too, and so is any on-screen text matching a declared pattern. Controls are never painted — blacking out a control the model must act on would blind it — which is the residual risk recorded in [docs/security-model.md](./docs/security-model.md).
_Avoid_: Blackout, redaction zone

**Two-Person Approval**:
The rule that an Artifact containing a Consequential Action needs two named Reviewers before it may run.
_Avoid_: Sign-off, double-check

**Evidence**:
The append-only, redacted record of a run: what was done and why, which Target matched, the Policy decisions, and a screenshot plus page snapshot on failure. Written for two readers — the Operator during an escalation, the Reviewer afterwards.
_Avoid_: Logs (alone), audit trail, trace

### Redaction: what is hidden, and why

A name is just words; a birthday is just digits. **No pattern can find them.** So the
first mechanism is not *what a value looks like* but **where it came from**.

```
        A VALUE ON SCREEN
              │
     ┌────────▼─────────┐
     │ is it a password?│──yes──► (protected)        never read at all
     └────────┬─────────┘
              │ no
     ┌────────▼──────────────────┐
     │ is its Target declared a  │──no──► (hidden)   ← catches names, birthdays,
     │ Readable Region?          │                     and every field nobody
     └────────┬──────────────────┘                     has thought about yet
              │ yes
     ┌────────▼─────────┐
     │ pattern net      │  SSN · card · email · phone · date · currency
     └────────┬─────────┘
              ▼
          recorded
```

**Why default-deny.** An allowlist fails safe: a screen added next year hides its
values until a Reviewer declares otherwise. A denylist fails open, and the failure is
silent.

**Why not a detector.** A model that finds names is ~90-95% accurate. For regulated
data, the missing 5% is a disclosure, false positives mangle the record, and an audit
cannot be answered with "the classifier usually catches it". So detection is used to
*check* the redaction, never to perform it.

**The strongest protection isn't masking at all — it is not capturing.** Evidence
records identifiers we generated (event, Target name, which rung matched, placeholder,
Outcome Code, policy decision), never page text. `typed {{member_number}} into
t_member_field` has nothing to leak.

Where each channel stands:

| Channel | Gate | Guarantee |
|---|---|---|
| evidence and logs | only identifiers we generated are written | total |
| Artifact | example values became placeholders; a lint fails the build otherwise | total |
| Secrets | substituted at the keystroke, below the model and the log | total |
| Outputs to the caller | returned **in full** — they are the answer — masked in the record | total |
| Observation sent to a model (discovery only) | default-deny by Readable Region, then patterns | total for declared fields |
| Watcher extraction | a declared capture group only, never free page text | total |
| **Screenshots** | cropped, downscaled, declared **Sensitive Regions** painted black at capture | **partial — a deny-list, and the residual risk** |

And above all of it: **discovery only ever runs against a Non-production Environment,
and Replay calls no model at all**, so nothing leaves the institution during production.

**Four layers, in order, during discovery.** Each catches what the one below cannot:

```
  1. STRUCTURAL   a password is never read, whatever anyone declared
  2. ORIGIN       a value is hidden unless its caption is a Readable Region
                  ← the only layer that can hide a name or a date of birth
  3. PATTERN      what does come through still passes the net
                  SSN · card · email · phone · date · currency
  4. PIXELS       value cells not declared readable, declared Sensitive Regions and
                  declared text patterns painted black at capture,
                  cropped and downscaled
```

Measured on a real run with all four on, the model saw:

```
[5] text "Member name":      (hidden)     ← layer 2; no pattern could find a name
[6] text "Member since":     (hidden)     ← nor a birthday
[7] text "Savings balance":  $*,***.**    ← declared readable, still masked by layer 3
[8] text "Checking balance": (hidden)     ← the goal does not need it
```

and still reached the goal: **the model needs the label to know which cell to read, not
the value**, and the `read` action returns the true figure into outputs regardless.

Layers 1–3 are an allowlist. Layer 4 is a deny-list, because painting every undeclared
control black would blind the model to something it must click — which is why pixels
remain the weaker channel and the residual risk.

### People and modes

**Calling Agent**:
The AI agent (talking to a Member) that invokes Capabilities and receives Run Results.
_Avoid_: Agent (alone), bot, client

**Discovery LLM**:
The model that proposes actions during a Discovery Run; it only proposes, code performs.
_Avoid_: Agent (alone), the AI, model (alone)

**Operator**:
A staff member of the Tenant who takes control of a live session during an escalation. The only human who ever touches a live session.
_Avoid_: Agent, user, human-in-the-loop (as a noun)

**Reviewer**:
An engineer on the automation provider's side who reads redacted evidence, turns Unknown States into Watchers, and approves Artifact versions. Never sees a live session.
_Avoid_: Admin, maintainer, operator

**Attended / Unattended**:
Whether an Operator is available to answer escalations during a run.
_Avoid_: Supervised, interactive, batch

### Environment

**Tenant**:
One customer institution (bank or credit union); many Tenants run the same vendor app configured differently.
_Avoid_: Bank (when meaning the customer), client, customer

**Production / Non-production Environment**:
Whether an app instance holds real Members and real money. Non-production copies (UAT, training) hold only synthetic Members.
_Avoid_: Live/test, prod/sandbox

**Member**:
A customer of the Tenant whose records the app holds; the subject of most tasks, and the source of the most sensitive data.
_Avoid_: Customer, account holder, user
