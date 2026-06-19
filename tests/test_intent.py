"""
LangGraph 의도 파악 테스트

- 결정론적 노드(classify_intent / respond)는 LLM 없이 직접 검증한다.
- 전체 그래프(/intent) e2e 는 실제 Gemini 가 필요하므로 기본 SKIP(옵트인).
"""

import os

import pytest

from app.core.config import settings
from app.schemas.note import ExtractedEntities
from app.services.intent_graph import IntentService


# ---- classify_intent: 엔티티 → 의도 (규칙/보정) ----

def test_classify_create():
    state = {"entities": ExtractedEntities(action="create", title="회의록")}
    assert IntentService._classify_intent(state)["intent"] == "create"


def test_classify_create_without_title_is_unknown():
    """제목 없는 create 는 unknown 으로 보정."""
    state = {"entities": ExtractedEntities(action="create")}
    assert IntentService._classify_intent(state)["intent"] == "unknown"


def test_classify_read_one_without_id_falls_back_to_read_all():
    state = {"entities": ExtractedEntities(action="read_one", note_id=None)}
    assert IntentService._classify_intent(state)["intent"] == "read_all"


def test_classify_read_one_with_id():
    state = {"entities": ExtractedEntities(action="read_one", note_id=3)}
    assert IntentService._classify_intent(state)["intent"] == "read_one"


def test_classify_update_without_id_is_unknown():
    state = {"entities": ExtractedEntities(action="update", content="x")}
    assert IntentService._classify_intent(state)["intent"] == "unknown"


def test_classify_delete_with_id():
    state = {"entities": ExtractedEntities(action="delete", note_id=5)}
    assert IntentService._classify_intent(state)["intent"] == "delete"


# ---- respond: 결과 → 자연어(템플릿) ----

def test_respond_create():
    out = IntentService._respond({"intent": "create", "result": {"id": 7}})
    assert "7" in out["reply"]


def test_respond_read_all_counts_items():
    out = IntentService._respond({"intent": "read_all", "result": {"result": [{}, {}, {}]}})
    assert "3" in out["reply"]


def test_respond_delete_success():
    out = IntentService._respond({"intent": "delete", "result": {"deleted": True, "note_id": 1}})
    assert "삭제" in out["reply"]


def test_respond_unknown_gives_guidance():
    out = IntentService._respond({"intent": "unknown", "result": None})
    assert out["reply"].strip()


# ---- 전체 그래프 e2e (실제 Gemini, 옵트인) ----

@pytest.mark.skipif(
    not (os.getenv("RUN_CHAT_E2E") == "1" and settings.gemini_api_key),
    reason="실제 Gemini 호출 테스트: RUN_CHAT_E2E=1 과 GEMINI_API_KEY 가 필요합니다.",
)
def test_intent_graph_end_to_end(chat_client):
    """자연어 → (그래프) 엔티티/의도 파악 → MCP 실행 → 구조화 응답."""
    res = chat_client.post("/intent", json={"message": "회의록 이라는 제목으로 메모 만들어줘"})
    assert res.status_code == 200
    body = res.json()
    assert body["intent"] == "create"
    assert body["entities"]["action"] == "create"
    assert body["reply"].strip()

    # 같은 DB 공유 → REST 로 확인
    assert len(chat_client.get("/notes").json()) >= 1
