"""
File-based session CRUD with soft-delete (trash).
Each session is stored as learning_sessions/{session_id}/session.json.
Deleted sessions move to learning_sessions_trash/{session_id}/ and are
permanently removed after 30 days on startup.
"""

import json
import shutil
from pathlib import Path
from datetime import datetime, timedelta


class SessionManager:
    TRASH_RETENTION_DAYS = 30

    def __init__(self, sessions_dir: Path):
        self._dir = sessions_dir
        self._trash_dir = sessions_dir.parent / "learning_sessions_trash"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._trash_dir.mkdir(parents=True, exist_ok=True)

    def _session_path(self, session_id: str) -> Path:
        return self._dir / session_id / "session.json"

    def _trash_path(self, session_id: str) -> Path:
        return self._trash_dir / session_id / "session.json"

    # ---- Active sessions ----

    def create(self, name: str = "Untitled Session") -> dict:
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        now = datetime.now().isoformat()
        data = {
            "id": session_id,
            "name": name,
            "created_at": now,
            "updated_at": now,
            "viewport": {"panX": 0, "panY": 0, "zoom": 1.0},
            "nodes": {},
            "edges": [],
            "highlights": {},
        }
        path = self._session_path(session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return {"id": session_id, "name": name, "created_at": now, "updated_at": now, "node_count": 0}

    def load(self, session_id: str) -> dict | None:
        path = self._session_path(session_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def save(self, session_id: str, data: dict):
        data["updated_at"] = datetime.now().isoformat()
        path = self._session_path(session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def rename(self, session_id: str, name: str):
        data = self.load(session_id)
        if data:
            data["name"] = name
            self.save(session_id, data)

    def delete(self, session_id: str):
        """Soft-delete: move session folder to trash."""
        src = self._dir / session_id
        if not src.exists():
            return
        dest = self._trash_dir / session_id
        # If already in trash (name collision), remove old trash copy first
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(src), str(dest))
        # Stamp the deletion time into the session data
        trash_json = dest / "session.json"
        if trash_json.exists():
            try:
                data = json.loads(trash_json.read_text(encoding="utf-8"))
                data["deleted_at"] = datetime.now().isoformat()
                trash_json.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except (json.JSONDecodeError, OSError):
                pass

    def list_all(self) -> list[dict]:
        sessions = []
        if not self._dir.exists():
            return sessions
        for folder in sorted(self._dir.iterdir(), reverse=True):
            path = folder / "session.json"
            if path.exists():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    sessions.append({
                        "id": data.get("id", folder.name),
                        "name": data.get("name", "Untitled"),
                        "created_at": data.get("created_at", ""),
                        "updated_at": data.get("updated_at", ""),
                        "node_count": len(data.get("nodes", {})),
                    })
                except (json.JSONDecodeError, KeyError):
                    continue
        return sessions

    # ---- Trash operations ----

    def list_trash(self) -> list[dict]:
        """List all sessions in trash with deletion date."""
        sessions = []
        if not self._trash_dir.exists():
            return sessions
        for folder in sorted(self._trash_dir.iterdir(), reverse=True):
            path = folder / "session.json"
            if path.exists():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    deleted_at = data.get("deleted_at", "")
                    days_left = self._days_until_expiry(deleted_at)
                    sessions.append({
                        "id": data.get("id", folder.name),
                        "name": data.get("name", "Untitled"),
                        "created_at": data.get("created_at", ""),
                        "deleted_at": deleted_at,
                        "node_count": len(data.get("nodes", {})),
                        "days_left": days_left,
                    })
                except (json.JSONDecodeError, KeyError):
                    continue
        return sessions

    def restore(self, session_id: str) -> bool:
        """Restore a session from trash back to active sessions."""
        src = self._trash_dir / session_id
        if not src.exists():
            return False
        dest = self._dir / session_id
        if dest.exists():
            # Active session with same ID exists — shouldn't happen, but be safe
            return False
        shutil.move(str(src), str(dest))
        # Remove the deleted_at stamp
        restored_json = dest / "session.json"
        if restored_json.exists():
            try:
                data = json.loads(restored_json.read_text(encoding="utf-8"))
                data.pop("deleted_at", None)
                data["updated_at"] = datetime.now().isoformat()
                restored_json.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except (json.JSONDecodeError, OSError):
                pass
        return True

    def permanent_delete(self, session_id: str):
        """Permanently delete a session from trash."""
        folder = self._trash_dir / session_id
        if folder.exists():
            shutil.rmtree(folder)

    def cleanup_trash(self) -> int:
        """Remove sessions older than TRASH_RETENTION_DAYS from trash.
        Returns the number of sessions purged."""
        if not self._trash_dir.exists():
            return 0
        purged = 0
        for folder in list(self._trash_dir.iterdir()):
            path = folder / "session.json"
            if not path.exists():
                # No session.json — remove stale folder
                shutil.rmtree(folder)
                purged += 1
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                deleted_at = data.get("deleted_at", "")
                if self._days_until_expiry(deleted_at) <= 0:
                    shutil.rmtree(folder)
                    purged += 1
            except (json.JSONDecodeError, OSError):
                # Corrupt — remove it
                shutil.rmtree(folder)
                purged += 1
        return purged

    def _days_until_expiry(self, deleted_at_iso: str) -> int:
        """How many days until this trashed session expires. 0 or negative = expired."""
        if not deleted_at_iso:
            return 0  # No timestamp = treat as expired
        try:
            deleted = datetime.fromisoformat(deleted_at_iso)
            expires = deleted + timedelta(days=self.TRASH_RETENTION_DAYS)
            remaining = (expires - datetime.now()).days
            return max(remaining, 0)
        except (ValueError, TypeError):
            return 0
