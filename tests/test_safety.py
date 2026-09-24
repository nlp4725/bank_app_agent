"""The guardrails, and the tests that are themselves controls.

Permissions are Baseline ∩ Role ∩ Tenant grant ∩ Needs; the first three are files
owned by different people, and the fourth is derived from what a run actually did.
"""

import ast
import json
from pathlib import Path

import pytest

from cua.domain.artifact import AppProfile, Artifact, merged
from cua.governance.profile import load_profile
from cua.replay.engine import RunContext, replay
from cua.governance.policy import Policy, load_baseline, load_tenant_policy

from .fixtures import artifact_dict

INPUTS = {"member_number": "12345", "account_type": "savings", "nickname": "Holiday fund"}
CUA = Path(__file__).resolve().parent.parent / "cua"


# ── the front door ────────────────────────────────────────────────────────────

def test_a_capability_whose_role_the_tenant_has_not_granted_is_refused(artifact, bank_app):
    r = replay(artifact, INPUTS, RunContext(origin=bank_app, tenant="bank_b"))
    assert r.status == "refused"
    assert "account_opener" in r.reason


def test_needs_outside_the_tenants_grant_are_refused(artifact, bank_app):
    d = artifact_dict()
    d["needs"]["pages"] = d["needs"]["pages"] + ["/transfers/*"]
    art = merged(Artifact.model_validate(d), load_profile("demo-core-servicing"))
    r = replay(art, INPUTS, RunContext(origin=bank_app))
    assert r.status == "refused"
    assert "/transfers/*" in r.reason


def test_an_action_type_the_baseline_forbids_is_refused(artifact, bank_app):
    d = artifact_dict()
    d["needs"]["actions"] = d["needs"]["actions"] + ["download"]
    art = merged(Artifact.model_validate(d), load_profile("demo-core-servicing"))
    r = replay(art, INPUTS, RunContext(origin=bank_app))
    assert r.status == "refused"
    assert "download" in r.reason


def test_the_refusal_names_the_layer_that_refused(artifact, bank_app):
    r = replay(artifact, INPUTS, RunContext(origin=bank_app, tenant="bank_b"))
    assert "tenant" in r.reason.lower()


# ── policy layering, without a browser ───────────────────────────────────────

def test_a_tenant_may_narrow_the_baseline_never_widen_it():
    baseline = load_baseline()
    tenant = load_tenant_policy("bank_a", "demo-core-servicing")
    policy = Policy(baseline=baseline, tenant=tenant, role_name="account_opener",
                    vendor_app="demo-core-servicing")
    assert policy.allows_action("click")
    assert not policy.allows_action("download")       # the baseline forbids it
    assert policy.allows_page("/members/12345")
    assert not policy.allows_page("/admin")           # keyword deny plus route allowlist


def test_a_read_only_role_may_not_commit():
    baseline = load_baseline()
    tenant = load_tenant_policy("bank_a", "demo-core-servicing")
    policy = Policy(baseline=baseline, tenant=tenant, role_name="balance_reader",
                    vendor_app="demo-core-servicing")
    assert policy.consequential_allowed() is False
    assert policy.service_account() == "svc_read"


# ── mid-run enforcement ───────────────────────────────────────────────────────

def test_a_url_outside_the_origin_is_asked_about_whole_and_denied():
    """One rule for both workflows. Discovery used to slice the URL by the origin's
    length, so a foreign URL could yield a path that happened to match."""
    from cua.governance.policy import route_of
    assert route_of("http://127.0.0.1:5001/members/12345", "http://127.0.0.1:5001") == "/members/12345"
    assert route_of("http://127.0.0.1:5001", "http://127.0.0.1:5001/") == "/"
    foreign = route_of("http://attacker.example/members/12345", "http://127.0.0.1:5001")
    assert foreign == "http://attacker.example/members/12345"
    policy = Policy(baseline=load_baseline(), tenant=load_tenant_policy("bank_a", "demo-core-servicing"),
                    role_name="account_opener", vendor_app="demo-core-servicing")
    assert not policy.allows_page(foreign)


def test_a_request_to_another_origin_is_aborted_in_the_browser(bank_app):
    """The page, not us, starts this one: an <img> pointing off-site.

    A check before we act cannot see it, so the allowlist is enforced on every
    request the browser makes.
    """
    from cua.surface import Surface
    surface = Surface(bank_app)
    try:
        surface.goto("/leaky")
        surface.page.wait_for_timeout(800)
        blocked = surface.blocked_requests
        assert any("attacker.example" in url for url in blocked), blocked
    finally:
        surface.close()


# ── redaction ─────────────────────────────────────────────────────────────────

def test_the_balance_reaches_the_caller_in_full_and_the_record_masked(artifact, bank_app, tmp_path):
    r = replay(artifact, INPUTS, RunContext(origin=bank_app, evidence_root=str(tmp_path)))
    assert r.outputs["savings_balance"] == "$4210.00"        # the answer is the product
    written = (Path(r.evidence_id) / "trail.jsonl").read_text()
    assert "$4210.00" not in written                          # the record of it is not


def test_no_secret_value_appears_anywhere_in_the_evidence(artifact, bank_app, tmp_path):
    r = replay(artifact, INPUTS, RunContext(origin=bank_app, evidence_root=str(tmp_path)))
    for path in Path(r.evidence_id).rglob("*"):
        if path.is_file() and path.suffix in (".jsonl", ".json", ".txt"):
            body = path.read_text()
            assert "officer-pw" not in body
            assert "svc_officer" not in body


def test_every_policy_decision_is_recorded(artifact, bank_app, tmp_path):
    r = replay(artifact, INPUTS, RunContext(origin=bank_app, evidence_root=str(tmp_path)))
    decisions = [json.loads(line) for line in
                 (Path(r.evidence_id) / "trail.jsonl").read_text().splitlines()]
    assert any(d["event"] == "policy_allow" for d in decisions)


# ── tests that are controls ───────────────────────────────────────────────────
#
# The boundaries are asserted over the whole package, wherever a file lives. LAYOUT
# says where each concern is; a move changes one row here and nothing else. Every
# row must name at least one real file, so a rule can never pass by finding nothing —
# which is what the flat-layout version of these tests would have done the moment a
# module moved into a package.

LAYOUT = {
    "domain": "domain",               # pure: no file, browser, model or clock
    "replay_entry": "replay/engine.py",       # a Production Replay starts here; it reaches only what this reaches
    "predicates": "replay/predicates.py",
    "discovery": ["discovery.py"],     # the only files that may import a model SDK
    "surface": ["surface"],            # the only files that may import playwright
}

MODEL_SDKS = {"anthropic", "openai", "google", "litellm"}
NOT_IN_DOMAIN = MODEL_SDKS | {"playwright", "yaml", "os", "sys", "pathlib", "json", "shutil",
                              "subprocess", "time", "datetime", "uuid", "flask"}


def sources() -> set[Path]:
    return set(CUA.rglob("*.py"))


def under(key: str) -> set[Path]:
    """The files a LAYOUT row names: a file, or every file below a directory."""
    entries = LAYOUT[key]
    found = set()
    for entry in (entries if isinstance(entries, list) else [entries]):
        path = CUA / entry
        if path.is_file():
            found.add(path)
        elif path.is_dir():
            found.update(path.rglob("*.py"))
    return found


def rel(path: Path) -> str:
    return str(path.relative_to(CUA.parent))


def _module_file(base: Path, dotted: str) -> Path | None:
    """The file a dotted name resolves to from `base`: x/y.py, or x/y/__init__.py."""
    path = base.joinpath(*dotted.split(".")) if dotted else base
    if path.with_suffix(".py").is_file():
        return path.with_suffix(".py")
    if (path / "__init__.py").is_file():
        return path / "__init__.py"
    return None


def imports_of(path: Path) -> tuple[set[str], set[Path]]:
    """(external top-level packages, cua files) this file imports — at module level
    or inside a function, absolute or relative."""
    externals: set[str] = set()
    internal: set[Path] = set()

    def internal_from(base: Path, module: str, names) -> None:
        found = _module_file(base, module)
        if found is not None:
            internal.add(found)
        for alias in names:                 # `from .replay import engine` names a module
            sub = _module_file(base, f"{module}.{alias.name}" if module else alias.name)
            if sub is not None:
                internal.add(sub)

    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top, _, rest = alias.name.partition(".")
                if top == "cua":
                    internal_from(CUA, rest, [])
                else:
                    externals.add(top)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = path.parent
                for _ in range(node.level - 1):
                    base = base.parent
                internal_from(base, node.module or "", node.names)
            elif node.module:
                top, _, rest = node.module.partition(".")
                if top == "cua":
                    internal_from(CUA, rest, node.names)
                else:
                    externals.add(top)
    return externals, internal


def reachable(entry: Path) -> set[Path]:
    """Every cua file reachable from `entry`, transitively."""
    seen, queue = set(), [entry]
    while queue:
        path = queue.pop()
        if path in seen:
            continue
        seen.add(path)
        queue.extend(imports_of(path)[1])
    return seen


def replay_entry() -> Path:
    (entry,) = under("replay_entry")
    return entry


def test_the_layout_names_files_that_exist():
    for key in LAYOUT:
        assert under(key), f"LAYOUT[{key!r}] names no file, so the rules below would check nothing"


def test_the_domain_imports_nothing_that_does_anything():
    """Models and rules only: no file, browser, model, clock or framework. And nothing
    from the rest of cua, so the domain cannot depend on the code that uses it."""
    for path in under("domain"):
        externals, internal = imports_of(path)
        assert not (externals & NOT_IN_DOMAIN), f"{rel(path)} imports {externals & NOT_IN_DOMAIN}"
        outside = internal - under("domain")
        assert not outside, f"{rel(path)} imports {sorted(map(rel, outside))}"


def test_replay_cannot_reach_a_model_sdk():
    """Not 'no file imports it' — the replay path cannot reach it, transitively."""
    for path in reachable(replay_entry()):
        assert not (imports_of(path)[0] & MODEL_SDKS), \
            f"replay reaches {rel(path)}, which imports a model SDK"


def test_the_model_sdk_lives_only_in_discovery():
    users = {p for p in sources() if imports_of(p)[0] & MODEL_SDKS}
    assert users, "nothing imports a model SDK: the rule has nothing to check"
    outside = users - under("discovery")
    assert not outside, f"unexpected model SDK users: {sorted(map(rel, outside))}"


def test_discovery_is_not_reachable_from_replay():
    crossed = reachable(replay_entry()) & under("discovery")
    assert not crossed, f"replay reaches discovery: {sorted(map(rel, crossed))}"


def test_no_import_hides_inside_a_function():
    """Every dependency is visible at the top of the file. An import inside a function
    is a cycle waiting to be found by the next move: it passes the rules above (they
    walk the whole AST) and still surprises whoever relocates the module."""
    for path in sources():
        tree = ast.parse(path.read_text())
        nested = [n.lineno for f in ast.walk(tree)
                  if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))
                  for n in ast.walk(f) if isinstance(n, (ast.Import, ast.ImportFrom))]
        assert not nested, f"{rel(path)}:{nested} imports inside a function"


def test_only_the_surface_module_touches_playwright():
    for path in sources() - under("surface"):
        assert "playwright" not in imports_of(path)[0], f"{rel(path)} imports playwright"


def test_a_locator_never_leaves_the_surface():
    """controls() and values() carry the driver's locator so the surface can act on
    them later. Nothing above the seam may touch it: discovery used to call
    `c["locator"].input_value()`, a driver method, and the attribute guard above
    could not see it because the name was not `surface`."""
    for path in sources() - under("surface"):
        hits = [n.lineno for n in ast.walk(ast.parse(path.read_text()))
                if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant)
                and n.slice.value == "locator"]
        assert not hits, f"{rel(path)}:{hits} reaches into a locator"


# ── the Surface seam: two interfaces, and nothing reaching past them ──────────

ACTING = {"origin", "allowed_origins", "blocked_requests", "url", "goto", "text",
          "wait", "close", "screenshot", "resolve", "click", "type", "select",
          "read", "value_of", "frame_urls"}


def _attributes_used_on(paths, variable):
    """Every `variable.X` across these files, statically."""
    used = set()
    for path in paths:
        tree = ast.parse(Path(path).read_text())
        used |= {n.attr for n in ast.walk(tree)
                 if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                 and n.value.id == variable}
    return used


def test_the_replay_path_uses_only_the_acting_interface():
    """Not 'it happens to work' — the engine may not reach for a driver object.

    This is the assertion that makes a scripted Surface possible: the engine used to
    read `surface.page.frames` and call the private `_tick`.
    """
    used = _attributes_used_on(under("replay_entry"), "surface")
    assert used <= ACTING, f"the engine reaches past the acting interface: {used - ACTING}"


def test_the_predicate_evaluator_needs_only_four_observations():
    used = _attributes_used_on(under("predicates"), "surface")
    assert used <= {"text", "url", "resolve", "value_of", "wait", "goto"}, used


def test_the_recording_interface_does_not_offer_the_acting_one():
    """A Discovery Run enumerates and describes; it does not get a driver handle."""
    from cua.surface import RecordingSurface
    for name in ("resolve", "click", "type", "select", "read", "value_of", "page"):
        assert not hasattr(RecordingSurface, name), \
            f"RecordingSurface exposes {name!r}, so the union interface is back"


def test_discovery_acts_through_the_recording_interface_not_on_a_locator():
    used = _attributes_used_on(under("discovery"), "surface")
    assert "act_on" in used
    assert not ({"click", "type", "select", "read", "page"} & used), used
