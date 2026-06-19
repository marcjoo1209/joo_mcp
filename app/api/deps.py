"""
의존성 주입 (Dependency Injection)

FastAPI 의 Depends 가 호출하는 '제공자(provider)' 함수들입니다.
라우터는 구체 클래스를 직접 생성하지 않고 여기서 주입받습니다.
→ 계층 간 결합을 낮추고, 테스트 시 가짜(mock) 구현으로 교체하기 쉬워집니다.
"""

from functools import lru_cache

from app.repositories.note_repository import NoteRepository
from app.services.chat_service import ChatService
from app.services.note_service import NoteService


def get_note_service() -> NoteService:
    """요청마다 Repository 를 묶은 NoteService 를 만든다."""
    return NoteService(NoteRepository())


@lru_cache
def get_chat_service() -> ChatService:
    """ChatService 는 Gemini 클라이언트를 들고 있으므로 1회만 생성해 재사용한다."""
    return ChatService()
