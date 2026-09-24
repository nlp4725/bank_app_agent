"""What a Reviewer hands to discovery, and what comes back.

`request_from_spec` is how a Discovery Request file — the Contract a Reviewer approved,
plus this run's values — becomes what `discover()` receives. Both tools build one
this way, so there is one rule for it.
"""

from dataclasses import dataclass, field

from ..domain.artifact import AppProfile
from ..governance.policy import Policy, policy_for_role
from ..governance.profile import load_profile
from ..governance.store import origin_for
from ..secrets import secrets_for


@dataclass
class DiscoveryRequest:
    """What the Reviewer hands to discovery: a goal in words, plus the Contract."""
    goal: str
    vendor_app: str
    role: str
    contract: dict
    example_values: dict
    tenant: str = "bank_a"
    origin: str = "http://127.0.0.1:5001"
    app_profile: AppProfile | None = None
    evidence_root: str = "runs"
    headless: bool = True
    secrets: object | None = None
    # The model that answers each turn. None means the real one (discovery/model.py);
    # a scripted stand-in is how the loop is tested without a key.
    model: object | None = None
    # Masking is ON, in layers (see CONTEXT.md, "Redaction"):
    #   structural — a password is never read, whatever is declared
    #   origin     — a value is hidden unless its caption is a Readable Region
    #   pattern    — what does flow through still passes the net
    #   pixels     — declared Sensitive Regions are painted black at capture
    # Pixels stay a deny-list: blacking out an undeclared control would blind the model.
    mask_values: bool = True
    mask_pixels: bool = True
    verbose: bool = False      # narrate each turn to the console
    slow_mo_ms: int = 0        # pace actions so a person can follow along
    # The Recorder is code and decides nothing, so it runs as soon as a successful run
    # finishes: a draft Artifact lands beside the trace. Approval stays with a person.
    compile_draft: bool = True
    capability_id: str = ""
    role_for_artifact: str = ""


@dataclass
class DiscoveryResult:
    ending: str
    run_id: str
    trace_dir: str
    turns: int
    outputs: dict = field(default_factory=dict)
    outcome: str | None = None
    detail: str | None = None
    actions: list = field(default_factory=list)
    draft: str | None = None                 # written when the run reached the goal
    suggestions: list = field(default_factory=list)

    def __str__(self):
        bits = [self.ending, f"{self.turns} turns"]
        if self.outcome:
            bits.append(self.outcome)
        if self.detail:
            bits.append(self.detail)
        return " · ".join(bits)


def policy_for_request(request: DiscoveryRequest) -> Policy:
    return policy_for_role(request.vendor_app, request.role, request.tenant)


def default_secrets(policy: Policy):
    return secrets_for(policy.service_account())


class _Keep(dict):
    """`{member_number}` is filled; a brace the values do not name is left as written,
    so a goal can mention something that is not an input without crashing."""
    def __missing__(self, key):
        return "{" + key + "}"


def render_goal(goal: str, values: dict) -> str:
    return goal.format_map(_Keep(values))


def request_from_spec(spec: dict, values: dict, *, tenant: str = "bank_a",
                      headed: bool = False, slowmo: int = 0, goal: str | None = None,
                      role: str | None = None, capability: str | None = None) -> DiscoveryRequest:
    """A Discovery Request file plus this run's values -> what discovery receives.
    Shared by the flag-driven tool and the interactive one."""
    vendor_app = spec["vendor_app"]
    return DiscoveryRequest(
        goal=render_goal(goal or spec["goal"], values),
        vendor_app=vendor_app,
        role=role or spec["role"],
        contract=spec["contract"],
        example_values=values,
        tenant=tenant,
        origin=origin_for(tenant, vendor_app),
        app_profile=load_profile(vendor_app),
        headless=not headed,
        verbose=True,
        capability_id=capability or spec["capability_id"],
        slow_mo_ms=slowmo,
    )
