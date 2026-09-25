"""Tests that are themselves controls: the import graph and the seams, asserted over
the whole package so a file that moves cannot slip out from under a rule.

Every boundary the package claims — the domain is pure, replay cannot reach a model
SDK, only the surface touches the browser, nothing reaches past the acting interface —
is a test here, not a sentence in a document.
"""

import ast
from pathlib import Path

from cua.replay.context import ActingSurface, members

CUA = Path(__file__).resolve().parents[2] / "cua"


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
    "discovery": ["discovery"],        # a model is in the loop here and nowhere else
    "model": ["discovery/model.py"],   # the only file that may import a model SDK
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
    outside = users - under("model")
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

ACTING = members(ActingSurface)


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


# ── the test tiers ────────────────────────────────────────────────────────────

TESTS = CUA.parent / "tests"
APP_FIXTURES = {"bank_app", "bank2_app", "approved"}


def test_nothing_under_unit_asks_for_the_demo_app():
    """`pytest tests/unit` runs in seconds with nothing listening, because conftest
    starts the demo app on first use and nothing here uses it. A test that needs the
    app belongs in tests/app/."""
    offenders = []
    for path in sorted((TESTS / "unit").glob("test_*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                asked = {a.arg for a in node.args.args} & APP_FIXTURES
                if asked:
                    offenders.append(f"{path.name}::{node.name} asks for {sorted(asked)}")
    assert not offenders, "\n".join(offenders)


def test_every_test_file_is_named_after_the_module_it_tests():
    """An outsider finds the tests of cua/<package>/<module>.py at
    tests/<tier>/<package>/test_<module>.py, and the tests of a package at
    tests/<tier>/<package>/ — without a table. A second file about the same module
    is test_<module>_<story>.py. This file is the one exception: it is about the
    package as a whole."""
    roots = {"cua": CUA, "tools": CUA.parent / "tools"}
    wrong = []
    for tier in ("unit", "app"):
        for path in sorted((TESTS / tier).rglob("test_*.py")):
            rel = path.relative_to(TESTS / tier)
            if str(rel) == "test_boundaries.py":
                continue
            parts = list(rel.parts)
            root = roots["tools"] if parts[0] == "tools" else roots["cua"]
            package = root.joinpath(*(parts[1:-1] if parts[0] == "tools" else parts[:-1]))
            modules = {q.stem for q in package.glob("*.py") if q.stem != "__init__"} if package.is_dir() else set()
            name = rel.stem[len("test_"):]
            if not any(name == m or name.startswith(m + "_") for m in modules):
                wrong.append(f"{tier}/{rel}: no module {name!r} in {package.relative_to(CUA.parent)}/")
    assert not wrong, "\n".join(wrong)
