"""Every log line, screenshot and result passes through here.

One writer means one place where redaction happens, and a write-ahead line before
and after each action means a run that dies mid-commit can be recognised later.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from .redact import redact
from .result import RunResult


class EvidenceWriter:
    def __init__(self, directory: Path, artifact):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.artifact = artifact
        self.trail = []
        self._fh = (self.dir / "trail.jsonl").open("a")
        self._shots = 0

    def event(self, run_id, event, **fields):
        record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "run_id": run_id,
            "event": event,
            **redact(fields),
        }
        self.trail.append(record)
        self._fh.write(json.dumps(record) + "\n")
        self._fh.flush()          # write-ahead: the line survives a crash
        return record

    def snap(self, surface) -> str:
        self._shots += 1
        path = self.dir / f"screen_{self._shots}.png"
        try:
            surface.screenshot(str(path))
        except Exception:
            return ""
        return str(path)

    # ── results ──────────────────────────────────────────────────────────────

    def _finish(self, result: RunResult) -> RunResult:
        result.evidence_id = str(self.dir)
        result.trail = self.trail
        self.event(result.run_id, "result", status=result.status,
                   reason=result.reason, outcome=(result.outcome or {}).get("code"))
        return result

    def succeeded(self, run_id, outputs, **extra):
        return self._finish(RunResult(status="succeeded", run_id=run_id,
                                      outputs=redact(outputs, keep_values=True), **extra))

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

    def outcome_unknown(self, run_id, step, guidance):
        return self._finish(RunResult(status="outcome_unknown", run_id=run_id,
                                      step=step, reason=guidance))

    def close(self):
        self._fh.close()
