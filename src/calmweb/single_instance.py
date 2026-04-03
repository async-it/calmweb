"""Single-instance process lock utilities (file-only lock)."""

from __future__ import annotations
import os
from . import config

LOCK_FILENAME = "calmweb.lock"


def acquire_single_instance_lock() -> str | None:
    """Create a lock file.

    Returns the lock file path when lock acquisition succeeds,
    or None if another instance already owns the lock.
    """
    lock_path = os.path.join(config.USER_CFG_DIR, LOCK_FILENAME)
    os.makedirs(config.USER_CFG_DIR, exist_ok=True)

    try:
        # Crée le fichier uniquement s'il n'existe pas
        with open(lock_path, "x", encoding="utf-8") as f:
            f.write(str(os.getpid()))
        return lock_path
    except FileExistsError:
        return None


def release_single_instance_lock(lock_path: str | None) -> None:
    """Remove the lock file."""
    if lock_path is None:
        return

    try:
        os.unlink(lock_path)
    except FileNotFoundError:
        pass  # fichier déjà supprimé
    except Exception as e:
        print(f"Impossible de supprimer {lock_path}: {e}")