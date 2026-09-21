# PRD: Computer-Use Automation System (interface.ai take-home)

Vocabulary: [CONTEXT.md](../CONTEXT.md). Decisions: [docs/adr](./adr). Error handling: [error-taxonomy.md](./error-taxonomy.md). Safety: [security-model.md](./security-model.md).

## Problem Statement

An AI agent talking to a credit-union member can answer questions but cannot *do* anything in the institution's back-office systems, because those systems have no API. Today a human operator does the clicking. The obvious fix — put an LLM in front of the screen every time — is slow, costly, non-repeatable and unreviewable, and no bank will let an unpredictable model click "Continue" on an account-opening screen unsupervised. The institution needs automation it can review before it runs, that behaves identically every time, that tells the caller the difference between "no such member" and "the system is broken", that stops rather than guesses when the screen is unfamiliar, and that can hand a stuck session to its own staff without starting over.

## Solution

A model drives the app once, in a non-production environment, to work out how a task is done. That run is compiled into an **Artifact**: a versioned, reviewable capability holding a typed **Contract** (inputs, outputs, Outcome Codes) and a state machine of **States**, **Transitions**, **Targets**, **Checkpoints** and **Watchers**. A human **Reviewer** approves it. Thereafter the **Replay Engine** executes the Artifact with no model in the loop, enforcing **Baseline ∩ Role ∩ Tenant grant ∩ Needs** before every action, classifying every surprise into one of four **Conditions**, and returning one of six **Run Results**. When it cannot safely proceed, it pauses and hands the live session to an **Operator** at the institution, then resumes on a re-checked Checkpoint.

The demo records one capability — `open_sub_account`, which reads the member's savings balance on the way through — against a deliberately hostile local Flask app standing in for a legacy servicing console.

## User Stories

**Calling Agent (the AI agent in production)**

1. As a Calling Agent, I want to discover capabilities in a catalog with typed inputs and outputs, so that I can invoke one by name without reading its steps.
2. As a Calling Agent, I want to call a capability with typed arguments and get a structured Run Result, so that I never parse screen text.
3. As a Calling Agent, I want `Succeeded` to carry the declared outputs, so that I can answer the member directly.
4. As a Calling Agent, I want `MEMBER_NOT_FOUND` returned as a Business Outcome rather than an error, so that I ask the member to re-check the number instead of reporting a fault.
5. As a Calling Agent, I want every Outcome Code to state its **resolver**, so that I know whether the member, institution staff, or nobody can act on it.
6. As a Calling Agent, I want every Business Outcome marked `retry_same_inputs: never`, so that I do not loop telling a member the same thing repeatedly.
7. As a Calling Agent, I want `VALIDATION_REJECTED` to carry the field and the app's message, so that I can explain precisely what the member must change.
8. As a Calling Agent, I want `Refused` to guarantee nothing was touched, so that I can safely retry after correcting the request.
9. As a Calling Agent, I want `Outcome Unknown` to be distinct from `Failed`, so that I never retry a commit that may already have happened.
10. As a Calling Agent, I want `Aborted` to tell me a person stopped the run, so that I do not treat a deliberate decision as a bug.
11. As a Calling Agent, I want a capability to be refused before it starts when the Tenant has not granted its Role, so that a member is not left waiting on a run that cannot complete.
12. As a Calling Agent, I want invalid inputs rejected against the Contract's patterns before any browser opens, so that mistakes cost nothing.

**Reviewer (engineer at the automation provider)**

13. As a Reviewer, I want to write a goal in natural language and have an LLM propose a Contract I then confirm, so that discovery is directed without hand-writing YAML.
14. As a Reviewer, I want the Contract fixed before discovery, so that inputs and outputs are never inferred from a transcript.
15. As a Reviewer, I want the Recorder to drop wrong turns and keep the successful path, so that the Artifact is the flow and not the history.
16. As a Reviewer, I want every discovery literal replaced by a placeholder in Transitions, Checkpoints and Watchers alike, so that an Artifact recorded on one member replays for another.
17. As a Reviewer, I want a lint that fails when a discovery literal survives anywhere in the Artifact, so that the commonest bug in this problem space cannot ship.
18. As a Reviewer, I want every click to arrive marked Consequential by default, so that I must deliberately downgrade each one to Safe.
19. As a Reviewer, I want the Discovery LLM's risk suggestion shown as advice with its reason, so that I decide faster without the model deciding for me.
20. As a Reviewer, I want interruptions recorded as Watchers rather than Transitions, with a suggestion I confirm, so that replay for a member without the popup still works.
21. As a Reviewer, I want each Watcher to record its **Provenance**, so that a reader can tell what was discovered from what a human assumed.
22. As a Reviewer, I want Needs derived from what the run actually used, and trimmable, so that a wrong turn does not grant permanent access.
23. As a Reviewer, I want approval refused when Needs fall outside the declared Role, so that a capability cannot quietly gain power in a later version.
24. As a Reviewer, I want approval gated on a clean verify-replay with different inputs, so that an Artifact that "runs but doesn't work" is never approved.
25. As a Reviewer, I want an Artifact containing a Consequential Action to need Two-Person Approval, so that risky capabilities match bank change control.
26. As a Reviewer, I want unattended approval refused unless every Consequential Action has a Verification Check, so that no unverifiable commit runs with nobody watching.
27. As a Reviewer, I want to read redacted evidence from any run, so that I can diagnose without seeing member data.
28. As a Reviewer, I want an Unknown State's evidence to contain the predicate expected, what was observed and which Target matched, so that I can turn it into a new Watcher.
29. As a Reviewer, I want adding a Watcher to produce a new Artifact version, so that behaviour changes are reviewable and revertible.
30. As a Reviewer, I want a rising Fallback Match rate for a Tenant surfaced, so that I fix drift before it breaks.

**Operator (staff at the institution)**

31. As an Operator, I want an intervention request carrying the capability, the current state, the reason and a live screenshot, so that I can act without asking what happened.
32. As an Operator, I want to take control of the *same* live session, so that I continue rather than start over.
33. As an Operator, I want the automation unable to act while I hold control, so that we never fight over the screen.
34. As an Operator, I want my actions recorded with my identity and values hidden, so that the audit trail is complete without leaking data.
35. As an Operator, I want Resume to re-check the current Checkpoint and skip the Transition if it already holds, so that my manual work is not repeated.
36. As an Operator, I want an approval prompt before a Consequential Action that shows which Target matched and highlights it, so that I can catch a wrong match before the click.
37. As an Operator, I want Abort to return a distinct Run Result, so that my decision is not recorded as a system failure.
38. As an Operator, I want an unanswered request to time out rather than hold a session open forever.

**Institution (the Tenant)**

39. As a Tenant, I want to own the Policy file for my app, so that the vendor does not grant itself access.
40. As a Tenant, I want to grant Roles individually, so that I can permit lookups but not account opening.
41. As a Tenant, I want each Role bound to my own least-privilege Service Account, so that a read-only capability signs in as a login that cannot move money.
42. As a Tenant, I want automation unable to reach any origin but mine, enforced in the browser, so that a planted link cannot exfiltrate member data.
43. As a Tenant, I want no capability able to exceed the Baseline Policy, whatever is configured, so that "no unverified unattended commit" holds everywhere.
44. As a Tenant, I want a Tenant Overlay to adjust only appearance, never transitions, Contract or permissions, so that a cosmetic fix cannot change behaviour.
45. As a Tenant, I want an Artifact recorded on another institution's instance of the same vendor app to work on mine with a small Overlay, so that capabilities are not rebuilt per institution.

**Member (indirect)**

46. As a Member, I want a mistyped number answered with "check that number", so that I am not told the system is broken.
47. As a Member, I want an answer within seconds on a repeat task, so that the automation is not re-reasoning about the screen each time.
48. As a Member, I want never to end up with two accounts because a retry was unsafe.
49. As a Member, I want my data not sent to a model provider during production runs.

**Operator of the system / graders**

50. As a grader, I want evidence of a real LLM-driven discovery run, so that the core claim is verifiable.
51. As a grader, I want a replay that hits an exceptional state, so that I can see detection and reporting rather than a happy path.
52. As a grader, I want a test proving replay cannot reach the model SDK, so that "no LLM in the loop" is enforced rather than asserted.
53. As a grader, I want to run everything without an API key, so that I can exercise replay without spending money.

## Implementation Decisions

**Surface.** Playwright drives the browser for both discovery and replay, behind one `Surface` seam (`observe`, `resolve`, `act`, `capture`, `hit_test`). Recording under one engine and replaying under another would make a recorded Target a promise about nothing. All Playwright calls live in this module; a test asserts no other module imports it. `observe` returns the accessibility tree *and* a screenshot cropped to the app window and downscaled. `hit_test(x, y)` turns a coordinate click into a recordable Target (role, name, nearby anchor text, frame path, cropped image).

**Artifact shape.** PreAct's structure — `states` (each with a Checkpoint Predicate), `transitions` (each carrying an action and a risk label), `metadata` with parameters — extended with **Watchers as global transitions**, because enterprise interruptions are cross-cutting and, unlike PreAct, we have no model to fall back on. Terminal states carry Outcome Codes. Predicates come from a closed set: `element_present`, `element_absent`, `text_present`, `field_value`, `url_matches`, `count`. Prose lives in a `description` beside a predicate, never instead of one.

**Targets** are ordered ladders: role+name, then position relative to visible text, then picture. Replay records which rung matched; a non-first match is a Fallback Match and is logged. When no rung resolves, the run stops rather than guessing.

**Replay Engine** is an interpreter over a closed action vocabulary (`click`, `type`, `select`, `read`, `wait`, `scroll`); actions outside it have no implementation and so cannot be expressed. Per Transition, in order: Precondition → Policy check → resolve Target → risk gate → act → observe (Checkpoint, then Watchers, then Unknown State handling). Retry budgets are engine defaults, overridable per Transition and visible in review.

**Values.** Three forms on a `type` action: a literal, a `{{placeholder}}` bound to a Contract input, or a `value_ref` naming a Secret resolved from a `SecretProvider` at the keystroke. Secrets never reach the model, the logs or the Artifact. `needs.secrets` is checked at the front door so a missing credential yields `Refused`, not a half-run.

**Permissions** are `Baseline ∩ Role ∩ Tenant grant ∩ Needs`. A Role is a per-vendor-app bundle (pages, actions, whether Consequential Actions are permitted, and the Service Account it signs in as); an Artifact declares exactly one. Route interception aborts any request — including ones the page initiates — to a non-allowlisted origin.

**Result envelope**, one shape with six statuses:

```json
{"status":"succeeded","outputs":{},"evidence_id":""}
{"status":"business_outcome","outcome":{"code":"","resolver":"","caller_hint":"","retry_same_inputs":"never","data":{}},"evidence_id":""}
{"status":"failed","step":"","expected":"","observed":"","evidence_id":""}
{"status":"refused","reason":""}
{"status":"aborted","by":"","at_step":""}
{"status":"outcome_unknown","step":"","guidance":"Do not retry…","evidence_id":""}
```

**Crash safety.** A write-ahead line is appended before and after every action. On restart, a run whose last line is `about_to` on a Consequential Action closes as `Outcome Unknown`. Consequential Actions are never retried, never reloaded after submit, and carry a Verification Check (a Predicate plus where to look) used whenever the outcome is unclear.

**Discovery.** Six endings: `goal_reached`, `report_outcome`, `ask_human`, `give_up` (the model's), `step_limit`/`timeout`, `stuck_detected` (the code's). Runs only against a Non-production Environment, bounded by its Role, with outbound redaction on the observation. A second discovery run on the not-found member ends `report_outcome` and contributes a Business Outcome Watcher — recognition, not route.

**Recorder** produces a draft Artifact: drops wrong turns, collapses retries, replaces example values with placeholders everywhere they were used, builds Target ladders from what was captured at each action, marks every click Consequential, attaches suggestions, derives Needs, and links the discovery run by id without embedding the transcript.

**Handoff.** One control state (`automation → awaiting_operator → operator_in_control → resuming`), a lease so only the holder may act, bounded at two escalations per Transition, resume re-checking the current Checkpoint.

**Target app.** Flask, server-rendered, table layout, no test IDs, full page reloads. Two Service Accounts (read-only, officer). Member numbers select the scenario (normal, not found, not authorized, popup, transient error, session expiry, app error). One unlabelled icon control. `SKIN=bank2` renames and moves controls for the Overlay demo. `/reset` restores state so runs are repeatable.

## Testing Decisions

A good test here exercises **external behaviour through the highest seam** — inputs and an Artifact in, a Run Result and evidence out — against the real Flask app, with no assertions about internal call order. The Flask app is the fixture: scenarios are chosen by member number, so a test is "replay this Artifact for 99999 and expect `business_outcome MEMBER_NOT_FOUND`", not a mock of a browser.

**Primary seam (preferred for nearly everything): `replay(artifact, inputs, context) -> RunResult`** against the live Flask app. Every Condition, Run Result, retry budget, policy layer and risk gate is observable here.

**Second seam: `record(trace) -> draft Artifact`**, a pure function over a recorded trace fixture. Covers placeholder substitution, wrong-turn dropping, Watcher inference, Needs derivation, provenance.

**Third seam: `Surface`**, so a fake surface can drive states that are awkward to produce live (a frozen page, a mid-step crash). Used sparingly — the Flask app can produce most conditions directly.

Tests that are also controls: replay cannot import the model SDK; no module but `Surface` imports Playwright; an Artifact naming an unknown action is rejected by the schema; Needs exceeding Policy yields `Refused` before the browser opens; an Overlay adding a Transition or widening Needs is rejected; a redaction canary never appears in evidence; a Business Outcome is never retried; automation and Operator cannot both hold control; replaying the same inputs five times gives identical results.

No prior art exists — this is a greenfield repo, so these seams set the pattern.

## Out of Scope

Multi-tenant provisioning, queues, clusters and schedulers. A real operator console (a minimal surface stands in). Desktop or Citrix surfaces (the `Surface` seam and the picture rung of each ladder are the design answer). Idempotency keys looked up in the app. Screenshot region masking. Tamper-evident hash chaining of evidence. Network isolation and credential separation as deployed infrastructure. Control-plane/data-plane deployment. Concurrency, latency budgets, artifact storage at scale and evidence retention policy. An LLM fallback at replay time, which is excluded by design, not by time.

## Further Notes

Prior art worth citing in REPORT.md: PreAct (verify-before-act, verify-before-store, and its stated limitation that re-running to verify presumes an idempotent task — which the Verification Check answers), AgentRR (record → summary → replay, check functions, and "Untrusted Model Record, Trusted Model Replay", which is our non-production rule), UiPath's ranked selectors and Computer Vision fallback, OpenAdapt's ladder and "halt instead of guessing", Power Automate's image fallback.

Build order: Flask app → schema and a hand-written Artifact → Replay Engine → safety → real discovery run (early, and budget for it) → Recorder → handoff → Overlay and unlabelled-control demos → evidence, README, REPORT.

Keep `NOTES.md` from the first commit: the bug stories are the report and the interview answers.
