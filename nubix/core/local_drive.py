"""
Local drive availability checks for sync paths on external/removable media.

Linux mounts removable drives under well-known roots (`/run/media/<user>/<label>`
on modern udisks2 systems, `/media/...` on older ones, `/mnt/...` for fstab
mounts).  When such a drive is unplugged, its directory tree vanishes — and a
naive `mkdir -p` would recreate the sync directory *on the system partition*,
after which bisync happily fills the root disk (or, worse, sees an empty local
tree and starts propagating deletions).

Rule: a sync path under one of these roots is only usable while some ancestor
of it (below the root itself) is an active mount point.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

# Roots under which paths are expected to live on a mounted filesystem.
# Order matters: "/run/media" must be checked before a hypothetical "/run".
REMOVABLE_ROOTS: tuple[str, ...] = ("/run/media", "/media", "/mnt")


def _removable_root_for(path: Path) -> Optional[Path]:
    """Return the removable root *path* lives under, or None."""
    for root in REMOVABLE_ROOTS:
        root_path = Path(root)
        if path == root_path:
            return None  # the root itself is never a valid sync target
        if root_path in path.parents:
            return root_path
    return None


def missing_mount_for(path: Path) -> Optional[Path]:
    """
    Return the expected mount point if *path* lies on a removable/mount root
    whose drive is currently NOT mounted; return None if the path is usable.

    "Usable" means either the path is outside all removable roots (regular
    home-directory paths), or at least one ancestor between the path and the
    root is an active mount point (the drive is plugged in and mounted).
    """
    path = Path(path).expanduser()
    root = _removable_root_for(path)
    if root is None:
        return None

    # Walk from the path itself up to (but excluding) the removable root.
    # Any active mount point in that chain means the drive is available.
    candidate = path
    while candidate != root:
        try:
            if os.path.ismount(candidate):
                return None
        except OSError:
            pass
        candidate = candidate.parent

    # No mount found — report the most likely mount point for the error
    # message: /run/media/<user>/<label> (two levels below the root) or
    # /media|/mnt/<name> (one level below).
    rel_parts = path.relative_to(root).parts
    depth = 2 if root == Path("/run/media") and len(rel_parts) >= 2 else 1
    return root.joinpath(*rel_parts[:depth])


def is_drive_available(path: Path) -> bool:
    """True if *path* can safely be created/synced right now."""
    return missing_mount_for(path) is None
