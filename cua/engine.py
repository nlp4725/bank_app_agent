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
from .handoff import (AUTOMATION, AWAITING_OPERATOR, DONE, OPERATOR_IN_CONTROL,
                      RESUMING, Control, Intervention, observe_operator, wait_for_decision)
from .policy import PolicyError, policy_for
from .result import RunResult
from .surface import Surface

PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")
OBSERVE = object()      # "a recovery ran: look at where it left us, do not re-act"
DEFAULT_TIMEOUT_MS = 6000
DEFAULT_RECOVERY_BUDGET = 2


class MissingSecret(Exception):
    pass


DEMO_ACCOUNTS = {           # the demo app only; documented in the README
    "svc_read": {"login_username": "svc_read", "login_password": "read-only-pw"},
    "svc_officer": {"login_username": "svc_officer", "login_password": "officer-pw"},
}


class EnvSecrets:
    """Secrets by reference, resolved at the moment of use, never stored.

    Which credential is used follows from the Role's Service Account, so a
    read-only capability signs in as a login that cannot commit anything.
    """

    def __init__(self, service_account: str = "svc_officer"):
        self.service_account = service_account

    def get(self, name: str) -> str:
        value = os.environ.get(f"SECRET_{self.service_account}_{name}".upper())
        if value is None:
            value = DEMO_ACCOUNTS.get(self.service_account, {}).get(name)
        if value is None:
            raise MissingSecret(name)
        return value


@dataclass
class RunContext:
    origin: str
    attended: bool = False
    tenant: str = "bank_a"
    secrets: object | None = None      # defaults to the Role's Service Account
    evidence_root: str = "runs"
    headless: bool = True
    # An Operator: called when the run escalates and a person is on shift. Given the
    # intervention and the live session, it returns "resume" or "abort". Absent, the
    # run waits for a decision file, which is what an operator console would write.
    operator: object | None = None
    operator_timeout_s: float = 120.0
    # A Tenant Overlay: appearance only. Linted before it is applied, so a patch that
    # tried to add a transition, change the contract or widen needs is refused here
    # rather than quietly taking effect.
    overlay: dict | None = None


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
    try:
        policy = policy_for(artifact, ctx.tenant)
    except PolicyError as exc:
        return evidence.refused(run_id, str(exc))
    refusal = policy.refuse_reason(artifact)
    if refusal:
        return evidence.refused(run_id, refusal)
    if ctx.secrets is None:
        ctx.secrets = EnvSecrets(policy.service_account())

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

    if ctx.overlay:
        from .overlay import apply_overlay, lint_overlay
        problems = lint_overlay(artifact, ctx.overlay)
        if problems:
            return evidence.refused(run_id, f"overlay rejected: {problems[0]}")
        artifact = apply_overlay(artifact, ctx.overlay)
        evidence.event(run_id, "overlay_applied", tenant=ctx.overlay.get("tenant"),
                       targets=sorted(ctx.overlay.get("targets", {})))

    surface = Surface(ctx.origin, headless=ctx.headless, allowed_origins=[ctx.origin])
    try:
        return _run(artifact, inputs, ctx, surface, evidence, run_id, policy)
    finally:
        surface.close()
        evidence.close()


def _run(artifact, inputs, ctx, surface, evidence, run_id, policy) -> RunResult:
    outputs, budgets = {}, {}
    control = Control()
    escalations: dict[str, int] = {}
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
            # A recovery has just run. Where are we? Ask the Checkpoints rather than
            # assume: the destination first (an interruption usually leaves us where
            # the transition was heading), then any State whose Checkpoint holds.
            observe_only = False
            destination = artifact.state(transition.to_state)
            if destination and destination.checkpoint and surface.holds(
                rendered_predicate(destination.checkpoint, inputs), artifact, timeout_ms=timeout
            ):
                index += 1
                continue
            here = _where_are_we(artifact, inputs, surface)
            if here is not None and here != index:
                evidence.event(run_id, "reoriented", step=artifact.transitions[here].from_state)
                index = here
                continue

        # 1. verify before acting: are we where this transition starts?
        start = artifact.state(transition.from_state)
        if start and start.checkpoint and not surface.holds(
            rendered_predicate(start.checkpoint, inputs), artifact, timeout_ms=timeout
        ):
            outcome = _handle_surprise(artifact, inputs, ctx, surface, evidence, run_id,
                                       transition, budgets, "precondition", policy, control,
                                       escalations)
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

        # 2b. may we do this, here?
        path = surface.url[len(ctx.origin):] or "/"
        if not (policy.allows_page(path) and policy.allows_action(transition.action.type)):
            evidence.event(run_id, "policy_deny", step=transition.from_state,
                           path=path, action=transition.action.type)
            return evidence.failed(run_id, "policy_denied", step=transition.from_state,
                                   observed=path, screenshot=evidence.snap(surface))
        evidence.event(run_id, "policy_allow", step=transition.from_state,
                       path=path, action=transition.action.type)

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
            evidence.event(run_id, "checkpoint_missed", step=transition.to_state,
                           predicate=destination.checkpoint.type,
                           expected=getattr(destination.checkpoint, "target", None)
                                    or getattr(destination.checkpoint, "value", None),
                           url=surface.url, timeout_ms=timeout,
                           blocked_requests=surface.blocked_requests[-3:],
                           frames=[f.url for f in surface.page.frames])
            outcome = _handle_surprise(artifact, inputs, ctx, surface, evidence, run_id,
                                       transition, budgets, "checkpoint", policy, control,
                                       escalations)
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


def _handle_surprise(artifact, inputs, ctx, surface, evidence, run_id, transition, budgets,
                     stage, policy=None, control=None, escalations=None):
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
            return _hand_over(artifact, inputs, ctx, surface, evidence, run_id,
                              transition, control, watcher.id,
                              watcher.reason or f"watcher {watcher.id}", escalations)

        if watcher.condition == "recoverable":
            budget = watcher.budget or DEFAULT_RECOVERY_BUDGET
            used = budgets.get(watcher.id, 0)
            if used >= budget:
                return evidence.failed(run_id, "retries_exhausted", step=transition.from_state,
                                       watcher=watcher.id, screenshot=evidence.snap(surface))
            budgets[watcher.id] = used + 1
            if watcher.recovery is not None:
                recovery_path = surface.url[len(ctx.origin):] or "/"
                if not (policy.allows_page(recovery_path)
                        and policy.allows_action(watcher.recovery.type)):
                    evidence.event(run_id, "policy_deny", step=transition.from_state,
                                   path=recovery_path, action=watcher.recovery.type,
                                   watcher=watcher.id)
                    return evidence.failed(run_id, "policy_denied", step=transition.from_state,
                                           observed=recovery_path, watcher=watcher.id)
                recovery_target = artifact.targets[watcher.recovery.target]
                found = surface.resolve(recovery_target, timeout_ms=4000)
                if found is None:
                    return evidence.failed(run_id, "recovery_target_not_found",
                                           step=transition.from_state, watcher=watcher.id)
                surface.click(found)
            else:
                surface._tick(400)
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
        return _hand_over(artifact, inputs, ctx, surface, evidence, run_id, transition,
                          control, None, "no Watcher recognises this screen", escalations)
    return evidence.failed(run_id, "unknown_state", step=transition.from_state,
                           expected=str(transition.to_state), observed=surface.url,
                           screenshot=evidence.snap(surface))


MAX_ESCALATIONS_PER_STATE = 2


def _hand_over(artifact, inputs, ctx, surface, evidence, run_id, transition, control,
               watcher_id, reason, escalations=None) -> RunResult:
    """Pause, give the Operator this session, record what they did, resume or abort."""
    escalations = escalations if escalations is not None else {}
    used = escalations.get(transition.from_state, 0)
    if used >= MAX_ESCALATIONS_PER_STATE:
        # Bounded, so escalate -> resume -> escalate cannot become a loop that keeps
        # a person answering the same question forever.
        return evidence.failed(run_id, "escalation_budget_exhausted",
                               step=transition.from_state, watcher=watcher_id)
    escalations[transition.from_state] = used + 1
    shot = evidence.snap(surface)
    control.move(AWAITING_OPERATOR, "operator")
    request = Intervention(run_id=run_id, capability=artifact.capability.id,
                           state=transition.from_state, reason=reason,
                           watcher=watcher_id, url=surface.url, screenshot=shot)
    path = request.write(evidence.dir)
    evidence.event(run_id, "intervention_raised", step=transition.from_state,
                   watcher=watcher_id, reason=reason, request=str(path))

    before_url = surface.url
    control.move(OPERATOR_IN_CONTROL, "operator")
    if ctx.operator is not None:
        decision, who = ctx.operator(request, surface), "operator:callback"
    else:
        decision, who = wait_for_decision(evidence.dir, ctx.operator_timeout_s, surface._tick)

    evidence.event(run_id, "operator_acted", by=who, decision=decision,
                   **observe_operator(surface, before_url))

    if decision == "timeout":
        control.move(DONE, "automation")
        return evidence.failed(run_id, "escalation_timeout", step=transition.from_state,
                               watcher=watcher_id)
    if decision != "resume":
        control.move(DONE, "operator")
        return evidence.aborted(run_id, by=who, at_step=transition.from_state)

    # Resume re-checks where we are rather than assuming the Operator finished the job.
    control.move(RESUMING, "automation")
    here = _where_are_we(artifact, inputs, surface)
    control.move(AUTOMATION, "automation")
    if here is None:
        return evidence.failed(run_id, "resume_checkpoint_missed", step=transition.from_state,
                               observed=surface.url, screenshot=evidence.snap(surface))
    evidence.event(run_id, "resumed", step=artifact.transitions[here].from_state)
    return artifact.transitions[here].from_state


def _where_are_we(artifact, inputs, surface) -> int | None:
    """The first transition whose starting State's Checkpoint holds right now."""
    for i, transition in enumerate(artifact.transitions):
        state = artifact.state(transition.from_state)
        if state and state.checkpoint and surface.holds(
            rendered_predicate(state.checkpoint, inputs), artifact, timeout_ms=0
        ):
            return i
    return None


def _verify_effect(artifact, inputs, surface, transition) -> bool:
    """Look, rather than clicking again."""
    verify = transition.verify_effect
    if verify.goto:
        surface.goto(render(verify.goto, inputs))
    return surface.holds(rendered_predicate(verify.predicate, inputs), artifact, timeout_ms=3000)


def _resume(artifact, directive, current: int) -> tuple[int, bool]:
    """Where to continue after a recovery.

    A named resume_at wins when the Artifact has that State. Otherwise — and when an
    App Profile watcher names a State this Artifact does not have — re-observe:
    the engine works out where it is by asking which Checkpoint holds, rather than
    trusting a name. Watchers are shared across capabilities, so they cannot know
    what any one Artifact called its States.
    """
    if directive is not OBSERVE:
        for i, t in enumerate(artifact.transitions):
            if t.from_state == directive:
                return i, False
    return current, True
