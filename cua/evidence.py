"""Every log line, screenshot and result passes through here.

One writer means one place where redaction happens, and a write-ahead line before
and after each action means a run that dies mid-commit can be recognised later.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from .redact import Redactor
from .result import RunResult


class EvidenceWriter:
    def __init__(self, directory: Path, artifact, redactor: Redactor | None = None):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.artifact = artifact
        # Every line and every image leaves through this one object. A writer built
        # without one still masks text and patterns; it simply knows of no Sensitive
        # Regions, because nobody told it which app it is writing about.
        self.redactor = redactor or Redactor()
        self.trail = []
        self._fh = (self.dir / "trail.jsonl").open("a")
        self._shots = 0

    def event(self, run_id, event, **fields):
        record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "run_id": run_id,
            "event": event,
            **self.redactor.fields(fields),
        }
        self.trail.append(record)
        self._fh.write(json.dumps(record) + "\n")
        self._fh.flush()          # write-ahead: the line survives a crash
        return record

    def snap(self, surface) -> str:
        """A screenshot, with the declared Sensitive Regions already painted black.

        This is the path a failure and an Operator intervention take, so it goes
        through the same gate as a Discovery Run's captures rather than around it.
        """
        self._shots += 1
        path = self.dir / f"screen_{self._shots}.png"
        return self.redactor.screenshot(surface, str(path))

    # ── results ──────────────────────────────────────────────────────────────

    def _finish(self, result: RunResult) -> RunResult:
        result.evidence_id = str(self.dir)
        result.trail = self.trail
        self.event(result.run_id, "result", status=result.status,
                   reason=result.reason, outcome=(result.outcome or {}).get("code"))
        return result

    def succeeded(self, run_id, outputs, **extra):
        return self._finish(RunResult(status="succeeded", run_id=run_id,
                                      outputs=self.redactor.fields(outputs, keep_values=True),
                                      **extra))

    def business_outcome(self, run_id, spec):
        return self._finish(RunResult(
            status="business_outcome", run_id=run_id,
            outcome={"code": spec.code, "resolver": spec.resolver,
                     "caller_hint": spec.caller_hint,
                     "retry_same_inputs": spec.retry_same_inputs, "data": {}}))

    def failed(self, run_id, reason, **fields):
        fields.pop("screenshot", None)
        return self._finish(RunResult(status="failed", run_id=run_id, reason=reason, **fields))

    def refused(self, run_id, reason):
        return self._finish(RunResult(status="refused", run_id=run_id, reason=reason))

    def aborted(self, run_id, by, at_step):
        return self._finish(RunResult(status="aborted", run_id=run_id,
                                      reason=f"stopped by {by}", step=at_step))

    def outcome_unknown(self, run_id, step, guidance):
        return self._finish(RunResult(status="outcome_unknown", run_id=run_id,
                                      step=step, reason=guidance))

    def close(self):
        self._fh.close()


def unfinished(evidence_root) -> list[dict]:
    """Runs that died with a Consequential Action in flight.

    Each action is written down before it is performed and again after, and the line
    is flushed, so a run that stopped between the two leaves the pair unbalanced.
    On restart this is what turns "the process was killed mid-commit" into an answer
    — Outcome Unknown, do not retry — rather than silence. See CONTEXT.md, the error
    table's last row.
    """
    found = []
    for trail in sorted(Path(evidence_root).glob("*/trail.jsonl")):
        in_flight, settled = None, False
        for line in trail.read_text().splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event["event"] == "about_to" and event.get("risk") == "consequential":
                in_flight = event
            elif event["event"] in ("done", "verification_check"):
                in_flight = None
            elif event["event"] == "result":
                settled = True
        if in_flight is not None and not settled:
            found.append({"run_id": in_flight["run_id"], "evidence": str(trail.parent),
                          "step": in_flight.get("step"),
                          "action": in_flight.get("action"),
                          "target": in_flight.get("target"),
                          "status": "outcome_unknown",
                          "guidance": "a consequential action was in flight when the "
                                      "run stopped; someone must check whether it "
                                      "took effect before it is tried again"})
    return found
