"""Checks a well-formed Artifact must also pass before it can be trusted.

The schema stops an Artifact naming something the engine cannot do; these rules
stop an Artifact that is well-formed and still wrong — a discovery literal frozen
into a checkpoint, a placeholder nothing fills, an outcome promised to the caller
that nothing can produce.
"""

from ..domain.artifact import Artifact
from ..domain.issue import Issue
from ..domain.placeholders import PLACEHOLDER
from ..governance.roles import UnknownRole, covers, get_role

MIN_TRIGGER_TEXT = 6      # a text trigger shorter than this cannot name a screen


def _strings(obj, path="") -> list[tuple[str, str]]:
    """Every string in a nested structure, with a readable path to it."""
    out = []
    if isinstance(obj, str):
        out.append((path, obj))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            out.extend(_strings(v, f"{path}.{k}" if path else str(k)))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            out.extend(_strings(v, f"{path}[{i}]"))
    return out


def lint(artifact: Artifact, unattended: bool = False) -> list[Issue]:
    issues: list[Issue] = []
    a = artifact

    state_ids = {s.id for s in a.states}
    # 0. A State id is the name everything else uses to point at it — transitions,
    #    resume_at, the trail, an intervention — so two States sharing one would make
    #    "go back to X" ambiguous.
    seen = set()
    for st in a.states:
        if st.id in seen:
            issues.append(Issue("duplicate_state", f"state {st.id}",
                                "two States share this id; every reference must be unambiguous"))
        seen.add(st.id)
    target_ids = set(a.targets)
    declared_outcomes = {o.code for o in a.contract.outcomes}
    produced_outcomes = {w.outcome for w in a.watchers if w.outcome}

    # Where a recorded value could actually do damage: what the artifact types into
    # the app, and what it asserts about the screen. Identifiers (state ids, target
    # names) are names, not data — scanning them produced false positives such as a
    # target called t_savings_balance matching the example value "savings".
    flow = {
        "transitions": [
            {"action": {k: v for k, v in t.action.model_dump().items()
                        if k in ("value", "value_ref")},
             "verify_effect": t.verify_effect.model_dump() if t.verify_effect else None}
            for t in a.transitions],
        "states": [s.checkpoint.model_dump() if s.checkpoint else None for s in a.states],
        "watchers": [{"trigger": w.trigger.model_dump(),
                      "extract": {k: v.model_dump() for k, v in w.extract.items()}}
                     for w in a.watchers],
    }

    # 1. A value used during discovery must not survive anywhere in the flow.
    for name, example in a.provenance.example_values.items():
        if not example:
            continue
        for path, text in _strings(flow):
            if path.endswith(("target", "into")):
                continue          # a reference to a Target is a name, not data
            if example in text:
                issues.append(
                    Issue("discovery_literal", path,
                          f"the discovery value {example!r} for {name!r} survived; "
                          f"it should be {{{{{name}}}}}")
                )

    # 2. Every placeholder must name a declared input.
    for path, text in _strings(flow):
        for ref in PLACEHOLDER.findall(text):
            if ref not in a.contract.inputs:
                issues.append(Issue("unknown_placeholder", path, f"no input named {ref!r}"))

    # 3/4. Outcomes and the Watchers that produce them must agree.
    for w in a.watchers:
        if w.outcome and w.outcome not in declared_outcomes:
            issues.append(Issue("undeclared_outcome", f"watcher {w.id}",
                                f"{w.outcome!r} is not in the contract"))
    for code in declared_outcomes - produced_outcomes:
        issues.append(Issue("unreachable_outcome", "contract",
                            f"{code!r} is declared but no watcher can produce it"))

    # 4b. A Watcher's text trigger must be able to name a screen. One letter matches
    #     nearly every page, so a business outcome would be reported at random.
    for w in a.watchers:
        value = getattr(w.trigger, "value", None)
        if w.trigger.type == "text_present" and value is not None and len(value.strip()) < MIN_TRIGGER_TEXT:
            issues.append(Issue("weak_trigger", f"watcher {w.id}",
                                f"text {value!r} is too short to identify a screen "
                                f"(fewer than {MIN_TRIGGER_TEXT} characters)"))

    # 5. Only a terminal state may lack a checkpoint.
    for s in a.states:
        if s.checkpoint is None and s.terminal is None:
            issues.append(Issue("missing_checkpoint", f"state {s.id}",
                                "a non-terminal state must assert where it is"))

    # 6/7. References must resolve.
    for t in a.transitions:
        where = f"transition {t.from_state}->{t.to_state}"
        for sid in (t.from_state, t.to_state):
            if sid not in state_ids:
                issues.append(Issue("unknown_state", where, f"no state {sid!r}"))
        target = getattr(t.action, "target", None)
        if target and target not in target_ids:
            issues.append(Issue("unknown_target", where, f"no target {target!r}"))
        ref = getattr(t.action, "value_ref", None)
        if ref and ref not in a.needs.secrets:
            issues.append(Issue("undeclared_secret", where,
                                f"{ref!r} is used but not declared in needs.secrets"))
    for w in a.watchers:
        target = getattr(w.recovery, "target", None) if w.recovery else None
        if target and target not in target_ids:
            issues.append(Issue("unknown_target", f"watcher {w.id}", f"no target {target!r}"))

    # 8. Consequential steps: verification is what makes unattended use safe.
    consequential = [t for t in a.transitions if t.risk == "consequential"]
    if unattended:
        for t in consequential:
            if t.verify_effect is None:
                issues.append(
                    Issue("consequential_without_verification",
                          f"transition {t.from_state}->{t.to_state}",
                          "without one, an unclear screen after this commit can only be "
                          "Outcome Unknown")
                )

    # 9. Needs must fit inside the declared Role.
    try:
        role = get_role(a.capability.vendor_app, a.capability.role)
    except UnknownRole as exc:
        issues.append(Issue("unknown_role", "capability", str(exc)))
    else:
        for page in a.needs.pages:
            if not covers(role.get("pages", []), page):
                issues.append(Issue("needs_exceed_role", "needs.pages",
                                    f"{page!r} is outside role {a.capability.role!r}"))
        for action in a.needs.actions:
            if action not in role.get("actions", []):
                issues.append(Issue("needs_exceed_role", "needs.actions",
                                    f"{action!r} is outside role {a.capability.role!r}"))
        for secret in a.needs.secrets:
            if secret not in role.get("secrets", []):
                issues.append(Issue("needs_exceed_role", "needs.secrets",
                                    f"{secret!r} is outside role {a.capability.role!r}"))
        if consequential and role.get("consequential") == "forbidden":
            issues.append(Issue("role_forbids_consequential", "capability",
                                f"role {a.capability.role!r} may not commit anything"))

    # 10. Approval state.
    if unattended and a.capability.status != "approved":
        issues.append(Issue("not_approved", "capability",
                            f"status is {a.capability.status!r}; unattended replay needs 'approved'"))
    if consequential and len(a.capability.approvals) < 2:
        issues.append(Issue("needs_two_person_approval", "capability",
                            "an artifact that commits needs two named reviewers"))

    return issues
