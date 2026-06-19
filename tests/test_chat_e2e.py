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


def test_chat_crud_end_to_end(client):
    """자연어 한 번의 세션 안에서 생성 → 조회 흐름을 검증한다.

    실제 Gemini 가 MCP 도구(create_note/list_notes)를 호출하고,
    그 결과가 같은 DB 에 반영되어 REST 로도 보이는지 확인한다.

    (실 API 호출 + MCP 서브프로세스 정리의 상호작용을 줄이기 위해
     하나의 TestClient 세션 안에서 처리한다.)
    """
    # 1) 생성 요청
    res = client.post(
        "/chat",
        json={"message": "테스트 메모 라는 제목으로 메모 하나 만들어줘"},
    )
    assert res.status_code == 200
    assert res.json()["reply"].strip()

    # 2) 같은 DB 공유 → REST 로 생성 결과 확인
    notes = client.get("/notes").json()
    assert len(notes) >= 1

    # 3) 목록 조회 요청도 정상 응답
    res2 = client.post("/chat", json={"message": "메모 목록 보여줘"})
    assert res2.status_code == 200
    assert res2.json()["reply"].strip()
