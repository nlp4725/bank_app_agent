"""The Replay Engine: executes an Artifact with no model in the decision loop.

The order of checks per Transition is in docs/error-taxonomy.md. Everything the
engine knows about surprises is in the four Conditions; everything it knows about
*this* app is data in the Artifact.
"""

import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from ..domain.artifact import Artifact
from ..domain.placeholders import render
from ..domain.result import RunResult
from ..evidence import EvidenceWriter
from ..governance.overlay import apply_overlay, lint_overlay
from ..governance.policy import PolicyError, policy_for, route_of
from ..governance.profile import redactor_for
from ..secrets import EnvSecrets, MissingSecret
from ..surface import Surface
from .handoff import (AUTOMATION, AWAITING_OPERATOR, DONE, OPERATOR_IN_CONTROL,
                      RESUMING, Control, Intervention, observe_operator, wait_for_decision)
from .narration import Silent
from .predicates import Predicates

OBSERVE = object()      # "a recovery ran: look at where it left us, do not re-act"
DEFAULT_TIMEOUT_MS = 6000
DEFAULT_RECOVERY_BUDGET = 2


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
    # How the run looks to a person watching it — pacing, narration, whether the
    # browser is left open. Demo ergonomics, behind their own seam: see cua/narration.
    narrator: object | None = None


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
    # The Redactor comes from the vendor app, so a replay's evidence is masked by the
    # same declarations a Discovery Run's is — screenshots included.
    evidence = EvidenceWriter(Path(ctx.evidence_root) / run_id,
                              redactor=redactor_for(artifact.capability.vendor_app))

    # ── the front door: nothing is touched if any of this fails ──────────────
    try:
        policy = policy_for(artifact, ctx.tenant)
    except PolicyError as exc:
        return evidence.refused(run_id, str(exc))
    refusal = policy.refuse_reason(artifact, origin=ctx.origin)
    if refusal:
        return evidence.refused(run_id, refusal)
    secrets = ctx.secrets or EnvSecrets(policy.service_account())

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
            secrets.get(name)
        except MissingSecret:
            return evidence.refused(run_id, f"secret {name!r} does not resolve")

    if ctx.overlay:
        problems = lint_overlay(artifact, ctx.overlay)
        if problems:
            return evidence.refused(run_id, f"overlay rejected: {problems[0]}")
        artifact = apply_overlay(artifact, ctx.overlay)
        evidence.event(run_id, "overlay_applied", tenant=ctx.overlay.get("tenant"),
                       targets=sorted(ctx.overlay.get("targets", {})))

    narrator = ctx.narrator or Silent()
    surface = Surface(ctx.origin, headless=ctx.headless, allowed_origins=[ctx.origin],
                      slow_mo_ms=narrator.slow_mo_ms)
    try:
        return Run(artifact, inputs, ctx, surface, evidence, run_id, policy,
                   narrator, secrets).execute()
    finally:
        narrator.linger(surface)
        surface.close()
        evidence.close()


MAX_ESCALATIONS_PER_STATE = 2


class Run:
    """One replay in progress: the state of a run, and everything done to it.

    The state a run accumulates — outputs read so far, recovery budgets spent,
    escalations raised, who holds the lease, where in the flow we are — lives here
    rather than in a loop's locals, so the steps that need it are methods taking a
    Transition rather than functions taking the whole world. Callers and tests cross
    one interface: `execute()`.
    """

    def __init__(self, artifact, inputs, ctx, surface, evidence, run_id, policy,
                 narrator=None, secrets=None):
        self.artifact = artifact
        self.secrets = secrets if secrets is not None else ctx.secrets
        self.inputs = inputs
        self.ctx = ctx
        self.surface = surface
        self.evidence = evidence
        self.run_id = run_id
        self.policy = policy
        self.narrator = narrator or Silent()
        self.predicates = Predicates(surface, artifact, inputs)
        self.origin = ctx.origin.rstrip("/")

        self.outputs: dict = {}
        self.budgets: dict[str, int] = {}          # recoveries spent, per Watcher
        self.escalations: dict[str, int] = {}      # interventions raised, per State
        self.control = Control()

    # ── the interface ────────────────────────────────────────────────────────

    def execute(self) -> RunResult:
        """Walk the Artifact's transitions until one of them answers the caller."""
        self.surface.goto("/login")
        index, guard, observe_only = 0, 0, False

        while index < len(self.artifact.transitions):
            guard += 1
            if guard > 3 * len(self.artifact.transitions) + 10:
                return self.failed("loop_detected",
                                   step=self.artifact.transitions[index].from_state)

            transition = self.artifact.transitions[index]

            if observe_only:
                observe_only = False
                here = self._reorient(transition, index)
                if here is not None:
                    index = here
                    continue

            outcome = self._step(transition)
            if isinstance(outcome, RunResult):
                return outcome
            if outcome is None:
                index += 1
                continue
            index, observe_only = self._resume_at(outcome, index)

        return self.evidence.succeeded(self.run_id, self.outputs)

    # ── one transition ───────────────────────────────────────────────────────

    def _step(self, transition):
        """None to advance, a directive to re-enter elsewhere, a RunResult to stop.

        The order of checks is docs/error-taxonomy.md: verify where we are, resolve
        the Target, ask the Policy, act, then verify where we landed.
        """
        timeout = transition.timeout_ms or DEFAULT_TIMEOUT_MS

        # 1. verify before acting: are we where this transition starts?
        start = self.artifact.state(transition.from_state)
        if start and start.checkpoint and not self.predicates.holds(
            start.checkpoint, timeout_ms=timeout
        ):
            return self._surprise(transition, "precondition")

        # 2. resolve the Target
        target = self.artifact.targets[transition.action.target]
        found = self.surface.resolve(target, timeout_ms=timeout)
        if found is None:
            self.event("target_unresolved", target=transition.action.target)
            return self.failed("target_not_found", step=transition.from_state,
                               expected=f"a control for {transition.action.target}",
                               observed=self.surface.url, snap=True)

        # 2b. may we do this, here?
        denied = self._refuse_if_not_permitted(transition.from_state, transition.action.type)
        if denied is not None:
            return denied

        # 3. risk gate
        if transition.risk == "consequential" and self.ctx.attended:
            self.event("operator_approval_required",
                       step=transition.from_state, matched_by=found.matched_by)

        # 4. act
        self.narrator.transition(transition, found)
        self.event("about_to", step=transition.from_state, action=transition.action.type,
                   target=transition.action.target, risk=transition.risk,
                   matched_by=found.matched_by)
        self._act(transition, found)
        self.event("done", step=transition.from_state, action=transition.action.type,
                   target=transition.action.target, matched_by=found.matched_by)

        # 5. observe: did it land where the artifact says?
        destination = self.artifact.state(transition.to_state)
        if destination and destination.checkpoint and not self.predicates.holds(
            destination.checkpoint, timeout_ms=timeout
        ):
            self.event("checkpoint_missed", step=transition.to_state,
                       predicate=destination.checkpoint.type,
                       expected=getattr(destination.checkpoint, "target", None)
                                or getattr(destination.checkpoint, "value", None),
                       url=self.surface.url, timeout_ms=timeout,
                       blocked_requests=self.surface.blocked_requests[-3:],
                       frames=self.surface.frame_urls())
            return self._surprise(transition, "checkpoint")
        return None

    def _act(self, transition, found):
        action = transition.action
        if action.type == "click":
            self.surface.click(found)
        elif action.type == "type":
            value = (self.secrets.get(action.value_ref) if action.value_ref
                     else render(action.value, self.inputs))
            self.surface.type(found, value)
        elif action.type == "select":
            self.surface.select(found, render(action.value, self.inputs))
        elif action.type == "read":
            self.outputs[action.into] = self.surface.read(found)

    # ── surprises ────────────────────────────────────────────────────────────

    def _surprise(self, transition, stage):
        """A Checkpoint did not hold: ask the Watchers what this screen is.

        `stage` is "precondition" (we never acted) or "checkpoint" (we acted and the
        screen is not what the Artifact expects). It is the difference between a step
        that can simply be retried and one whose effect is now in doubt.
        """
        for watcher in self.artifact.watchers:
            if not self.predicates.holds(watcher.trigger, timeout_ms=0):
                continue
            self.event("watcher_matched", watcher=watcher.id,
                       condition=watcher.condition, step=transition.from_state)
            handler = getattr(self, f"_on_{watcher.condition}")
            return handler(transition, watcher, stage)
        return self._unrecognised(transition, stage)

    def _on_business_outcome(self, transition, watcher, stage):
        spec = next(o for o in self.artifact.contract.outcomes if o.code == watcher.outcome)
        return self.evidence.business_outcome(self.run_id, spec)

    def _on_hard_failure(self, transition, watcher, stage):
        return self.failed("hard_failure", step=transition.from_state,
                           observed=watcher.id, snap=True)

    def _on_escalate(self, transition, watcher, stage):
        if not self.ctx.attended:
            return self.failed("escalation_required", step=transition.from_state,
                               watcher=watcher.id, snap=True)
        return self._hand_over(transition, watcher.id,
                               watcher.reason or f"watcher {watcher.id}", stage)

    def _on_recoverable(self, transition, watcher, stage):
        """Fix it within the run, within a budget, and never by acting twice."""
        budget = watcher.budget or DEFAULT_RECOVERY_BUDGET
        used = self.budgets.get(watcher.id, 0)
        if used >= budget:
            return self.failed("retries_exhausted", step=transition.from_state,
                               watcher=watcher.id, snap=True)
        self.budgets[watcher.id] = used + 1

        if watcher.recovery is not None:
            denied = self._refuse_if_not_permitted(transition.from_state,
                                                   watcher.recovery.type, watcher=watcher.id)
            if denied is not None:
                return denied
            found = self.surface.resolve(self.artifact.targets[watcher.recovery.target],
                                         timeout_ms=4000)
            if found is None:
                return self.failed("recovery_target_not_found",
                                   step=transition.from_state, watcher=watcher.id)
            self.surface.click(found)
        else:
            self.surface.wait(400)

        self.event("recovered", watcher=watcher.id, attempt=self.budgets[watcher.id],
                   resume_at=watcher.resume_at)
        # No resume_at: dismissing an interruption usually leaves us where the
        # transition was heading, so look before acting again.
        return watcher.resume_at or OBSERVE

    def _unrecognised(self, transition, stage):
        """Nothing recognises this screen. Look before guessing, then ask a person."""
        if transition.risk == "consequential" and transition.verify_effect is not None:
            took_effect = self._verify(transition)
            self.event("verification_check", step=transition.from_state,
                       took_effect=took_effect)
            if took_effect:
                # The commit landed. The outputs read on the way here are still the
                # answer, so they are returned rather than dropped.
                return self.evidence.succeeded(self.run_id, self.outputs,
                                               verified_effect=True)
            # Settled, in the negative: the action did not take effect, so this is a
            # plain failure and the caller may retry.
            return self.failed("unknown_state", step=transition.from_state,
                               expected=str(transition.to_state),
                               observed=self.surface.url, snap=True, verified_effect=False)

        if self.ctx.attended:
            return self._hand_over(transition, None,
                                   "no Watcher recognises this screen", stage)
        return self._unsettled(transition, "unknown_state", stage)

    def _unsettled(self, transition, reason, stage, **fields) -> RunResult:
        """A screen we cannot read, possibly after an action we cannot take back.

        If the Consequential Action was actually performed — the Checkpoint after it
        is what failed, not the one before — and no Verification Check settled the
        question, the effect was never confirmed either way: that is Outcome Unknown,
        not Failed. The difference is what the Calling Agent does next. Failed invites
        a retry; Outcome Unknown means a person must look before anything is tried
        again. A precondition that did not hold means we never acted, so it is a
        plain failure.
        """
        self.evidence.snap(self.surface)
        if (stage == "checkpoint" and transition.risk == "consequential"
                and transition.verify_effect is None):
            return self.evidence.outcome_unknown(
                self.run_id, step=transition.from_state,
                guidance=("a consequential action was performed and no verification "
                          "check could confirm whether it took effect; do not retry "
                          "until someone has looked"))
        return self.failed(reason, step=transition.from_state,
                           expected=str(transition.to_state),
                           observed=self.surface.url, **fields)

    def _verify(self, transition) -> bool:
        """Look, rather than clicking again."""
        verify = transition.verify_effect
        return self.predicates.after_going_to(verify.goto, verify.predicate)

    # ── handing the session to a person ──────────────────────────────────────

    def _hand_over(self, transition, watcher_id, reason, stage) -> RunResult:
        """Pause, give the Operator this session, record what they did, resume or abort."""
        used = self.escalations.get(transition.from_state, 0)
        if used >= MAX_ESCALATIONS_PER_STATE:
            # Bounded, so escalate -> resume -> escalate cannot become a loop that
            # keeps a person answering the same question forever.
            return self._unsettled(transition, "escalation_budget_exhausted", stage,
                                   watcher=watcher_id)
        self.escalations[transition.from_state] = used + 1

        watcher = next((w for w in self.artifact.watchers if w.id == watcher_id), None)
        shot = self.evidence.snap(self.surface)
        self.control.move(AWAITING_OPERATOR, "operator")
        request = Intervention(run_id=self.run_id, capability=self.artifact.capability.id,
                               state=transition.from_state, reason=reason,
                               watcher=watcher_id, url=self.surface.url, screenshot=shot,
                               instruction=(watcher.operator_instruction if watcher else None))
        path = self.evidence.intervention(request)
        self.event("intervention_raised", step=transition.from_state,
                   watcher=watcher_id, reason=reason, request=str(path))

        before_url = self.surface.url
        self.control.move(OPERATOR_IN_CONTROL, "operator")
        decision, who = self._await_operator(request, watcher)
        self.event("operator_acted", by=who, decision=decision,
                   **observe_operator(self.surface, before_url))

        if decision == "timeout":
            self.control.move(DONE, "automation")
            return self._unsettled(transition, "escalation_timeout", stage,
                                   watcher=watcher_id)
        if decision != "resume":
            self.control.move(DONE, "operator")
            return self.evidence.aborted(self.run_id, by=who, at_step=transition.from_state)

        # Resume re-checks where we are rather than assuming the Operator finished.
        self.control.move(RESUMING, "automation")
        here = self._where_am_i()
        self.control.move(AUTOMATION, "automation")
        if here is None:
            return self._unsettled(transition, "resume_checkpoint_missed", stage)
        self.event("resumed", step=self.artifact.transitions[here].from_state)
        return self.artifact.transitions[here].from_state

    def _await_operator(self, request, watcher) -> tuple[str, str]:
        def blocker_cleared() -> bool:
            """The blocking screen is gone and we recognise where we are."""
            if watcher is not None and self.predicates.holds(watcher.trigger, timeout_ms=0):
                return False
            return self._where_am_i() is not None

        if self.ctx.operator is not None:
            decision = self.ctx.operator(request, self.surface) or ""
            if decision:
                return decision, "operator:callback"
            # They acted without answering; let the screen decide.
        return wait_for_decision(self.evidence.dir, self.ctx.operator_timeout_s,
                                 self.surface.wait, blocker_cleared)

    # ── where are we ─────────────────────────────────────────────────────────

    def _where_am_i(self) -> int | None:
        """The first transition whose starting State's Checkpoint holds right now."""
        for i, transition in enumerate(self.artifact.transitions):
            state = self.artifact.state(transition.from_state)
            if state and state.checkpoint and self.predicates.holds(state.checkpoint,
                                                                    timeout_ms=0):
                return i
        return None

    def _reorient(self, transition, index) -> int | None:
        """A recovery has just run. Where are we?

        Ask the Checkpoints rather than assume: the destination first (an interruption
        usually leaves us where the transition was heading), then any State whose
        Checkpoint holds. None means "stay here and act".
        """
        timeout = transition.timeout_ms or DEFAULT_TIMEOUT_MS
        destination = self.artifact.state(transition.to_state)
        if destination and destination.checkpoint and self.predicates.holds(
            destination.checkpoint, timeout_ms=timeout
        ):
            return index + 1
        here = self._where_am_i()
        if here is not None and here != index:
            self.event("reoriented", step=self.artifact.transitions[here].from_state)
            return here
        return None

    def _resume_at(self, directive, current: int) -> tuple[int, bool]:
        """Where to continue after a recovery.

        A named resume_at wins when the Artifact has that State. Otherwise — and when
        an App Profile watcher names a State this Artifact does not have — re-observe:
        the engine works out where it is by asking which Checkpoint holds, rather than
        trusting a name. Watchers are shared across capabilities, so they cannot know
        what any one Artifact called its States.
        """
        if directive is not OBSERVE:
            for i, t in enumerate(self.artifact.transitions):
                if t.from_state == directive:
                    return i, False
        return current, True

    # ── policy, evidence, narration ──────────────────────────────────────────

    def path(self) -> str:
        return route_of(self.surface.url, self.origin)

    def _refuse_if_not_permitted(self, step, action_type, watcher=None):
        path = self.path()
        if self.policy.allows_page(path) and self.policy.allows_action(action_type):
            if watcher is None:
                self.event("policy_allow", step=step, path=path, action=action_type)
            return None
        self.event("policy_deny", step=step, path=path, action=action_type,
                   **({"watcher": watcher} if watcher else {}))
        return self.failed("policy_denied", step=step, observed=path,
                           snap=watcher is None, **({"watcher": watcher} if watcher else {}))

    def event(self, name, **fields):
        return self.evidence.event(self.run_id, name, **fields)

    def failed(self, reason, *, snap=False, **fields) -> RunResult:
        if snap:
            fields["screenshot"] = self.evidence.snap(self.surface)
        return self.evidence.failed(self.run_id, reason, **fields)
