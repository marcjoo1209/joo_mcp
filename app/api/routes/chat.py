"""
챗 라우터 (Presentation 계층) — AI 기반 CRUD

자연어 메시지를 받아 ChatService(Gemini + MCP)에 위임한다.
"""

from fastapi import APIRouter, Depends

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
    reply = await service.handle(body.message)
    return ChatResponse(reply=reply)
