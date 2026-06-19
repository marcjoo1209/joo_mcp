"""
저장소 (Repository 계층)

데이터 접근(SQL)을 한곳에 캡슐화합니다. 위 계층(Service)은
"SQL 이 어떻게 생겼는지" 모른 채 메서드만 호출합니다.

중요: 이 Repository 는 두 곳에서 공유됩니다.
  - app/services/note_service.py  → REST API 의 데이터 접근
  - mcp_server/server.py          → MCP 도구의 데이터 접근
즉, 사람(REST)과 AI(MCP)가 '같은 데이터 접근 계층'을 사용합니다.
"""

import sqlite3
from datetime import datetime, timezone

from app.db.database import get_connection
from app.models.note import Note


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_note(row: sqlite3.Row) -> Note:
    return Note(
        id=row["id"],
        title=row["title"],
        content=row["content"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class NoteRepository:
    """notes 테이블에 대한 CRUD."""

    def create(self, title: str, content: str = "") -> Note:
        now = _now()
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO notes (title, content, created_at, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (title, content, now, now),
            )
            conn.commit()
            note_id = cur.lastrowid
        return self.get(note_id)  # type: ignore[return-value]

    def list(self) -> list[Note]:
        with get_connection() as conn:
            rows = conn.execute("SELECT * FROM notes ORDER BY id DESC").fetchall()
        return [_to_note(r) for r in rows]

    def get(self, note_id: int) -> Note | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM notes WHERE id = ?", (note_id,)
            ).fetchone()
        return _to_note(row) if row else None

    def update(
        self,
        note_id: int,
        title: str | None = None,
        content: str | None = None,
    ) -> Note | None:
        existing = self.get(note_id)
        if existing is None:
            return None

        new_title = title if title is not None else existing.title
        new_content = content if content is not None else existing.content
        with get_connection() as conn:
            conn.execute(
                "UPDATE notes SET title = ?, content = ?, updated_at = ? WHERE id = ?",
                (new_title, new_content, _now(), note_id),
            )
            conn.commit()
        return self.get(note_id)

    def delete(self, note_id: int) -> bool:
        with get_connection() as conn:
            cur = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
            conn.commit()
        return cur.rowcount > 0
