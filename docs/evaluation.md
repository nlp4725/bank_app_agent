# How discovery is evaluated

The task is fixed by the brief, so tasks cannot be held out the way a benchmark would.
Three axes can be, and all three are real.

| Axis | Discovery sees | Replay is evaluated on |
|---|---|---|
| **inputs** | member 54321 | 12345, 22222, 66666, 77777, 88888, 99999 |
| **tenant** | bank1 | **bank2** — renamed controls, moved icon, different skin, plus an Overlay |
| **conditions** | the interstitial it lived through, and the not-found screen from a second run | session expiry, slow load, transient error, and one condition held out entirely |

## The two ground truths, both written before any model runs

1. **The scenario table** — member number to expected Run Result, a property of the app.
2. **The hand-written Artifact** (`tests/fixtures.py`) — a known-good flow for this app,
   against which the Replay Engine is built with no model involved.

## What a discovered Artifact is scored on

**Behavioural, and this is the criterion:** does the discovered Artifact pass the same
scenario suite the hand-written one passes? A different route that replays correctly on
every scenario is a success, not a deviation. This is PreAct's verify-before-store gate,
which their measurements show is what separates a corpus that improves from one that
decays.

**Structural, reported but never scored:** a diff against the hand-written Artifact —
number of states, wasted actions during discovery, whether the unlabelled control was
found and by which rung, which Watchers were learnt, whether the risk suggestion was
right. Scoring structural identity would measure the wrong thing: it would penalise a
better route for not being mine.

## The held-out condition

`MAX_ACCOUNTS_REACHED` is deliberately **absent** from the Artifact and its Contract.
Member 33333 already holds the maximum, so replaying it must produce an **Unknown State**
— escalate when attended, fail when unattended — rather than a wrong answer. A Reviewer
then adds the Watcher and the Outcome Code, the version becomes 1.1.0, and the same
replay passes.

That is the learning loop demonstrated on a genuinely unseen condition, and it is better
evidence than eight green scenarios.

## Metrics to report

- Run Result **correctness** per scenario — the classification, not merely pass/fail
- **stability**: identical inputs five times, identical results (the brief's multi-run
  stability stretch goal)
- **LLM calls during replay: 0**, enforced by an import test rather than asserted
- **wall-clock**: discovery versus replay
- **rung usage** per target, and the Fallback Match rate — the drift alarm
- **discovery cost**: actions taken, wasted actions, dollars spent
