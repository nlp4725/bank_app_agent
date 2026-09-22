"""The Replay Engine: executes an Artifact with no model in the decision loop.

The order of checks per Transition is in docs/error-taxonomy.md. Everything the
engine knows about surprises is in the four Conditions; everything it knows about
*this* app is data in the Artifact.
"""

import os
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .artifact import Artifact
from .evidence import EvidenceWriter
from .result import RunResult
from .surface import Surface

PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")
OBSERVE = object()      # "a recovery ran: look at where it left us, do not re-act"
DEFAULT_TIMEOUT_MS = 6000
DEFAULT_RECOVERY_BUDGET = 2


class MissingSecret(Exception):
    pass


class EnvSecrets:
    """Secrets by reference, resolved at the moment of use, never stored."""

    def get(self, name: str) -> str:
        value = os.environ.get(f"SECRET_{name.upper()}")
        if value is None:
            demo = {"login_username": "svc_officer", "login_password": "officer-pw"}
            if name in demo:
                return demo[name]          # demo app only; documented in the README
            raise MissingSecret(name)
        return value


@dataclass
class RunContext:
    origin: str
    attended: bool = False
    tenant: str = "bank_a"
    secrets: object = field(default_factory=EnvSecrets)
    evidence_root: str = "runs"
    headless: bool = True


def render(value: str, inputs: dict) -> str:
    return PLACEHOLDER.sub(lambda m: str(inputs.get(m.group(1), m.group(0))), value)


def rendered_predicate(predicate, inputs):
    """Fill placeholders inside a predicate before evaluating it."""
    data = predicate.model_copy(deep=True)
    for attr in ("value", "pattern", "equals"):
        if getattr(data, attr, None):
            setattr(data, attr, render(getattr(data, attr), inputs))
    if getattr(data, "of", None):
        data.of = [rendered_predicate(p, inputs) for p in data.of]
    return data


def validate_inputs(artifact: Artifact, inputs: dict) -> str | None:
    for name, spec in artifact.contract.inputs.items():
        if name not in inputs:
            if spec.required:
                return f"missing required input {name!r}"
            continue
        value = str(inputs[name])
        if spec.pattern and not re.fullmatch(spec.pattern, value):
            return f"input {name!r} does not match {spec.pattern}"
        if spec.values and value not in spec.values:
            return f"input {name!r} must be one of {spec.values}"
        if spec.max_length and len(value) > spec.max_length:
            return f"input {name!r} is longer than {spec.max_length}"
    return None


def replay(artifact: Artifact, inputs: dict, ctx: RunContext) -> RunResult:
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    evidence = EvidenceWriter(Path(ctx.evidence_root) / run_id, artifact)

    # ── the front door: nothing is touched if any of this fails ──────────────
    if artifact.capability.status != "approved":
        return evidence.refused(run_id, f"artifact is {artifact.capability.status!r}, not approved")
    problem = validate_inputs(artifact, inputs)
    if problem:
        return evidence.refused(run_id, problem)
    consequential = [t for t in artifact.transitions if t.risk == "consequential"]
    if not ctx.attended and any(t.verify_effect is None for t in consequential):
        return evidence.refused(run_id, "a consequential action has no verification check")
    for name in artifact.needs.secrets:
        try:
            ctx.secrets.get(name)
        except MissingSecret:
            return evidence.refused(run_id, f"secret {name!r} does not resolve")

    surface = Surface(ctx.origin, headless=ctx.headless)
    try:
        return _run(artifact, inputs, ctx, surface, evidence, run_id)
    finally:
        surface.close()
        evidence.close()


def _run(artifact, inputs, ctx, surface, evidence, run_id) -> RunResult:
    outputs, budgets = {}, {}
    surface.goto("/login")

    index = 0
    guard = 0
    observe_only = False          # set after a recovery that should not re-act
    while index < len(artifact.transitions):
        guard += 1
        if guard > 3 * len(artifact.transitions) + 10:
            return evidence.failed(run_id, "loop_detected", step=artifact.transitions[index].from_state)

        transition = artifact.transitions[index]
        timeout = transition.timeout_ms or DEFAULT_TIMEOUT_MS

        if observe_only:
            # A recovery has just run; look at where it left us before acting again.
            observe_only = False
            destination = artifact.state(transition.to_state)
            if destination and destination.checkpoint and surface.holds(
                rendered_predicate(destination.checkpoint, inputs), artifact, timeout_ms=timeout
            ):
                index += 1
                continue

        # 1. verify before acting: are we where this transition starts?
        start = artifact.state(transition.from_state)
        if start and start.checkpoint and not surface.holds(
            rendered_predicate(start.checkpoint, inputs), artifact, timeout_ms=timeout
        ):
            outcome = _handle_surprise(artifact, inputs, ctx, surface, evidence, run_id,
                                       transition, budgets, "precondition")
            if isinstance(outcome, RunResult):
                return outcome
            index, observe_only = _resume(artifact, outcome, index)
            continue

        # 2. resolve the Target
        target = artifact.targets[transition.action.target]
        found = surface.resolve(target, timeout_ms=timeout)
        if found is None:
            evidence.event(run_id, "target_unresolved", target=transition.action.target)
            return evidence.failed(run_id, "target_not_found", step=transition.from_state,
                                   expected=f"a control for {transition.action.target}",
                                   observed=surface.url, screenshot=evidence.snap(surface))

        # 3. risk gate
        if transition.risk == "consequential" and ctx.attended:
            evidence.event(run_id, "operator_approval_required",
                           step=transition.from_state, matched_by=found.matched_by)

        # 4. act
        evidence.event(run_id, "about_to", step=transition.from_state,
                       action=transition.action.type, target=transition.action.target,
                       risk=transition.risk, matched_by=found.matched_by)
        _act(surface, transition, found, inputs, ctx, outputs)
        evidence.event(run_id, "done", step=transition.from_state,
                       action=transition.action.type, target=transition.action.target,
                       matched_by=found.matched_by)

        # 5. observe: did it land where the artifact says?
        destination = artifact.state(transition.to_state)
        if destination and destination.checkpoint and not surface.holds(
            rendered_predicate(destination.checkpoint, inputs), artifact, timeout_ms=timeout
        ):
            outcome = _handle_surprise(artifact, inputs, ctx, surface, evidence, run_id,
                                       transition, budgets, "checkpoint")
            if isinstance(outcome, RunResult):
                return outcome
            index, observe_only = _resume(artifact, outcome, index)
            continue

        index += 1

    return evidence.succeeded(run_id, outputs)


def _act(surface, transition, found, inputs, ctx, outputs):
    action = transition.action
    if action.type == "click":
        surface.click(found)
    elif action.type == "type":
        value = ctx.secrets.get(action.value_ref) if action.value_ref else render(action.value, inputs)
        surface.type(found, value)
    elif action.type == "select":
        surface.select(found, render(action.value, inputs))
    elif action.type == "read":
        outputs[action.into] = surface.read(found)


def _handle_surprise(artifact, inputs, ctx, surface, evidence, run_id, transition, budgets, stage):
    """Checkpoint missed: ask the Watchers what this screen is, then react."""
    for watcher in artifact.watchers:
        if not surface.holds(rendered_predicate(watcher.trigger, inputs), artifact, timeout_ms=0):
            continue
        evidence.event(run_id, "watcher_matched", watcher=watcher.id,
                       condition=watcher.condition, step=transition.from_state)

        if watcher.condition == "business_outcome":
            spec = next(o for o in artifact.contract.outcomes if o.code == watcher.outcome)
            return evidence.business_outcome(run_id, spec)

        if watcher.condition == "hard_failure":
            return evidence.failed(run_id, "hard_failure", step=transition.from_state,
                                   observed=watcher.id, screenshot=evidence.snap(surface))

        if watcher.condition == "escalate":
            if not ctx.attended:
                return evidence.failed(run_id, "escalation_required", step=transition.from_state,
                                       watcher=watcher.id, screenshot=evidence.snap(surface))
            return evidence.failed(run_id, "operator_handoff_not_implemented",
                                   step=transition.from_state, watcher=watcher.id)

        if watcher.condition == "recoverable":
            budget = watcher.budget or DEFAULT_RECOVERY_BUDGET
            used = budgets.get(watcher.id, 0)
            if used >= budget:
                return evidence.failed(run_id, "retries_exhausted", step=transition.from_state,
                                       watcher=watcher.id, screenshot=evidence.snap(surface))
            budgets[watcher.id] = used + 1
            if watcher.recovery is not None:
                recovery_target = artifact.targets[watcher.recovery.target]
                found = surface.resolve(recovery_target, timeout_ms=4000)
                if found is None:
                    return evidence.failed(run_id, "recovery_target_not_found",
                                           step=transition.from_state, watcher=watcher.id)
                surface.click(found)
            else:
                time.sleep(0.4)
            evidence.event(run_id, "recovered", watcher=watcher.id,
                           attempt=budgets[watcher.id], resume_at=watcher.resume_at)
            # No resume_at: dismissing an interruption usually leaves us where the
            # transition was heading, so look before acting again.
            return watcher.resume_at or OBSERVE

    # Nothing recognises this screen.
    if transition.risk == "consequential" and transition.verify_effect is not None:
        took_effect = _verify_effect(artifact, inputs, surface, transition)
        evidence.event(run_id, "verification_check", step=transition.from_state,
                       took_effect=took_effect)
        if took_effect:
            return evidence.succeeded(run_id, {}, verified_effect=True)
        return evidence.failed(run_id, "unknown_state", step=transition.from_state,
                               expected=str(transition.to_state), observed=surface.url,
                               screenshot=evidence.snap(surface), verified_effect=False)

    if ctx.attended:
        return evidence.failed(run_id, "escalation_required", step=transition.from_state,
                               screenshot=evidence.snap(surface))
    return evidence.failed(run_id, "unknown_state", step=transition.from_state,
                           expected=str(transition.to_state), observed=surface.url,
                           screenshot=evidence.snap(surface))


def _verify_effect(artifact, inputs, surface, transition) -> bool:
    """Look, rather than clicking again."""
    verify = transition.verify_effect
    if verify.goto:
        surface.goto(render(verify.goto, inputs))
    return surface.holds(rendered_predicate(verify.predicate, inputs), artifact, timeout_ms=3000)


def _resume(artifact, directive, current: int) -> tuple[int, bool]:
    """Where to continue after a recovery: re-observe here, or rewind to a State."""
    if directive is OBSERVE:
        return current, True
    for i, t in enumerate(artifact.transitions):
        if t.from_state == directive:
            return i, False
    return current, False
