"""
MCP 서버 CRUD e2e 테스트 (Client → stdio → MCP 서버 → Repository → DB)

실제 mcp_server/server.py 를 하위 프로세스로 띄우고, MCP 클라이언트로
도구를 호출해 CRUD 전체를 검증한다. (Gemini 없이 도구 계층만 검증)

격리: 서버 프로세스에 환경변수 DB_PATH 를 주입해 임시 SQLite 파일을 쓰게 한다.
"""

import asyncio
import json
import os
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_PATH = os.path.join(PROJECT_ROOT, "mcp_server", "server.py")


def _server_params(db_path: str) -> StdioServerParameters:
    """임시 DB 를 쓰도록 DB_PATH 환경변수를 주입한 서버 실행 파라미터."""
    return StdioServerParameters(
        command=sys.executable,
        args=[SERVER_PATH],
        # os.environ 을 합쳐 PATH 등 시스템 환경을 유지한 채 DB_PATH 만 덮어쓴다.
        env={**os.environ, "DB_PATH": db_path},
    )


def _result_to_obj(call_result):
    """단일 dict 를 반환하는 도구 결과 → 파이썬 dict.

    (create/get/update/delete 처럼 dict 하나를 돌려주는 도구는
     content[0].text 에 JSON dict 가 담긴다.)
    """
    return json.loads(call_result.content[0].text)


def _result_to_list(call_result):
    """리스트를 반환하는 도구(list_notes) 결과 → 파이썬 list.

    FastMCP 는 list 반환을 structuredContent 의 "result" 키에 담아준다.
    (content 블록은 항목마다 하나씩 쪼개지므로 길이 계산에 쓰지 않는다.)
    """
    return call_result.structuredContent["result"]


async def _run(coro_fn, db_path: str):
    """서버에 연결해 세션을 만든 뒤 coro_fn(session) 을 실행한다."""
    async with stdio_client(_server_params(db_path)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await coro_fn(session)


@pytest.fixture
def mcp_db(tmp_path):
    """MCP 서버 프로세스용 임시 DB 경로."""
    return str(tmp_path / "mcp_notes.db")


def test_lists_five_crud_tools(mcp_db):
    async def scenario(session):
        return [t.name for t in (await session.list_tools()).tools]

    names = asyncio.run(_run(scenario, mcp_db))
    assert set(names) == {
        "create_note",
        "list_notes",
        "get_note",
        "update_note",
        "delete_note",
    }


def test_create_note_tool(mcp_db):
    async def scenario(session):
        return _result_to_obj(
            await session.call_tool("create_note", {"title": "MCP생성", "content": "x"})
        )

    note = asyncio.run(_run(scenario, mcp_db))
    assert note["id"] >= 1
    assert note["title"] == "MCP생성"
    assert note["content"] == "x"


def test_get_note_not_found_tool(mcp_db):
    async def scenario(session):
        return _result_to_obj(await session.call_tool("get_note", {"note_id": 99999}))

    res = asyncio.run(_run(scenario, mcp_db))
    assert "error" in res


def test_full_crud_lifecycle_via_mcp(mcp_db):
    """create → list → get → update → delete 를 MCP 도구로 한 번에 검증."""

    async def scenario(session):
        out = {}

        # Create
        created = _result_to_obj(
            await session.call_tool("create_note", {"title": "원본", "content": "1"})
        )
        nid = created["id"]
        out["created_id"] = nid

        # Read - list
        listed = _result_to_list(await session.call_tool("list_notes", {}))
        out["list_count"] = len(listed)

        # Read - get
        got = _result_to_obj(await session.call_tool("get_note", {"note_id": nid}))
        out["got_content"] = got["content"]

        # Update
        updated = _result_to_obj(
            await session.call_tool("update_note", {"note_id": nid, "content": "2"})
        )
        out["updated_content"] = updated["content"]
        out["title_preserved"] = updated["title"]

        # Delete
        deleted = _result_to_obj(await session.call_tool("delete_note", {"note_id": nid}))
        out["deleted"] = deleted["deleted"]

        # Delete 후 조회
        after = _result_to_obj(await session.call_tool("get_note", {"note_id": nid}))
        out["after_delete_error"] = "error" in after
        return out

    r = asyncio.run(_run(scenario, mcp_db))
    assert r["created_id"] >= 1
    assert r["list_count"] == 1
    assert r["got_content"] == "1"
    assert r["updated_content"] == "2"
    assert r["title_preserved"] == "원본"  # 미전달 필드 유지
    assert r["deleted"] is True
    assert r["after_delete_error"] is True
