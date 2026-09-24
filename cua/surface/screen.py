"""Enumerating a screen for a Discovery Run: every control a person could act on,
every label/value pair they could read, and the durable description of what was
acted on. Record-time only; replay never asks for any of this.

Each dict carries the driver's locator so the driver can act on it later. Nothing
above the surface package may touch that key (a boundary test says so).
"""

INTERACTIVE = ("button", "textbox", "link", "combobox", "checkbox", "radio")


def controls(page) -> list[dict]:
    """Every control a person could act on, main document and frames.

    Controls with no accessible name are the interesting ones: we annotate them
    with the nearest text to their left, which is what a human reads instead.
    """
    found = []
    for frame in page.frames:
        for role in INTERACTIVE:
            loc = frame.get_by_role(role)
            for i in range(min(loc.count(), 40)):
                el = loc.nth(i)
                try:
                    box = el.bounding_box()
                    if not box or box["width"] == 0:
                        continue
                    name = (el.get_attribute("aria-label")
                            or el.inner_text().strip()
                            or el.get_attribute("value") or "")
                    found.append({
                        "index": len(found) + 1,
                        "role": role,
                        "name": name,
                        "anchor": nearest_text(frame, box),
                        "is_password": (el.get_attribute("type") == "password"),
                        "frame_url": frame.url,
                        "box": box,
                        "locator": el,
                    })
                except Exception:
                    continue
    return found


def values(page, start_index: int) -> list[dict]:
    """Label/value pairs on the page: the things a `read` action needs.

    A balance or a confirmation number is a table cell, not a control. The model
    can see it in the screenshot, so it must be able to point at it too.
    """
    found = []
    for frame in page.frames:
        cells = frame.locator("td, th")
        for i in range(min(cells.count(), 120)):
            label = cells.nth(i)
            try:
                text = label.inner_text().strip()
                if (not text or len(text) > 40 or "\n" in text
                        or label.locator("td, input, button, a").count()):
                    continue
                value = label.locator("xpath=following-sibling::*[1]")
                if not value.count():
                    continue
                shown = value.first.inner_text().strip()
                if (not shown or len(shown) > 60 or "\n" in shown
                        or value.first.locator("input, button, a, td").count()):
                    continue
                box = value.first.bounding_box()
                if not box:
                    continue
            except Exception:
                continue
            found.append({
                "index": start_index + len(found),
                "role": "text",
                "name": "",
                "anchor": text,
                "text": shown,
                "is_password": False,
                "frame_url": frame.url,
                "box": box,
                "locator": value.first,
            })
    return found


def nearest_text(frame, box) -> str | None:
    """The visible words closest to the left of a box, then above it.

    This is label_anchor in reverse: at record time we work out which caption a
    human would read for this control, so replay can find it the same way.
    """
    best, best_score = None, float("inf")
    cells = frame.locator("td, th, label, span, div, p, strong, b")
    for i in range(min(cells.count(), 250)):
        cell = cells.nth(i)
        try:
            if cell.locator("input, button, select, textarea, td, span, div").count():
                continue          # innermost text holders only
            text = cell.inner_text().strip()
            if not text or len(text) > 40:
                continue
            b = cell.bounding_box()
            if not b:
                continue
        except Exception:
            continue
        same_line = abs((b["y"] + b["height"] / 2) - (box["y"] + box["height"] / 2)) < max(b["height"], 14)
        dx = box["x"] - (b["x"] + b["width"])
        if same_line and dx >= -2 and dx < best_score:
            best, best_score = text, dx
    return best


def describe(control: dict, page_url: str) -> dict:
    """Turn the control that was just acted on into durable Target descriptors.

    A value read from a table cell has no ARIA role — "text" is our own label for
    it — so its rung carries no role and is resolved as "the nearest thing to the
    right of these words".
    """
    role = None if control["role"] == "text" else control["role"]
    rungs = []
    if control["name"] and role:
        rungs.append({"kind": "role_name", "role": role, "name": control["name"]})
    if control["anchor"]:
        rungs.append({"kind": "label_anchor", "anchor": control["anchor"],
                      "role": role, "relation": "right_of"})
    target = {"rungs": rungs}
    if "/" in control["frame_url"] and control["frame_url"] != page_url:
        tail = control["frame_url"].rsplit("/", 1)[-1]
        target["frame"] = {"url_contains": f"/{tail}"}
    return target


def crop(control: dict, path: str):
    """A small picture of one control: the last rung of a ladder."""
    try:
        control["locator"].screenshot(path=path)
        return path
    except Exception:
        return None
