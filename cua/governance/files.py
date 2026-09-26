"""The one YAML reader, cached by path. A loader that computes its path from
`settings` at call time therefore sees a new root as a new file, with no cache to
clear. A file rewritten in place is not a new path: `store.refresh()` forgets it."""

from functools import cache
from pathlib import Path

import yaml


@cache
def read_yaml(path: Path):
    return yaml.safe_load(Path(path).read_text())
