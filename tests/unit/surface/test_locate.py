"""The label_anchor geometry, over literal boxes and no browser.

`score` is what decides which control "the nearest thing to the right of these words"
is. Until it had a file of its own it was only reachable through a live page.
"""

import math

from cua.surface.locate import score

ANCHOR = {"x": 100, "y": 200, "width": 80, "height": 16}      # the caption


def box(x, y, width=60, height=16):
    return {"x": x, "y": y, "width": width, "height": height}


def test_right_of_prefers_the_closest_control_on_the_same_line():
    near = box(x=190, y=200)          # 10px right of the caption's edge
    far = box(x=300, y=200)
    assert score("right_of", ANCHOR, near) < score("right_of", ANCHOR, far)


def test_right_of_rejects_a_control_on_another_line():
    below = box(x=190, y=240)
    assert math.isinf(score("right_of", ANCHOR, below))


def test_right_of_rejects_a_control_to_the_left():
    left = box(x=0, y=200)
    assert math.isinf(score("right_of", ANCHOR, left))


def test_right_of_tolerates_a_control_that_starts_just_before_the_caption_ends():
    """Layouts overlap by a pixel or two; that must not lose the field."""
    touching = box(x=179, y=200)
    assert not math.isinf(score("right_of", ANCHOR, touching))


def test_below_needs_horizontal_overlap():
    under = box(x=110, y=230)
    beside = box(x=400, y=230)
    assert score("below", ANCHOR, under) < score("below", ANCHOR, beside)
    assert math.isinf(score("below", ANCHOR, beside))


def test_below_rejects_a_control_above_the_caption():
    above = box(x=110, y=100)
    assert math.isinf(score("below", ANCHOR, above))


def test_nearest_never_disqualifies_only_ranks():
    anywhere = box(x=0, y=0)
    close = box(x=185, y=200)
    assert not math.isinf(score("nearest", ANCHOR, anywhere))
    assert score("nearest", ANCHOR, close) < score("nearest", ANCHOR, anywhere)
