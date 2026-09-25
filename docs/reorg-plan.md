# `cua/` reorganisation plan

Goal: turn the flat `cua/` package into a small set of subpackages with one direction of
dependency, so a reader can find "where does X happen" from the directory listing, and so
each concern can be tested without the ones below it. Every step below is one commit that
leaves the whole suite green. Moves and splits are never mixed in one commit.

## 1. What is there today

Fourteen modules at the package root, three lifecycles mixed together:

| lifecycle | modules today | who imports them |
|---|---|---|
| production replay (no model) | `engine`, `predicates`, `handoff`, `narration` | `tools/replay`, `tools/demo_*`, `tools/make_evidence`, tests |
| authoring (draft → approved) | `recorder`, `review`, `lint`, `overlay` | `tools/record`, `tools/review`, `discovery`, `engine` (overlay) |
| model in the loop | `discovery` (570 lines: prompts, tool schemas, the turn loop, the proposal, draft compilation) | `tools/discover`, `tools/start` |
| the browser seam | `surface` (471 lines: driver wiring, rung ladder geometry, enumeration, two interfaces) | `engine`, `predicates`, `discovery`, tools |
| cross-cutting | `evidence`, `redact`, `secrets`, `paths` | everything |
| already packaged | `domain/` (pure), `governance/` (YAML readers) | everything |

Concrete problems, in order of how much they hurt:

1. **Lazy imports hide cycles.** `redact.for_app` imports `governance.profile` inside the
   function; `engine.replay` imports `overlay` inside the function; `discovery` imports
   `recorder`, `Contract`, `list_roles`, `yaml`, `base64` inside functions. Each one is a
   dependency that the import graph test cannot see and that will surface as an
   `ImportError` the moment a file moves.
2. **The model SDK and the turn loop are one module.** `discovery.discover` calls
   `client.messages.create` directly, so the loop (policy check, control lookup, stuck
   detection, six endings) cannot be tested without the API. The proposal step, which
   needs no browser, sits in the same file.
3. **`surface.py` holds four things.** Launching and hardening the browser, the rung
   ladder (pure geometry over bounding boxes), enumeration for discovery, and the two
   interfaces. The geometry is the part most likely to need tuning and the part least
   tested, because it is only reachable through a live page.
4. **Seams are untyped.** `RunContext.secrets`, `.operator`, `.narrator` and the surface
   passed to `Run` are `object`. Nothing states what a scripted Surface must provide,
   so the boundary tests do it by scanning attribute names.
5. **Repo-relative configuration.** `paths.ROOT` is computed from `__file__`, every
   loader is an `lru_cache` over a module constant, and `secrets.DEMO_ACCOUNTS` is baked
   into the only provider. Installed as a wheel, the package finds no config and ships
   demo credentials.
6. **Library code lives in `tools/`.** `request_from_spec`, `load_dotenv`, `report` in
   `tools/discover.py` are imported by `tools/start.py` and tested by two test modules.
7. **No public API.** `cua/__init__.py` is empty; callers import from ten modules.

## 2. Target layout

```
cua/
  __init__.py            empty on purpose (see "runtime rule" below)
  settings.py            was paths.py; data directories, overridable from the environment
  secrets.py             SecretsProvider protocol, EnvSecrets, DemoSecrets
  domain/                pure: artifact schema, result, placeholders, issue, rules
    rules.py             covers(), route_of(), validate_inputs()  — no I/O, no clock
  governance/            the only readers of config YAML
    roles.py profile.py policy.py store.py overlay.py
  evidence/              the one channel every log line, image and result leaves through
    writer.py            EvidenceWriter
    redact.py            patterns, mask_value, Redactor  (imports nothing from cua)
    recovery.py          unfinished()
  surface/               the only importer of playwright
    driver.py            Surface: launch, hardening, request gate, wait, goto, act
    locate.py            the rung ladder and the anchor geometry, as functions over a scope
    enumerate.py         controls(), values(), nearest_text(), describe(), crop()
    recording.py         RecordingSurface
  replay/                production path; reaches nothing that imports a model SDK
    context.py           RunContext and the Protocols for its seams
    engine.py            replay(), Run
    predicates.py handoff.py narration.py
  authoring/             draft → approved; no browser, no model
    lint.py recorder.py review.py
  discovery/             the only importer of a model SDK
    request.py           DiscoveryRequest, DiscoveryResult, request_from_spec
    model.py             prompts, tool schemas, the SDK adapter (the one anthropic import)
    run.py               discover(): observe → decide → act
    propose.py           propose_contract(), spec_from_proposal()
```

Dependency direction, top to bottom. A package may import from any row below it and
never from its own row's neighbours or above:

```
discovery ──► authoring ──► replay? no: authoring uses replay only through the `verify`
   │             │            callback that tools/review passes in
   │             ▼
   ├──────► governance ──► domain
   ├──────► evidence   ──► domain
   ├──────► surface    ──► domain
   └──────► secrets, settings
replay ───► governance, evidence, surface, secrets, domain
```

Runtime rule, not just a static one: `import cua.replay.engine` must not execute an
`anthropic` import. So `cua/__init__.py` stays empty and each package's `__init__` is the
front door: `cua.replay` exports `replay`, `RunContext`, `RunResult`; `cua.discovery`
exports `discover`, `propose_contract`, `DiscoveryRequest`. Callers import two names.

What deliberately stays where it is: `domain/` and `governance/` (already right),
`handoff` and `narration` inside `replay/` rather than their own packages (one caller
each), `tools/` as thin scripts (they become thinner, not fewer).

## 3. Steps

Every step has the same shape:

1. `git mv` or edit.
2. One `sed`/`grep` pass over `cua/ tools/ tests/ docs/ REPORT.md` for the old dotted path.
   No compatibility shims: they would make the boundary test's `LAYOUT` rows ambiguous.
3. Update the matching row of `LAYOUT` in `tests/app/test_safety.py` and the row of
   `docs/modules.md` in the same commit.
4. `python -m pytest -q` (the suite owns the demo app; nothing else may be on 5099/5100).
5. `python -X importtime -c 'import cua.replay.engine' 2>&1 | grep -c anthropic` prints
   `0` (from step 5 on, once the package exists; before that use `cua.engine`).
6. Commit.

### Step 0 — freeze the baseline
The working tree already holds the `domain/` + `governance/` move, uncommitted, and a
second change in flight: `contract.outcomes` → `contract.business_outcomes` across the
schema, tests, tools, artifacts and contracts. Finish that rename first, then run the
suite and commit. The full run on 2026-09-24 (180 passed, 6 failed, 5m54s) showed:

- `tests/unit/test_start.py` × 3: `KeyError: 'business_outcomes'` at `tools/start.py:351`,
  which still reads `draft["contract"]["outcomes"]` and appends to `keep_outcomes`.
  That is the rename, not yet applied to this file.
- `tests/unit/test_store.py::test_a_run_compiled_after_it_moved_still_finds_its_crops`:
  `evidence/01-discovery-goal-reached/screens/` holds `01.png…` but no `NN_target.png`
  crops, while its `actions.json` names them. Pre-existing data problem: either
  re-record that evidence run or relax the test to the runs that do carry crops.
- `tests/app/test_replay.py` × 2 (`transient_error_is_retried`,
  `expired_session_is_signed_into_again`): fail in the full run, pass when run alone.
  Order-dependent, almost certainly the fire-once scenarios in the demo app that
  `conftest.py` warns about. Worth pinning down before the moves, because a flaky
  pair makes "the suite is green after this step" impossible to read.

Everything after this is measured against a green run of that tree.

### Step 1 — make the import graph honest (no moves)
- `redact.for_app` → `governance/profile.py` as `redactor_for(vendor_app, **flags)`.
  `redact.py` then imports only `re`. Callers: `engine`, `discovery`, `tests/test_pii`.
- `engine.replay`: the in-function `from .overlay import …` becomes a module import.
- `discovery`: `recorder`, `Contract`, `list_roles`, `yaml`, `base64` become module imports.
- Add one test: no `import` statement inside a function body anywhere in `cua/`
  (`ast.walk`, same style as the existing boundary tests). It is what keeps step 1 done.

Why first: every later move is mechanical only if the graph is a DAG at module level.

### Step 2 — `evidence/` (move only)
`evidence.py` → `evidence/writer.py`; `redact.py` → `evidence/redact.py`; `unfinished`
→ `evidence/recovery.py`. `evidence/__init__.py` re-exports `EvidenceWriter`,
`Redactor`, `unfinished`, `HIDDEN`, `PROTECTED`, `mask_value`, `redact_text`.
No LAYOUT row changes. Smallest move, proves the mechanics.

### Step 3 — `surface/` (move, then split)
- 3a: `surface.py` → `surface/driver.py`; `__init__` re-exports `Surface`,
  `RecordingSurface`, `Resolved`. `LAYOUT["surface"] = ["surface"]`.
- 3b: pull `RecordingSurface` into `surface/recording.py`.
- 3c: pull `_try_rung`, `_by_anchor` and the scoring into `surface/locate.py` as
  functions taking a scope and a rung; `Surface.resolve` becomes the polling loop
  around them. Pull `controls`, `values`, `nearest_text`, `describe`, `crop` into
  `surface/enumerate.py` the same way. The tests
  `test_the_recording_interface_does_not_offer_the_acting_one` and
  `test_a_locator_never_leaves_the_surface` keep passing unchanged because the
  package is still "the surface".
- The geometry in `locate.py` takes bounding boxes, so add a handful of unit tests for
  `right_of` / `below` / `nearest` scoring with literal boxes — the first tests of that
  logic that need no browser.

### Step 4 — `authoring/` and `governance/overlay.py` (move only)
`overlay.py` → `governance/overlay.py` (it is a rule about tenant-owned data, and the
engine applies it at run time, so it belongs below `replay`, not beside `review`).
`lint.py`, `recorder.py`, `review.py` → `authoring/`. `recorder` keeps importing
`settings.ASSETS`/`ROOT`. `discovery` now imports `authoring.recorder` at module level.

### Step 5 — `replay/` (move, then one extraction)
- 5a: `engine.py`, `predicates.py`, `handoff.py`, `narration.py` → `replay/`.
  `LAYOUT["replay_entry"] = "replay/engine.py"`, `LAYOUT["predicates"] =
  "replay/predicates.py"`. `replay/__init__.py` exports `replay`, `RunContext`,
  `RunResult`, `Silent`, `Console`, `from_env`. Tools and tests switch to
  `from cua.replay import …`.
- 5b: `RunContext` → `replay/context.py`, together with four `typing.Protocol`s:
  `ActingSurface` (the `ACTING` set from the boundary test, as a type),
  `SecretsProvider` (`get`), `Operator` (`__call__(intervention, surface) -> str`),
  `Narrator` (`slow_mo_ms`, `transition`, `linger`). `RunContext` fields lose their
  `object | None` annotations. The `ACTING` set in the test is then derived from the
  Protocol rather than duplicated.
- 5c (optional, same package): `validate_inputs` → `domain/rules.py` beside `covers`
  and `route_of`, which also move there from `governance.roles` / `governance.policy`
  (both are pure). `governance` re-exports them so no caller changes.

### Step 6 — `discovery/` (move, then split)
- 6a: `discovery.py` → `discovery/run.py`; `__init__` re-exports; `LAYOUT["discovery"]
  = ["discovery"]`.
- 6b: `DiscoveryRequest`, `DiscoveryResult`, `policy_for_request` → `request.py`.
  `ProposalError`, `PROPOSE_SYSTEM`, `propose_tool`, `spec_from_proposal`,
  `propose_contract` → `propose.py`.
- 6c: `SYSTEM`, `tools()`, and a small `Model` class wrapping `anthropic.Anthropic`
  with two methods, `next_action(messages, tools) -> (call, extras)` and
  `propose(...)`, → `model.py`. `run.py` takes the model from
  `DiscoveryRequest.model` (default: the real one) and never mentions the SDK.
  `test_the_model_sdk_lives_only_in_discovery` narrows to `["discovery/model.py"]`.
  This is the step that lets the loop be tested with a scripted model: add one such
  test (policy deny → `give_up` after three, and `report_outcome`).
- 6d: `request_from_spec` (and its validation) from `tools/discover.py` →
  `discovery/request.py`; `load_dotenv` stays a CLI concern but moves to a tiny
  `tools/_env.py` so `tools/start.py` stops importing `tools/discover.py` for it.

### Step 7 — `settings.py` and secrets (behaviour change, small)
- `paths.py` → `settings.py`. `ROOT` defaults to the repo as today but honours
  `CUA_ROOT`; the five directory constants become attributes of a `Settings`
  instance built once at import. Loaders keep `lru_cache`; add `governance.reset()`
  that clears them, for tests that point at another root.
- `secrets.py`: `EnvSecrets` reads the environment only. `DemoSecrets` holds
  `DEMO_ACCOUNTS`. `replay()` and `discover()` pick the provider from
  `settings.secrets_provider` (env `CUA_SECRETS=demo|env`, default `env`);
  `tests/conftest.py` sets `demo`. This is the one step where a test can fail for a
  reason other than an import path, so it is last among the code steps.

### Step 8 — finishing (each its own commit, any order)
- One `CuaError` base in `domain/issue.py`; `PolicyError`, `UnknownRole`,
  `UnknownProfile`, `UnknownCapability`, `MissingSecret`, `ProposalError`,
  `ControlError` subclass it. Tools catch one type at the top.
- `discovery._say` and `narration.Console` print → `logging` with a `cua.*` logger;
  tools configure the handler.
- `pyproject.toml`: `[project]` metadata, `cua` as the package, `ruff` and `mypy`
  config, console entry points for `tools/replay`, `tools/discover`, `tools/start`.
  `mypy --strict cua/domain cua/replay` is the first target; the Protocols from 5b are
  what make it pass.
- `docs/modules.md` regrouped by package; `docs/figures/make_architecture.py` labels
  checked against the new paths.

## 4. Order of risk

| step | kind | can break | what proves it did not |
|---|---|---|---|
| 0 | commit | nothing | suite green |
| 1 | edit | import order | new "no lazy import" test + suite |
| 2 | move | import paths | suite |
| 3a, 4, 5a, 6a | move | import paths, LAYOUT rows | suite; `test_the_layout_names_files_that_exist` |
| 3b, 3c, 5b, 6b, 6c | split | behaviour of extracted code | suite + the new unit tests each split adds |
| 5c | move of pure functions | nothing | suite |
| 6d | move out of tools | `test_start`, `test_discover_cli` | those two files |
| 7 | behaviour | secret resolution, config root | suite with `CUA_SECRETS=demo`; one test with `CUA_ROOT` at a tmp copy |
| 8 | tooling | nothing at run time | ruff/mypy clean, suite |

Stop after any step and the tree is still coherent. Steps 2–6a can be done in one
sitting; each is ten minutes of moving and a test run.

## 5. Status (2026-09-24)

Every step below was done as one or more commits on `main`, each after a green full run.
The suite went from 186 tests to 205; ruff and mypy (over `cua.domain` and `cua.replay`)
are clean.

| step | commits | notes |
|---|---|---|
| 0 | `76045e9` | governance move committed as found; the five click crops 8f9c92e dropped restored |
| 1 | `b7620ab` | `redactor_for` in governance.profile; no imports inside functions, and a test that says so |
| 2 | `80c4563` | `evidence/` |
| 3 | `5e6eebb` `71924d3` `56ecbbc` | `surface/`; `locate.score` over boxes, with the first browser-free tests of it |
| 4 | `c3602f6` | `authoring/`, overlay into `governance/` |
| 5 | `81b3815` `008f8be` `07c89b9` | `replay/`; Protocols in `replay/context.py`; `domain/rules.py` |
| 6 | `9ed5a0a` `af8341c` `1c4cf78` `2d43baf` | `discovery/`; the SDK behind `discovery/model.py`; four scripted-model tests of the loop; `request_from_spec` out of the CLI |
| 7 | `e86ba3a` | `settings.py` with `CUA_ROOT` / `CUA_SECRETS`; loaders read it at call time; `EnvSecrets` strict, `DemoSecrets` separate |
| 8 | `ea501a9` | `CuaError`; `pyproject.toml` with entry points, ruff and mypy |

Left as is, on purpose: the two `print` calls (`narration.Console` and discovery's
`verbose`) are the "someone is watching" channel, not logging; and `docs/modules.md`
was updated row by row rather than regrouped.
