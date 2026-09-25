"""Every log line, screenshot and result passes through here.

One writer means one place where redaction happens, and a write-ahead line before
and after each action means a run that dies mid-commit can be recognised later.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from ..domain.result import RunResult
from .redact import Redactor


class EvidenceWriter:
    def __init__(self, directory: Path, redactor: Redactor | None = None):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        # Every line and every image leaves through this one object. A writer built
        # without one still masks text and patterns; it simply knows of no Sensitive
        # Regions, because nobody told it which app it is writing about.
        self.redactor = redactor or Redactor()
        self.trail: list[dict] = []
        self._fh = (self.dir / "trail.jsonl").open("a")
        self._shots = 0

    def event(self, run_id, event, **fields):
        record = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "run_id": run_id,
            "event": event,
            **self.redactor.fields(fields),
        }
        self.trail.append(record)
        self._fh.write(json.dumps(record) + "\n")
        self._fh.flush()          # write-ahead: the line survives a crash
        return record

    def intervention(self, request) -> Path:
        """What the Operator is given, written through the same gate as everything
        else in this directory. It used to be dumped by the request itself, so the one
        file an Operator reads was the one file the Redactor never saw."""
        name = "approval.json" if getattr(request, "kind", "") == "approval" else "intervention.json"
        path = self.dir / name
        path.write_text(json.dumps(self.redactor.fields(dict(request.__dict__)), indent=2))
        return path

    def raw_json(self, name: str, data) -> Path:
        """The one write that does not pass the Redactor, by name.

        A Discovery Run's actions are what the Recorder compiles: they must keep the
        example values a Reviewer declared, or the Recorder cannot turn them into
        inputs. Secrets never reach this list (they are PROTECTED before it is built),
        and the Reviewer sees every example value in the draft's provenance. The
        exemption is a method here so it is visible in one place, not a Path.write_text
        somewhere else.
        """
        path = self.dir / name
        path.write_text(json.dumps(data, indent=2))
        return path

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

