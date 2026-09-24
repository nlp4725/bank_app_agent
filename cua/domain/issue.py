"""A finding about an Artifact or an Overlay: what is wrong, and where."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Issue:
    code: str
    where: str
    detail: str

    def __str__(self):
        return f"[{self.code}] {self.where}: {self.detail}"
