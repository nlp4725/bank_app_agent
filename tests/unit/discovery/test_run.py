"""The Discovery loop, without a model or a browser: what its source promises. The loop itself runs under tests/app/discovery/test_run.py with a scripted model."""

def test_a_crop_is_only_ever_of_a_control_never_of_a_value():
    """Discovery crops a target before acting, and only for a click: a field after
    typing or a cell being read is a picture of a value."""
    import inspect

    from cua import discovery
    src = inspect.getsource(discovery.discover)
    assert 'if call.name == "click" else None' in src
    assert src.index("surface.crop(") < src.index("record = _perform(")
