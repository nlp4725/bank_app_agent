"""The rung ladder: how a Target is found on a live page.

Each rung is tried in order and the first that resolves wins; the driver records
which. `role_name` asks the accessibility tree; `label_anchor` finds the words, then
the nearest control in the given relation — geometry over bounding boxes, not DOM
structure, so the same idea works on a desktop accessibility tree or on OCR over a
screenshot. See docs/targeting.md. `picture` is not implemented and falls through.

`score` is the geometry alone, over two boxes, so it can be tested without a page.
"""

INTERACTIVE_FALLBACK = "td, span, div, p, strong, b"

SAME_LINE_SLACK = 14      # px: two boxes whose centres differ by less share a line
OVERLAP_SLACK = 2         # px: a control may start this far before its anchor ends


def score(relation: str, anchor: dict, candidate: dict) -> float:
    """How well `candidate` sits in `relation` to `anchor`. Lower is better; inf means
    it does not qualify at all. Boxes are {x, y, width, height}."""
    a, b = anchor, candidate
    same_line = abs((b["y"] + b["height"] / 2) - (a["y"] + a["height"] / 2)) < max(a["height"], SAME_LINE_SLACK)
    dx = b["x"] - (a["x"] + a["width"])
    dy = b["y"] - (a["y"] + a["height"])
    if relation == "right_of":
        return dx if (same_line and dx >= -OVERLAP_SLACK) else float("inf")
    if relation == "below":
        overlap = not (b["x"] + b["width"] < a["x"] or b["x"] > a["x"] + a["width"])
        return dy if (overlap and dy >= -OVERLAP_SLACK) else float("inf")
    return abs(dx) + abs(dy)          # nearest


def try_rung(scope, rung):
    try:
        if rung.kind == "role_name":
            loc = scope.get_by_role(rung.role, name=rung.name, exact=True)
            return loc.first if loc.count() else None
        if rung.kind == "label_anchor":
            return by_anchor(scope, rung)
        if rung.kind == "picture":
            return None      # template matching: not implemented; falls through
    except Exception:
        return None
    return None


def by_anchor(scope, rung):
    """Find the words, then the nearest control in the given relation.

    Geometry, not DOM structure — the same idea works on a desktop accessibility
    tree or on OCR over a screenshot. See docs/targeting.md.
    """
    anchor = scope.get_by_text(rung.anchor, exact=True)
    if not anchor.count():
        return None
    a = anchor.first.bounding_box()
    if not a:
        return None

    candidates = scope.get_by_role(rung.role) if rung.role else scope.locator(INTERACTIVE_FALLBACK)
    best, best_score = None, float("inf")
    for i in range(min(candidates.count(), 200)):
        c = candidates.nth(i)
        try:
            b = c.bounding_box()
        except Exception:
            continue
        if not b or b["width"] == 0:
            continue
        if rung.role is None:
            try:
                if not c.inner_text().strip() or c.inner_text().strip() == rung.anchor:
                    continue
                if c.locator(INTERACTIVE_FALLBACK).count():
                    continue        # prefer the innermost element holding the text
            except Exception:
                continue

        s = score(rung.relation, a, b)
        if s < best_score:
            best, best_score = c, s
    return best
