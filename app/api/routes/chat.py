"""
챗 라우터 (Presentation 계층) — AI 기반 CRUD

자연어 메시지를 받아 ChatService(Gemini + 영속 MCP 세션)에 위임한다.
Gemini API 오류(쿼터 초과 등)는 깔끔한 HTTP 응답으로 변환한다.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from google.genai import errors as genai_errors

from app.api.deps import get_chat_service
from app.schemas.note import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

router = APIRouter(tags=["chat (AI 기반 CRUD)"])


@router.post("/chat", response_model=ChatResponse, summary="[AI] 자연어로 메모 CRUD 수행")
async def chat(body: ChatRequest, service: ChatService = Depends(get_chat_service)):
    """예시 메시지:
    - "내일 회의 준비라는 제목으로 메모 만들어줘"
    - "메모 목록 보여줘"
    - "3번 메모 내용을 '완료'로 바꿔줘"
    - "1번 메모 삭제해줘"
    """
    try:
        reply = await service.handle(body.message)
    except genai_errors.APIError as e:
        # 예: 429 무료 티어 쿼터 초과, 5xx 등. 원래 상태코드를 최대한 보존한다.
        code = getattr(e, "code", None) or status.HTTP_502_BAD_GATEWAY
        status_code = code if 400 <= code < 600 else status.HTTP_502_BAD_GATEWAY
        raise HTTPException(
            status_code=status_code,
            detail=f"Gemini API 오류: {getattr(e, 'message', str(e))}",
        )
    return ChatResponse(reply=reply)
