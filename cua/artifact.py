"""The Artifact schema.

Everything an Artifact may say is drawn from a closed vocabulary: the engine
implements exactly these actions, predicates and target rungs, so an Artifact
cannot express an action the engine has no function for. See ADR 0001.
"""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ── Predicates: machine-checkable claims about the screen ─────────────────────

class ElementPresent(Strict):
    type: Literal["element_present"]
    target: str
    timeout_ms: int | None = None


class ElementAbsent(Strict):
    type: Literal["element_absent"]
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


class CountIs(Strict):
    type: Literal["count"]
    target: str
    equals: int


class AllOf(Strict):
    type: Literal["all"]
    of: list["Predicate"]


class AnyOf(Strict):
    type: Literal["any"]
    of: list["Predicate"]


Predicate = Annotated[
    Union[ElementPresent, ElementAbsent, TextPresent, FieldValue, UrlMatches, CountIs, AllOf, AnyOf],
    Field(discriminator="type"),
]


# ── Target rungs: ways to find a control, strongest first ─────────────────────

class RoleName(Strict):
    kind: Literal["role_name"]
    role: str
    name: str


class RightOfText(Strict):
    kind: Literal["right_of_text"]
    anchor: str
    role: str | None = None


class PictureMatch(Strict):
    kind: Literal["picture"]
    asset: str
    threshold: float = 0.94


TargetRung = Annotated[Union[RoleName, RightOfText, PictureMatch], Field(discriminator="kind")]


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


class WaitFor(Strict):
    type: Literal["wait"]
    predicate: Predicate | None = None
    ms: int | None = None


class Scroll(Strict):
    type: Literal["scroll"]
    target: str | None = None


Action = Annotated[
    Union[Click, TypeText, SelectOption, ReadValue, WaitFor, Scroll], Field(discriminator="type")
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
    """How to find out whether a Consequential Step already took effect."""
    goto: str | None = None
    predicate: Predicate


class Transition(Strict):
    from_state: str
    to_state: str
    action: Action
    risk: Literal["safe", "consequential"] = "consequential"
    precondition: Predicate | None = None
    timeout_ms: int | None = None
    retry: Retry | None = None
    verify_effect: VerifyEffect | None = None
    risk_suggestion: str | None = None  # the Discovery LLM's advice, never the decision


class Watcher(Strict):
    id: str
    trigger: Predicate
    condition: Literal["business_outcome", "recoverable", "escalate", "hard_failure"]
    outcome: str | None = None
    recovery: Action | None = None
    budget: int | None = None
    extract: dict[str, dict] = Field(default_factory=dict)
    reason: str | None = None
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
    targets: dict[str, list[TargetRung]]
    watchers: list[Watcher] = Field(default_factory=list)
    provenance: Provenance = Field(default_factory=Provenance)

    def state(self, state_id: str) -> State | None:
        return next((s for s in self.states if s.id == state_id), None)
