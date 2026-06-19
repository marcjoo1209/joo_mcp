"""
MCP 서버 (notes)

이 파일이 바로 "MCP 서버"입니다.
- AI(Gemini)가 사용할 수 있는 '도구(tool)'를 정의해 제공합니다.
- 메모(note) CRUD 도구 5개를 제공합니다.
- 통신 방식은 기본값 stdio (표준입출력). app(ChatService)이 이 파일을
  하위 프로세스로 실행해 연결합니다.

아키텍처 메모:
  이 MCP 서버는 직접 SQL 을 짜지 않고, REST API 와 '동일한' Repository 계층
  (app.repositories.NoteRepository)을 재사용합니다.
  → 데이터 접근 규칙이 한 곳(Repository)에만 존재해, 사람(REST)과 AI(MCP)가
    완전히 같은 방식으로 데이터를 다룹니다.
"""

import os
import sys
from dataclasses import asdict

# 하위 프로세스(stdio)로 실행될 때도 app 패키지를 import 할 수 있도록 루트를 경로에 추가.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from mcp.server.fastmcp import FastMCP  # noqa: E402

from app.db.database import init_db  # noqa: E402
from app.repositories.note_repository import NoteRepository  # noqa: E402

mcp = FastMCP("notes")
repo = NoteRepository()


@mcp.tool()
def create_note(title: str, content: str = "") -> dict:
    """새 메모를 생성한다.

    Args:
        title: 메모 제목 (필수)
        content: 메모 본문 내용 (선택, 기본값은 빈 문자열)

    Returns:
        생성된 메모. id, title, content, created_at, updated_at 를 포함한다.
    """
    return asdict(repo.create(title, content))


@mcp.tool()
def list_notes() -> list[dict]:
    """저장된 모든 메모를 최신순으로 조회한다.

    Returns:
        메모 목록. 메모가 없으면 빈 리스트.
    """
    return [asdict(n) for n in repo.list()]


@mcp.tool()
def get_note(note_id: int) -> dict:
    """id로 단일 메모를 조회한다.

    Args:
        note_id: 조회할 메모의 id

    Returns:
        해당 메모. 존재하지 않으면 {"error": "..."}.
    """
    note = repo.get(note_id)
    if note is None:
        return {"error": f"id={note_id} 메모를 찾을 수 없습니다."}
    return asdict(note)


@mcp.tool()
def update_note(note_id: int, title: str | None = None, content: str | None = None) -> dict:
    """기존 메모의 제목/내용을 수정한다. 전달하지 않은 항목은 그대로 유지된다.

    Args:
        note_id: 수정할 메모의 id
        title: 새 제목 (수정하지 않으려면 생략)
        content: 새 내용 (수정하지 않으려면 생략)

    Returns:
        수정된 메모. 존재하지 않으면 {"error": "..."}.
    """
    note = repo.update(note_id, title, content)
    if note is None:
        return {"error": f"id={note_id} 메모를 찾을 수 없습니다."}
    return asdict(note)


@mcp.tool()
def delete_note(note_id: int) -> dict:
    """id로 메모를 삭제한다.

    Args:
        note_id: 삭제할 메모의 id

    Returns:
        {"deleted": true/false, "note_id": ...}
    """
    ok = repo.delete(note_id)
    return {"deleted": ok, "note_id": note_id}


if __name__ == "__main__":
    init_db()
    mcp.run()
