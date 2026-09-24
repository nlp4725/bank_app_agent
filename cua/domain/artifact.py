"""The Artifact schema.

Everything an Artifact may say is drawn from a closed vocabulary: the engine
implements exactly these actions, predicates and target rungs, so an Artifact
cannot express an action the engine has no function for. See ADR 0001.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    # populate_by_name so a model can round-trip through model_dump() as well as
    # through its aliases ("from" is a keyword, so the field is from_).
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# ── Predicates: machine-checkable claims about the screen ─────────────────────

class ElementPresent(Strict):
    type: Literal["element_present"]
    target: str
    timeout_ms: int | None = None


class TextPresent(Strict):
    type: Literal["text_present"]
    value: str


class FieldValue(Strict):
    type: Literal["field_value"]
    target: str
    equals: str | None = None
    non_empty: bool | None = None


class UrlMatches(Strict):
    type: Literal["url_matches"]
    pattern: str


class AllOf(Strict):
    type: Literal["all"]
    of: list["Predicate"]


class AnyOf(Strict):
    type: Literal["any"]
    of: list["Predicate"]


Predicate = Annotated[
    ElementPresent | TextPresent | FieldValue | UrlMatches | AllOf | AnyOf,
    Field(discriminator="type"),
]


# ── Target rungs: ways to find a control, strongest first ─────────────────────

class RoleName(Strict):
    kind: Literal["role_name"]
    role: str
    name: str


class LabelAnchor(Strict):
    """Find the visible words, then the nearest control of `role` in `relation`.

    Stores the relationship, never a measured distance: see docs/targeting.md.
    """
    kind: Literal["label_anchor"]
    anchor: str
    role: str | None = None
    relation: Literal["right_of", "below", "nearest"] = "right_of"


class PictureMatch(Strict):
    kind: Literal["picture"]
    asset: str
    threshold: float = 0.94


TargetRung = Annotated[RoleName | LabelAnchor | PictureMatch, Field(discriminator="kind")]


class FrameRef(Strict):
    """Which document to look in. Absent means the main one."""
    url_contains: str


class Target(Strict):
    frame: FrameRef | None = None
    rungs: list[TargetRung]
    description: str | None = None


# ── Actions: the engine's entire vocabulary ───────────────────────────────────

class Click(Strict):
    type: Literal["click"]
    target: str


class TypeText(Strict):
    type: Literal["type"]
    target: str
    value: str | None = None
    value_ref: str | None = None

    @model_validator(mode="after")
    def exactly_one_source(self):
        if (self.value is None) == (self.value_ref is None):
            raise ValueError("a type action needs exactly one of value or value_ref")
        return self


class SelectOption(Strict):
    type: Literal["select"]
    target: str
    value: str


class ReadValue(Strict):
    type: Literal["read"]
    target: str
    into: str


Action = Annotated[
    Click | TypeText | SelectOption | ReadValue, Field(discriminator="type")
]


# ── Contract: what the Calling Agent depends on ───────────────────────────────

class InputSpec(Strict):
    type: str
    pattern: str | None = None
    values: list[str] | None = None
    max_length: int | None = None
    sensitive: bool = False
    required: bool = True


class OutputSpec(Strict):
    type: str
    sensitive: bool = False


class OutcomeSpec(Strict):
    code: str
    meaning: str
    resolver: Literal["member", "institution_staff", "nobody"]
    caller_hint: str | None = None
    retry_same_inputs: Literal["never"] = "never"
    data: dict[str, dict] = Field(default_factory=dict)


class Contract(Strict):
    inputs: dict[str, InputSpec] = Field(default_factory=dict)
    outputs: dict[str, OutputSpec] = Field(default_factory=dict)
    outcomes: list[OutcomeSpec] = Field(default_factory=list)


# ── Flow ──────────────────────────────────────────────────────────────────────

class State(Strict):
    id: str
    checkpoint: Predicate | None = None
    terminal: Literal["succeeded"] | None = None
    description: str | None = None


class Retry(Strict):
    max: int
    backoff_ms: int = 500


class VerifyEffect(Strict):
    """How to find out whether a Consequential Action already took effect."""
    goto: str | None = None
    predicate: Predicate


class Transition(Strict):
    from_state: str
    to_state: str
    action: Action
    risk: Literal["safe", "consequential"] = "consequential"
    timeout_ms: int | None = None
    retry: Retry | None = None
    verify_effect: VerifyEffect | None = None
    risk_suggestion: str | None = None  # the Discovery LLM's advice, never the decision


class Extract(Strict):
    """What a Watcher may return from the screen: a declared capture group, never
    free page text. Allowlist by construction — see CONTEXT.md, "Redaction"."""
    from_: Literal["regex"] = Field(default="regex", alias="from")
    pattern: str

    @model_validator(mode="after")
    def must_capture(self):
        if "(" not in self.pattern or ")" not in self.pattern:
            raise ValueError("an extract pattern must contain a capture group")
        return self


class Watcher(Strict):
    id: str
    trigger: Predicate
    condition: Literal["business_outcome", "recoverable", "escalate", "hard_failure"]
    outcome: str | None = None
    recovery: Action | None = None
    budget: int | None = None
    resume_at: str | None = None   # which State to continue from after a recovery
    extract: dict[str, Extract] = Field(default_factory=dict)
    reason: str | None = None
    # What to tell the Operator, in their words. Data, so a Reviewer writes it once
    # and every escalation on this screen says the same thing.
    operator_instruction: str | None = None
    provenance: str


class Capability(Strict):
    id: str
    version: str
    vendor_app: str
    role: str
    status: Literal["draft", "approved", "disabled"] = "draft"
    approvals: list[str] = Field(default_factory=list)
    description: str | None = None


class Needs(Strict):
    pages: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    secrets: list[str] = Field(default_factory=list)


class Provenance(Strict):
    discovered_by: str | None = None
    contract_by: str | None = None
    example_values: dict[str, str] = Field(default_factory=dict)


class Artifact(Strict):
    schema_version: int
    capability: Capability
    contract: Contract
    needs: Needs
    states: list[State]
    transitions: list[Transition]
    targets: dict[str, Target]
    watchers: list[Watcher] = Field(default_factory=list)
    provenance: Provenance = Field(default_factory=Provenance)

    def state(self, state_id: str) -> State | None:
        return next((s for s in self.states if s.id == state_id), None)


class AppProfile(Strict):
    """What every capability on one vendor app shares.

    Session expiry, interstitials and error pages are properties of the app, not of
    any one capability: learnt once, they reach every Artifact. See CONTEXT.md.
    """
    app_profile: str
    watchers: list[Watcher] = Field(default_factory=list)
    targets: dict[str, Target] = Field(default_factory=dict)
    # Masking is declared data, not code. The two channels take opposite defaults,
    # deliberately: hiding a VALUE costs nothing (the model needs structure, not
    # contents), but blacking out a CONTROL would blind it to something it must use.
    readable_regions: list[str] = Field(default_factory=list)   # values: allowlist (by Target)
    sensitive_regions: list[str] = Field(default_factory=list)  # pixels: painted black
    # During discovery there are no Targets yet, so the same allowlist is expressed by
    # the caption a human reads beside the value.
    readable_anchors: list[str] = Field(default_factory=list)
    # On-screen text that is not a value cell but must not be in a picture: regexes,
    # painted black at capture (a member number in a page heading).
    sensitive_text: list[str] = Field(default_factory=list)


def merged(artifact: Artifact, profile: AppProfile | None) -> Artifact:
    """App-wide watchers and targets, with the Artifact's own winning on a clash."""
    if profile is None:
        return artifact
    if profile.app_profile != artifact.capability.vendor_app:
        raise ValueError(
            f"profile {profile.app_profile!r} does not match app {artifact.capability.vendor_app!r}"
        )
    data = artifact.model_dump(mode="python")
    own_watchers = {w["id"] for w in data["watchers"]}
    data["watchers"] = [w for w in profile.model_dump(mode="python")["watchers"]
                        if w["id"] not in own_watchers] + data["watchers"]
    for name, target in profile.model_dump(mode="python")["targets"].items():
        data["targets"].setdefault(name, target)
    return Artifact.model_validate(data)
