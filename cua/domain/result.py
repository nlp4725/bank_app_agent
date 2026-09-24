"""The result contract: one shape, six statuses. See docs/error-taxonomy.md."""

from dataclasses import dataclass, field


@dataclass
class RunResult:
    status: str                      # succeeded | business_outcome | failed | refused | aborted | outcome_unknown
    run_id: str = ""
    outputs: dict = field(default_factory=dict)
    outcome: dict | None = None      # business_outcome: code, resolver, caller_hint, retry_same_inputs, data
    reason: str | None = None        # failed / refused
    step: str | None = None
    expected: str | None = None
    observed: str | None = None
    watcher: str | None = None
    evidence_id: str | None = None
    verified_effect: bool | None = None
    trail: list = field(default_factory=list)

    def __str__(self):
        bits = [self.status]
        if self.outcome:
            bits.append(self.outcome["code"])
        if self.reason:
            bits.append(self.reason)
        if self.step:
            bits.append(f"at {self.step}")
        return " · ".join(bits)
