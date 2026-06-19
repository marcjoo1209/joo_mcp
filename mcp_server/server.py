"""
MCP 서버 (notes)

이 파일이 바로 "MCP 서버"입니다.
- MCP 서버는 AI(여기서는 Gemini)가 사용할 수 있는 "도구(tool)"를 정의해서 제공합니다.
- 여기서는 메모(note)에 대한 CRUD 도구 5개를 제공합니다.
- 통신 방식(transport)은 기본값인 stdio 입니다.
  즉, 이 파이썬 프로세스의 표준입력/표준출력으로 MCP 클라이언트와 대화합니다.
  app/main.py 가 이 파일을 하위 프로세스로 실행해서 연결합니다.

@mcp.tool() 데코레이터를 붙이면, 함수의
  - 이름(create_note 등)
  - 인자 타입(title: str ...)
  - docstring(아래 설명 문자열)
이 그대로 AI에게 "이 도구는 이런 일을 하고, 이런 인자가 필요하다"라고 전달됩니다.
그래서 docstring을 사람이 아니라 'AI가 읽는 설명서'라고 생각하고 명확하게 써야 합니다.
"""

import os
import sys

# 이 파일이 하위 프로세스(stdio)로 실행될 때도 `common` 패키지를 import 할 수 있도록
# 프로젝트 루트를 모듈 검색 경로에 추가한다.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from mcp.server.fastmcp import FastMCP  # noqa: E402

from common import database  # noqa: E402

# MCP 서버 인스턴스. "notes"는 이 서버의 이름이다.
mcp = FastMCP("notes")


@mcp.tool()
def create_note(title: str, content: str = "") -> dict:
    """새 메모를 생성한다.

    Args:
        title: 메모 제목 (필수)
        content: 메모 본문 내용 (선택, 기본값은 빈 문자열)

    Returns:
        생성된 메모. id, title, content, created_at, updated_at 를 포함한다.
    """
    return database.create_note(title, content)


@mcp.tool()
def list_notes() -> list[dict]:
    """저장된 모든 메모를 최신순으로 조회한다.

    Returns:
        메모 목록. 메모가 없으면 빈 리스트를 반환한다.
    """
    return database.list_notes()


@mcp.tool()
def get_note(note_id: int) -> dict:
    """id로 단일 메모를 조회한다.

    Args:
        note_id: 조회할 메모의 id

    Returns:
        해당 메모. 존재하지 않으면 {"error": "..."} 를 반환한다.
    """
    note = database.get_note(note_id)
    if note is None:
        return {"error": f"id={note_id} 메모를 찾을 수 없습니다."}
    return note


@mcp.tool()
def update_note(note_id: int, title: str | None = None, content: str | None = None) -> dict:
    """기존 메모의 제목/내용을 수정한다. 전달하지 않은 항목은 그대로 유지된다.

    Args:
        note_id: 수정할 메모의 id
        title: 새 제목 (수정하지 않으려면 생략)
        content: 새 내용 (수정하지 않으려면 생략)

    Returns:
        수정된 메모. 존재하지 않으면 {"error": "..."} 를 반환한다.
    """
    note = database.update_note(note_id, title, content)
    if note is None:
        return {"error": f"id={note_id} 메모를 찾을 수 없습니다."}
    return note


@mcp.tool()
def delete_note(note_id: int) -> dict:
    """id로 메모를 삭제한다.

    Args:
        note_id: 삭제할 메모의 id

    Returns:
        성공 여부를 담은 객체. {"deleted": true/false, "note_id": ...}
    """
    ok = database.delete_note(note_id)
    return {"deleted": ok, "note_id": note_id}


if __name__ == "__main__":
    # 서버 시작 시 테이블을 보장한다.
    database.init_db()
    # stdio transport 로 MCP 서버 실행 (표준입출력으로 통신).
    mcp.run()
