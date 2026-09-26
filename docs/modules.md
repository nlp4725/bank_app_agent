# Modules

Every module, in the order the data flows through it, with what goes in and what comes
out. `cua/` is the system; `tools/` are entry points that only wire it together;
`fake_bank/` is the target. Nothing in `cua/` imports from `tools/`. Examples are the
demo's real values. Vocabulary: [CONTEXT.md](../CONTEXT.md).

| Module | In → Out (example) | Does |
|---|---|---|
| **discovery** — once per capability, model in the loop | | |
| `cua/discovery/` — `model.py` · `run.py` · `propose.py` · `request.py` | `propose_contract("read a member's savings balance")` → `{role: balance_reader, contract: {inputs: {member_number…}, outputs: {savings_balance: money}, outcomes: […]}}` ; `discover(DiscoveryRequest(goal, contract, role, origin))` → `DiscoveryResult(ending=goal_reached, outputs={savings_balance: "$4210.00"}, draft=runs/disc_x/draft.yaml)` + `trail.jsonl` | the only package where a model is in the loop: `model` is the one SDK adapter (a scripted stand-in drives the loop in tests); `propose` proposes a Contract + Role from a goal; `run` is observe → decide → act, one policy-checked action per turn |
| `cua/authoring/recorder.py` | `actions.json` (13 recorded actions: url, action, target ladder, value) + contract + example values → draft dict: 14 states, 13 transitions, `{{member_number}}` where `54321` was typed; plus suggestions (`"action 6 clicks 'OK' on /members, a page visited once…"`) | turns a run into a draft Artifact — one State + one Checkpoint per step; decides nothing |
| `cua/authoring/review.py` | `apply_decisions(draft, decisions.yaml)` → candidate (4 clicks now safe, `t_ok` → `w_system_notice`, 2 watchers added, `VALIDATION_REJECTED` dropped) ; `approve(candidate, verify)` → `(Artifact status=approved, [])` or `(None, ["[consequential_without_verification] …"])` | applies a Reviewer's decisions mechanically; approves only if lint passes and a model-free verify-replay succeeds |
| `cua/authoring/lint.py` | `lint(artifact)` → `[Issue(code="unreachable_outcome", where="contract", detail="'NO_SAVINGS_ACCOUNT' is declared but no watcher can produce it")]` or `[]` | what a well-formed Artifact must also satisfy before it can be trusted |
| **the artifact** | | |
| `cua/domain/rules.py` | `covers(["/members/*"], "/members/12345")` → `True` ; `route_of("http://bank/members/1?x=2", "http://bank")` → `/members/1?x=2`, and a URL under another origin is returned whole so it fails the allowlist ; `validate_inputs(artifact, {member_number: "12"})` → `"input 'member_number' does not match ^[0-9]{5}$"` | the rules more than one package asks: no file, browser or clock |
| `cua/domain/artifact.py` | `Artifact.model_validate(yaml)` → typed `Artifact`, or `ValidationError: transitions.3.action.type … 'hover' is not one of click/type/select/read` | the schema — a closed vocabulary; an unknown key or action is rejected |
| `cua/governance/store.py` | `load_capability("member.open_sub_account")` → the `1.0.0` approved Artifact with its App Profile merged (7 watchers); `artifacts()` → every file on disk, for `--list` | which Artifact is live: the highest approved version of a capability id |
| `cua/governance/profile.py` · `cua/governance/overlay.py` | `load_profile("demo-core-servicing")` → shared watchers (`w_session_expired`…), readable/sensitive regions ; `apply_overlay(artifact, overlays/lakeside.yaml)` → same flow, `t_member_field` now found by caption "Find member by #"; an overlay adding a transition → refused | per-app knowledge shared by every capability; per-tenant appearance, never behaviour |
| **production** — every invocation, no model | | |
| `cua/governance/policy.py` · `cua/governance/roles.py` | `policy_for(artifact, "bank_b").refuse_reason(artifact)` → `"tenant 'bank_b' does not grant role 'account_opener'"` ; for `bank_a` → `None` ; `allows_page("/admin")` → `False` | permissions as an intersection: Baseline ∩ Role ∩ Tenant grant ∩ Needs; refused before the browser opens |
| `cua/replay/engine.py` | `replay(artifact, {member_number: "12345", …}, RunContext(origin))` → `RunResult(status=succeeded, outputs={savings_balance: "$4210.00", new_account_number: "SA-2001"})` ; member `99999` → `RunResult(status=business_outcome, outcome={code: MEMBER_NOT_FOUND, resolver: member, retry_same_inputs: never})` ; `33333` → `RunResult(status=failed, reason=unknown_state, step=s13_members_id, verified_effect=False)` | the Replay Engine: checkpoint → resolve → policy → act → checkpoint; Watchers on a miss; recovery budgets; escalation; the Verification Check |
| `cua/replay/predicates.py` | `holds({type: field_value, target: t_member_number, non_empty: true})` → `True`/`False` ; `holds({type: text_present, value: "No records found"}, timeout_ms=0)` → `True` on the not-found screen | evaluates the four predicates against a Surface, placeholders rendered from the run's inputs |
| `cua/surface/` — `driver.py` · `locate.py` · `screen.py` · `recording.py` | `resolve(t_member_number_button)` → `Resolved(locator, matched_by="label_anchor", rung_index=0)` or `None` ; `controls()` → `[{index: 2, role: "textbox", name: "", anchor: "User ID", is_password: False, frame_url: …}, …]` ; `text()` → all visible text, frames included | the only package that touches a browser: `driver` launches, gates and acts; `locate` is the rung ladder and its geometry; `screen` enumerates controls and values for discovery; `recording` is the record-time interface |
| `cua/replay/handoff.py` | `Control.move(AWAITING_OPERATOR, "operator")` → lease held by operator, or `ControlError("cannot move from automation to resuming")` ; `Intervention(...).write(dir)` → `intervention.json` ; `wait_for_decision(dir, 120s)` → `("resume", "operator:jane")` / `("resume", "auto:blocker cleared")` / `("timeout", "")` ; `open_requests(runs/)` → `[runs/run_x/intervention.json]`, only requests a live run is still waiting on | control transfer as a lease: one holder at a time, the same live session |
| `cua/domain/result.py` | the dataclass every run returns: `status` ∈ {succeeded, business_outcome, failed, refused, aborted, outcome_unknown}, `outputs`, `outcome`, `reason`, `step`, `expected`, `observed`, `verified_effect`, `evidence_id` | the result contract: one shape, six statuses |
| **cross-cutting** | | |
| `cua/settings.py` · `cua/secrets.py` | `Settings.from_env({"CUA_ROOT": "/srv/cua"})` → every directory under `/srv/cua`; `secrets_for("svc_read").get("login_password")` → the `SECRET_SVC_READ_LOGIN_PASSWORD` variable, or `MissingSecret`; the demo accounts only with `CUA_SECRETS=demo`, the default beside the demo app | where the data lives and which secrets resolve, read from the environment once; loaders read `settings` at call time |
| `cua/evidence/redact.py` | `redact_text("SSN 123-45-6789, $4,210.00")` → `"SSN [ssn], $*,***.**"` ; `value(anchor="Member name", raw="Alex Rivera")` → `"(hidden)"` (not a Readable Region) ; `value(anchor="Savings balance", raw="$4210.00")` → `"$*,***.**"` ; a password → `"(protected)"` | the Redaction Chokepoint: structural, origin, pattern and pixel layers, for the model and the evidence alike |
| `cua/evidence/writer.py` | `event(run_id, "about_to", step=s12_members_id, action=click, target=t_continue, risk=consequential)` → one masked line in `runs/run_x/trail.jsonl` ; `snap(surface)` → `screen_1.png` with Sensitive Regions black ; `unfinished("runs")` → runs that died mid-commit | every log line, screenshot and result passes through here; write-ahead line before a commit |
| `cua/replay/narration.py` | `transition(t, found)` → `s5_member_number_entered -> s7_members_id  click t_member_number_button  rung=label_anchor risk=safe` on the console; `Silent` → nothing | how a run looks to a person watching it, and nothing else |
| **entry points** (`tools/`, one package per stage) | | |
| `tools/start.py` | a goal typed at the prompt → `contracts/read_savings_balance.yaml` → a headed discovery → `artifacts/read_savings_balance.decisions.yaml` → `artifacts/read_savings_balance.1.0.0.yaml` (approved) → a watched replay | the front door: both reviews in one sitting; only the conversation lives here |
| `tools/discovery/` — `contract.py` · `cli.py` · `smoke_llm.py` | `show(spec)` → the Contract as the Reviewer reads it, `ask_values` → values checked against its rules, `save` → `contracts/x.yaml` ; `--contract contracts/x.yaml --values member_number=12345` → `runs/disc_x/` ; a key → one tool call and a token count | the first review, and the Discovery Request from flags |
| `tools/authoring/` — `walkthrough.py` · `interview.py` · `review.py` · `record.py` · `approve.py` | `show_draft` → one block per step ; `decide` → the decisions file ; `review_artifact` → apply, verify-replay on an unseen member, save ; `record runs/disc_x` → `artifacts/x.draft.yaml` ; `approve runs/disc_x` → `artifacts/x.1.0.0.yaml` or `REFUSED: …` | the second review, interactive (from `start`) or scripted (one stage each) |
| `tools/replay/` — `run.py` · `cli.py` · `make_evidence.py` | `12345 -c member.read_savings_balance` → `RESULT succeeded  OUTPUTS {'savings_balance': '$4210.00'}` ; `--list` → the catalog ; the approved artifact → `evidence/03…07/` | invoke an approved capability by name with typed inputs; regenerate the evidence |
| `tools/operator/` — `console.py` · `web.py` | `runs/run_x/intervention.json` → printed request / a web page ; `resume` → `runs/run_x/decision.json` | the Operator's side of a handoff |
| `tools/demos/` — `b1.py` · `b2.py` | → the unlabelled search icon found by caption ; → one artifact at two institutions, with and without its overlay | the two demonstrations |
| `tools/inspect/` — `show_run.py` · `a11y_dump.py` | a run dir → its turns as a story ; a URL → the numbered control list the model sees | read a run; see what the browser can name |
| `tools/_cli.py` | `.env` → the one key into the environment ; a Discovery Result → printed ; an origin → `/reset`, or a plain message that the demo app is not running | what the tools share and the package does not need |
| **the target** | | |
| `fake_bank/app.py` · `fake_bank/data.py` | `POST /members {member: 88888}` → the login page with "Your session has expired" (once) ; `44444` → the supervisor screen ; `99999` → "No records found" ; `GET /reset` → seed data restored | the hostile stand-in: one scenario per member number |
| **tests** (`tests/`) | 216 tests; the demo app is the fixture, reset before each; `test_safety` also asserts the import graph (no model SDK reachable from replay; Playwright only in `surface.py`) | one file per concern |
| **data, not code** — the folders the modules read and write | | |
| `config/baseline.yaml` | ours, provider-wide: `actions_allowed: [click, type, select, read]`, denied route keywords, hard rules (`secrets_never_sent_to_a_model`, `max_actions_per_run: 60`) | the floor every Tenant may narrow, never widen |
| `config/roles/<app>.yaml` | per vendor app, before any discovery: `balance_reader` (pages, actions, secrets, `consequential: forbidden`, `service_account: svc_read`) … | what a goal may touch |
| `config/policies/<tenant>.<app>.yaml` | the institution's file: `origin`, `environment: non_production`, `roles_granted: {account_opener: {service_account: svc_officer}}`, optional page narrowing | who may run what, where; `bank_b` grants no `account_opener` → `refused` |
| `config/profiles/<app>.yaml` | the App Profile: shared watchers (`w_session_expired`…), `readable_regions`, `sensitive_regions`, `readable_anchors`, `sensitive_text` | what every capability on this app knows, and what may be seen |
| `overlays/<tenant>.yaml` | `lakeside.yaml`: `t_member_field` found by caption "Find member by #", the search icon `nearest` rather than `right_of` | one artifact, a second institution; appearance only |
| `contracts/<name>.yaml` | a Discovery Request: goal in words, Role, Contract, example values | what a Reviewer approved before the run (review #1) |
| `artifacts/` | `<name>.draft.yaml` (as recorded) · `<name>.decisions.yaml` (what the Reviewer answered) · `<name>.1.0.0.yaml` (approved: the only thing that replays) · `assets/<capability>/NN_target.png` (crops of *clicked* controls, never of values) | the capability, and its review trail |
| `evidence/` | `01`, `02`: real discovery runs, as recorded · `03`–`07`: five replays regenerated by `make_evidence` · `artifact/`: the approved artifact, its draft and decisions | the deliverable a reader can check without running anything |
| `runs/<id>/` (gitignored) | `trail.jsonl`, `screens/`, `actions.json`, `draft.yaml`, `intervention.json`, `decision.json` | every run's masked record; the figures and evidence are copies of these |
| `docs/` | `error-taxonomy.md` (the four Conditions, six Run Results) · `security-model.md` (controls built, limits) · `targeting.md` (the rung ladder) · `evaluation.md` · `adr/0001–0007` (one decision each) · `figures/make_*.py` → the three SVGs in this report, generated from the artifacts and from live replays | the reasoning, kept where the code can't drift from it |
| `fake_bank/templates/` | `login`, `search`, `member` (+ `panel` in an iframe), `subaccount_*`, `approval_required`, `not_authorized`, `app_error`, `notice`, `leaky` | one screen per Condition the taxonomy names |

## By package

The same modules grouped the way the tree is laid out, one table per package under `cua/`.
Each package imports only from those listed after the arrow, and `domain` imports from
nothing else in `cua`:

```
domain  ←  evidence, surface, governance  ←  replay  ←  authoring  ←  discovery
```

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
| `locate.py` | The rung ladder: `role_name` asks the accessibility tree, `label_anchor` finds the caption and the nearest control by geometry, `picture` falls through. Records which rung won. See [docs/targeting.md](../docs/targeting.md). |
| `screen.py` | Record-time enumeration for discovery: every control a person could act on, every label/value pair, and the durable description of what was acted on. Also the target crop. |
| `recording.py` | The record-time interface. It cannot resolve or act on a Target; a boundary test says so. |

**`replay/`** — the production path. `replay()` is the front door.

| Module | What it does |
|---|---|
| `engine.py` | The Replay Engine and the `Run`: per Transition, checkpoint → resolve → policy → act → checkpoint; Watchers on a miss; bounded recovery; escalation; the Verification Check after a Consequential Action. Every guarantee in [REPORT.md](../REPORT.md) is enforced here. |
| `predicates.py` | The four Predicates plus `all`/`any`: rendering placeholders, Target lookup, evaluation against a Surface. Adding a Predicate means editing `artifact.py` and one case here. |
| `handoff.py` | Control transfer as a lease: one holder of the live session at a time (`automation → awaiting_operator → operator_in_control → resuming`). Writes the intervention file and waits for the decision. Reads a run's trail to say whether its request is still waiting, so a console never offers a finished run's. |
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
