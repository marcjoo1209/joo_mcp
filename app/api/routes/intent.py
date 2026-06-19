"""
의도 파악 라우터 (Presentation 계층) — LangGraph 기반

자연어 메시지를 받아 IntentService(LangGraph)에 위임한다.
응답에는 '어떻게 이해했는지'(엔티티/의도)와 '무엇을 했는지'(결과/답변)가 모두 담겨
의도 파악 과정을 들여다볼 수 있다.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from google.genai import errors as genai_errors

from app.api.deps import get_intent_service
from app.schemas.note import ChatRequest, IntentResponse
from app.services.intent_graph import IntentService

router = APIRouter(tags=["intent (LangGraph 의도 파악)"])


@router.post("/intent", response_model=IntentResponse, summary="[AI] 엔티티 기반 의도 파악 후 CRUD")
async def analyze_intent(
    body: ChatRequest, service: IntentService = Depends(get_intent_service)
):
    """그래프 단계: 엔티티 추출 → 의도 분류 → 실행 → 응답

    예시 메시지:
    - "회의록 이라는 제목으로 메모 만들어줘"  → intent=create
    - "메모 목록 보여줘"                      → intent=read_all
    - "3번 메모 보여줘"                       → intent=read_one
    - "3번 메모 삭제해줘"                     → intent=delete
    """
    try:
        final = await service.analyze(body.message)
    except genai_errors.APIError as e:
        code = getattr(e, "code", None) or status.HTTP_502_BAD_GATEWAY
        status_code = code if 400 <= code < 600 else status.HTTP_502_BAD_GATEWAY
        raise HTTPException(
            status_code=status_code,
            detail=f"Gemini API 오류: {getattr(e, 'message', str(e))}",
        )
    return IntentResponse(
        intent=final["intent"],
        entities=final["entities"],
        result=final.get("result"),
        reply=final["reply"],
    )
