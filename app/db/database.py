"""
데이터베이스 연결 (Infrastructure 계층)

SQLite 연결 생성과 테이블 초기화만 담당합니다.
CRUD 쿼리 자체는 여기 두지 않고 Repository 계층(note_repository.py)에 둡니다.
  - 이 모듈: "어떻게 연결하나"
  - Repository: "무엇을 저장/조회하나"
"""

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from app.core.config import settings


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """SQLite 연결을 열고, 사용 후 반드시 닫는 컨텍스트 매니저.

    사용 예:
        with get_connection() as conn:
            conn.execute(...)
    """
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row  # 컬럼명으로 접근 가능하게
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """notes 테이블이 없으면 생성한다. 앱/MCP 서버 시작 시 호출."""
    with get_connection() as conn:
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
