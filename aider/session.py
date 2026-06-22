#!/usr/bin/env python

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path


SESSION_FILENAME = ".aider.session.json"
SESSION_VERSION = 1


def _hash_root(root):
    """Return a stable SHA-256 hex digest of the project root path."""
    return hashlib.sha256(os.path.abspath(root).encode("utf-8")).hexdigest()


class SessionState:
    """Manages auto-save and auto-load of the chat session's file list.

    The session file (``.aider.session.json``) is stored in the **git root**
    (if inside a repo) or the **current working directory** (otherwise).
    It records the relative paths of editable and read-only files so that
    if aider is accidentally killed or the user exits and restarts, the file
    context can be restored without manually re-adding everything.
    """

    def __init__(self, root):
        self.root = root
        self.root_hash = _hash_root(root)
        self._path = Path(root) / SESSION_FILENAME

    # ------------------------------------------------------------------
    # Path
    # ------------------------------------------------------------------
    @property
    def path(self):
        return self._path

    # ------------------------------------------------------------------
    # Read / write
    # ------------------------------------------------------------------
    def read(self):
        """Return the deserialised session dict, or ``None``."""
        try:
            if not self.path.exists():
                return None
            raw = self.path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if data.get("version") != SESSION_VERSION:
                return None
            if data.get("root_hash") != self.root_hash:
                return None
            return data
        except (OSError, json.JSONDecodeError, ValueError):
            return None

    def write(self, editable_files, read_only_files):
        """Persist the current file list to the session file."""
        data = {
            "version": SESSION_VERSION,
            "root_hash": self.root_hash,
            "created_at": self._created_at(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "files": {
                "editable": sorted(editable_files),
                "read_only": sorted(read_only_files),
            },
        }
        try:
            self.path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass  # best-effort

    def exists(self):
        return self.path.exists()

    def clear(self):
        """Remove the session file from disk."""
        try:
            if self.path.exists():
                self.path.unlink()
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _created_at(self):
        """Preserve the original creation timestamp if the file already exists."""
        try:
            if self.path.exists():
                existing = json.loads(self.path.read_text(encoding="utf-8"))
                return existing.get("created_at", datetime.now(timezone.utc).isoformat())
        except (OSError, json.JSONDecodeError, ValueError):
            pass
        return datetime.now(timezone.utc).isoformat()
