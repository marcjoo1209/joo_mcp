"""
의존성 주입 (Dependency Injection)

FastAPI 의 Depends 가 호출하는 '제공자(provider)' 함수들입니다.
라우터는 구체 클래스를 직접 생성하지 않고 여기서 주입받습니다.
→ 계층 간 결합을 낮추고, 테스트 시 가짜(mock) 구현으로 교체하기 쉬워집니다.
"""

from fastapi import HTTPException, Request, status

from app.repositories.note_repository import NoteRepository
from app.services.chat_service import ChatService
from app.services.intent_graph import IntentService
from app.services.note_service import NoteService


def get_note_service() -> NoteService:
    """요청마다 Repository 를 묶은 NoteService 를 만든다."""
    return NoteService(NoteRepository())


def get_chat_service(request: Request) -> ChatService:
    """앱 시작 시 lifespan 이 만들어 둔 ChatService 를 돌려준다.

    ChatService 는 영속 MCP 세션을 들고 있어 매 요청마다 새로 만들지 않는다.
    GEMINI_API_KEY 가 없으면 lifespan 이 생성하지 않으므로 503 으로 안내한다.
    """
    service = getattr(request.app.state, "chat_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GEMINI_API_KEY 가 설정되지 않아 /chat 을 사용할 수 없습니다.",
        )
    return service


def get_intent_service(request: Request) -> IntentService:
    """lifespan 이 만들어 둔 LangGraph IntentService 를 돌려준다."""
    service = getattr(request.app.state, "intent_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GEMINI_API_KEY 가 설정되지 않아 /intent 를 사용할 수 없습니다.",
        )
    return service
