"""The Capability Store: the one answer to "which Artifact is live?".

Every caller — the Replay Engine's entry points, the demo tools, the tests — asks
here rather than opening a file, so there is one model of a capability and not two.
The Store owns the three things a caller would otherwise assemble by hand: finding
the approved Artifact, merging its App Profile, and the per-Tenant address and
Overlay. See CONTEXT.md, "Artifact" and "Tenant Overlay".
"""

from functools import cache
from pathlib import Path

from ..domain.artifact import Artifact, merged
from ..domain.errors import CuaError
from ..settings import settings
from .files import read_yaml
from .policy import PolicyError, load_tenant_policy
from .profile import load_profile


class UnknownCapability(CuaError):
    pass


@cache
def _index(artifacts_dir: Path) -> dict:
    """Every Artifact on disk, by (capability id, version).

    A file that is not an Artifact — a decisions file — simply does not appear,
    rather than raising: the Store answers for what is there. A draft carrying the
    same version as an approved Artifact never displaces it, so re-reviewing a
    version in place cannot quietly change what replays.
    """
    found = {}
    for path in sorted(artifacts_dir.glob("*.yaml")):
        try:
            artifact = Artifact.model_validate(read_yaml(path))
        except Exception:
            continue
        key = (artifact.capability.id, artifact.capability.version)
        sitting = found.get(key)
        if sitting is not None and sitting.capability.status == "approved" \
                and artifact.capability.status != "approved":
            continue
        found[key] = artifact
    return found


def artifacts() -> list[Artifact]:
    """Every Artifact on disk, approved or not — what a Reviewer may borrow from."""
    return list(_index(settings.artifacts_dir).values())


def load_capability(capability_id: str, version: str | None = None) -> Artifact:
    """The Artifact a Calling Agent would get, with its App Profile already merged.

    Omit the version to take the highest approved one, which is what a caller that
    just wants "the live capability" means.
    """
    index = _index(settings.artifacts_dir)
    if version is not None:
        artifact = index.get((capability_id, version))
        if artifact is None:
            raise UnknownCapability(f"no artifact {capability_id}@{version}")
    else:
        approved = sorted(v for (i, v) in index if i == capability_id
                          and index[(i, v)].capability.status == "approved")
        if not approved:
            raise UnknownCapability(f"no approved artifact for {capability_id!r}")
        artifact = index[(capability_id, approved[-1])]
    return merged(artifact, load_profile(artifact.capability.vendor_app))


def overlay_for(tenant: str) -> dict | None:
    """The Tenant Overlay, if this Tenant has one. Appearance only; the engine lints
    it before applying it, so nothing here needs to judge what it contains."""
    path = settings.overlays_dir / f"{tenant}.yaml"
    return read_yaml(path) if path.exists() else None


def origin_for(tenant: str, vendor_app: str) -> str:
    """Where this Tenant's instance lives, from the Tenant's own Policy file.

    The address belongs to the institution, so it is read from the file the
    institution owns rather than from a dict in whichever tool is running.
    """
    try:
        return load_tenant_policy(tenant, vendor_app)["origin"].rstrip("/")
    except PolicyError as exc:
        raise UnknownCapability(str(exc)) from exc
