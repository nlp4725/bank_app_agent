# `tests/` reorganisation plan

Companion to [reorg-plan.md](./reorg-plan.md). The package now has one direction of
dependency and a boundary test per seam; the suite that proves it is still fifteen flat
files organised by story. This plan keeps the stories and adds the one thing the layout
does not say today: which tests need the demo app and which do not.

## 1. What is there today

| fact | number |
|---|---|
| tests | 205 in 15 files |
| need no browser and no model | 110, in 1.5 s |
| need the demo app | 95, in about 5 min |
| files that mix the two | 6: `test_safety`, `test_pii`, `test_bugs`, `test_handoff` (by tier); `test_store`, `test_start` are pure but hold tests of two packages |
| test doubles private to one file | 3: a scripted Surface (`test_predicates`), a scripted model (`test_discovery`), verify stand-ins (`test_start`) |
| doc citations of test paths | 7, in REPORT.md, README.md and docs/modules.md |

The fast tier exists, but only someone who knows the eight file names can run it.
`conftest.py` starts the demo app lazily (a session fixture, first use), so a directory
holding no test that asks for it never starts it. That is the whole mechanism.

## 2. Target layout

Two tiers, as directories, one rule: everything under `app/` drives the demo app;
everything else runs in seconds with nothing listening.

```
tests/
  conftest.py            unchanged: the demo app, the artifact, the settings
  support/
    artifact.py          was fixtures.py: the hand-written Artifact and the test Overlay
    doubles.py           ScriptedSurface, Scripted (model), VerifyOk / VerifyBad
  unit/                  no browser, no model
    test_schema.py       test_lint.py        test_locate.py     test_predicates.py
    test_settings.py     test_store.py       test_recorder.py   test_redaction.py
    test_policy.py       test_lease.py       test_recovery.py   test_boundaries.py
    test_discover_cli.py test_start.py
  app/                   against the demo app, never a model
    test_replay.py       test_handoff.py     test_pixels.py     test_safety.py
    test_outcome_unknown.py                  test_discovery.py  test_demos.py
```

Why two tiers and not a folder per package: `unit/` is fourteen files named after the
module each one tests, which is what a reader looks for; seven folders holding one or
two files each would say less. The story files (`safety`, `demos`, `outcome_unknown`)
keep their names inside `app/`, so the report's citations change path, not meaning.

Where each test goes, for the files that split:

| from | to `unit/` | to `app/` |
|---|---|---|
| `test_safety` | `test_boundaries`: the 12 import-graph and seam rules, with `LAYOUT` and the AST helpers; `test_policy`: the 2 layering tests and the `route_of` test | `test_safety`: the 4 front-door refusals, the browser origin gate, the 3 evidence checks |
| `test_pii` | `test_redaction`: the 16 masking, extraction and chokepoint tests | `test_pixels`: the 4 that paint a screenshot or read a page |
| `test_bugs` | `test_policy`: S3 (4) and `origin_for` (1); `test_recovery`: the 3 write-ahead-log tests | `test_safety`: the 2 origin-allowlist runs; `test_outcome_unknown`: the 5 S1 runs and the real-trail test |
| `test_handoff` | `test_lease`: the 2 lease tests | `test_handoff`: the 6 live handoffs |
| `test_store` | `test_store`: the Store and the shipped artifact (11); `test_recorder`: the 2 crop tests | — |

`test_bugs.py` disappears as a file. Its docstring — three defects a review surfaced —
becomes a paragraph in the docstring of each file that inherits its tests, so the
history is not lost.

## 3. Steps

Same discipline as the package: one commit per step, imports updated in the same
commit, doc citations updated in the same commit. A full run before every commit that
changes what a test does; the split commits in step 3 run the files they touch, and
the last one runs everything.

1. **`support/`.** `fixtures.py` → `support/artifact.py`. The three doubles move into
   `support/doubles.py` with public names; the files that owned them import them. Every
   `from .fixtures import` becomes `from tests.support.artifact import`, which is what
   subdirectories will need. Nothing else changes.
2. **The two directories, whole files only.** Pure files move to `unit/`; files that need
   the app, mixed or not, move to `app/`. Update the seven doc citations. After this
   commit `pytest tests/unit` runs 92 tests in about two seconds with nothing listening;
   the rest of the fast tier is still inside the mixed files in `app/`.
3. **Split the mixed files**, one commit each, in the order of the table above:
   `test_safety`, `test_pii`, `test_bugs`, `test_handoff`, `test_store`. Each commit
   moves tests verbatim, carries the helpers they use, and leaves a docstring that says
   where the rest went.
4. **Keep the tier honest.** A test in `unit/test_boundaries.py` scans `tests/unit` and
   fails if any test there asks for `bank_app`, `bank2_app` or `approved`. A
   `pytest_collection_modifyitems` hook in `conftest.py` marks everything under `app/`
   with `app`, registered in `pyproject.toml`, so `-m "not app"` works for anyone who
   prefers markers to paths. README and docs/modules.md name the two commands.

## 4. Order of risk

| step | kind | can break | proof |
|---|---|---|---|
| 1 | move + rename | imports | full run |
| 2 | move | imports, relative paths to `evidence/` | full run; `pytest tests/unit` starts no app |
| 3 | split | a test losing a helper or a constant | the touched files, then a full run after the last split |
| 4 | tooling | nothing at run time | `pytest tests/unit`, `pytest -m "not app"`, both without the app |

## 5. Status (2026-09-24)

Done, one commit per step, each after a green run (full runs at steps 1, 2 and the end
of 3; the touched files for each split).

| step | commits | result |
|---|---|---|
| 1 | `85ded19` | `tests/support/`: the Artifact and the three doubles |
| 2 | `5e57858` | `unit/` and `app/`, whole files |
| 3 | `709c1f2` `01d2b74` `5b72df4` `b08a9e9` `3129e09` | safety, pii, bugs, handoff, store split; `test_bugs.py` retired |
| 4 | (this commit) | the tier guard in `unit/test_boundaries.py`; the `app` marker from `conftest.py` |

| command | tests | time | demo app |
|---|---|---|---|
| `pytest tests/unit` | 157 | under 2 s | never started |
| `pytest -m "not app"` | 157 | under 2 s | never started |
| `pytest tests/app` | 49 | about 5 min | started once, on first use |
| `pytest` | 206 | about 5 min 20 s | started once |

The marker is registered from `conftest.py` rather than `pyproject.toml` because another
session held uncommitted changes to that file at the time.

## 6. Mirror the package, so an outsider can test a module by path

Requested after step 4: a test file must be findable from the module it tests without
a table. The rule, enforced by a test in `unit/test_boundaries.py`:

    tests/<tier>/<package>/test_<module>.py          the tests of cua/<package>/<module>.py
    tests/<tier>/<package>/test_<module>_<story>.py  a second file about the same module
    tests/<tier>/test_<module>.py                    a top-level module (settings, secrets)
    tests/unit/test_boundaries.py                    the one file about the package as a whole
    tests/<tier>/tools/...                           the same rule, over tools/

So `pytest tests/unit/authoring/test_lint.py` is the lint module, `pytest tests/unit/replay`
is the replay package, and `pytest tests/unit/replay tests/app/replay` is everything
about it. Names that said what a file was about rather than what it tested go away:
`test_schema` → `domain/test_artifact`, `test_lease` → `replay/test_handoff`,
`test_redaction` → `evidence/test_redact`, `test_pixels` → `evidence/test_redact` (app),
`test_safety` → `governance/test_policy` (app), `test_demos` → `surface/test_locate` (B1)
and `governance/test_overlay` (B2), `test_outcome_unknown` → `replay/test_engine_outcome_unknown`.

Tests that sat in the wrong file because of a story move to the module they exercise:
the three `merged()` tests from lint to `domain/test_artifact`; the overlay lint tests
to `governance/test_overlay`; the profile-data tests to `governance/test_profile`; the
two writer tests to `evidence/test_writer`; the narration test to `replay/test_narration`;
the four `spec_from_proposal` tests to `discovery/test_propose`; the source-inspection
test of the crop rule to `discovery/test_run`; the secrets tests to `test_secrets`.

Three commits: the unit tier (verified by `pytest tests/unit`, seconds), the app tier
(verified by the full run), then the guard test and the doc citations.
