"""
AI 기반 CRUD e2e 테스트 (FastAPI → Gemini → MCP → DB)

실제 Gemini API 를 호출하므로 비용/네트워크/비결정성이 있다.
그래서 기본적으로 SKIP 되며, 아래 두 조건을 모두 만족할 때만 실행된다.
  1) .env 에 GEMINI_API_KEY 설정
  2) 환경변수 RUN_CHAT_E2E=1

실행 예:
    # PowerShell
    $env:RUN_CHAT_E2E="1"; pytest tests/test_chat_e2e.py -v
"""

import os

import pytest

from app.core.config import settings

pytestmark = pytest.mark.skipif(
    not (os.getenv("RUN_CHAT_E2E") == "1" and settings.gemini_api_key),
    reason="실제 Gemini 호출 테스트: RUN_CHAT_E2E=1 과 GEMINI_API_KEY 가 필요합니다.",
)


def test_chat_creates_note_end_to_end(client):
    """자연어로 메모 생성을 요청하면, Gemini 가 MCP 도구로 실제 메모를 만든다."""
    res = client.post(
        "/chat",
        json={"message": "'테스트 메모'라는 제목으로 메모 하나 만들어줘"},
    )
    assert res.status_code == 200
    reply = res.json()["reply"]
    assert isinstance(reply, str) and reply.strip()

    # 같은 DB 를 공유하므로 REST 로 생성 결과를 확인할 수 있다.
    notes = client.get("/notes").json()
    assert len(notes) >= 1


def test_chat_lists_notes_end_to_end(client):
    """기존 메모가 있을 때 '목록 보여줘' 요청이 정상 응답을 준다."""
    client.post("/notes", json={"title": "사전메모", "content": "내용"})
    res = client.post("/chat", json={"message": "메모 목록 보여줘"})
    assert res.status_code == 200
    assert res.json()["reply"].strip()
