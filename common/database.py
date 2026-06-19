"""
공용 데이터베이스 모듈 (SQLite)

이 파일은 두 곳에서 함께 사용됩니다.
1) mcp_server/server.py  -> Gemini가 MCP 도구를 통해 호출하는 CRUD
2) app/main.py           -> 사람이 직접 호출하는 REST CRUD

즉, "AI를 통한 CRUD"와 "직접 REST CRUD"가 같은 DB(notes 테이블)를 바라봅니다.
그래서 Gemini가 만든 메모를 REST API GET으로 바로 확인할 수 있습니다.
"""

import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

# 프로젝트 루트(joo_mcp/) 기준으로 DB 파일 경로를 고정한다.
# 이렇게 하면 어디서 실행하든(작업 디렉터리가 달라도) 같은 DB를 사용한다.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "notes.db")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    # 결과를 dict 처럼 컬럼명으로 접근할 수 있게 한다.
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """notes 테이블이 없으면 생성한다. 앱/서버 시작 시 한 번 호출한다."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                title      TEXT NOT NULL,
                content    TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# CRUD 함수들 (Create / Read / Update / Delete)
# ---------------------------------------------------------------------------

def create_note(title: str, content: str = "") -> dict:
    """[Create] 새 메모를 추가하고, 생성된 메모(dict)를 반환한다."""
    now = _now()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO notes (title, content, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (title, content, now, now),
        )
        conn.commit()
        note_id = cur.lastrowid
    return get_note(note_id)


def list_notes() -> list[dict]:
    """[Read] 모든 메모를 최신순으로 반환한다."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM notes ORDER BY id DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def get_note(note_id: int) -> Optional[dict]:
    """[Read] 단일 메모를 반환한다. 없으면 None."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM notes WHERE id = ?", (note_id,)
        ).fetchone()
    return dict(row) if row else None


def update_note(
    note_id: int,
    title: Optional[str] = None,
    content: Optional[str] = None,
) -> Optional[dict]:
    """[Update] 메모의 title/content 를 수정한다. 없으면 None."""
    existing = get_note(note_id)
    if existing is None:
        return None

    new_title = title if title is not None else existing["title"]
    new_content = content if content is not None else existing["content"]

    with _connect() as conn:
        conn.execute(
            "UPDATE notes SET title = ?, content = ?, updated_at = ? WHERE id = ?",
            (new_title, new_content, _now(), note_id),
        )
        conn.commit()
    return get_note(note_id)


def delete_note(note_id: int) -> bool:
    """[Delete] 메모를 삭제한다. 삭제 성공 시 True, 대상이 없으면 False."""
    with _connect() as conn:
        cur = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        conn.commit()
    return cur.rowcount > 0
