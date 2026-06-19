"""
애플리케이션 진입점 (Composition Root)

여기서 모든 계층을 '조립'한다.
  - 앱 생성(create_app)
  - 라우터 등록(notes, chat)
  - 도메인 예외 → HTTP 응답 변환 핸들러
  - 시작 시 DB 초기화(lifespan)

계층 구조:
  api(routes) → services → repositories → db
  (위에서 아래로만 의존한다)

실행:
    uvicorn app.main:app --reload
문서:
    http://127.0.0.1:8000/docs
"""

from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api.routes import chat, notes
from app.core.config import settings
from app.core.exceptions import NoteNotFoundError
from app.db.database import init_db
from app.services.chat_service import ChatService
from app.services.mcp_session import McpSessionManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 앱 시작 시 1회: 테이블 보장
    init_db()

    # MCP 세션을 '앱 수명 동안' 한 번만 열어 재사용한다(요청당 subprocess 제거).
    # stdio 세션은 anyio 규칙상 '연 task 에서 닫아야' 하므로 여기(lifespan)에서
    # async with 로 열고 닫는다. GEMINI_API_KEY 가 없으면 /chat 비활성(REST 는 동작).
    app.state.chat_service = None
    async with AsyncExitStack() as stack:
        if settings.gemini_api_key:
            manager = await stack.enter_async_context(McpSessionManager())
            app.state.chat_service = ChatService(manager)
        yield
    # async with 종료 시 MCP 세션도 같은 task 에서 정리됨


def create_app() -> FastAPI:
    """앱 팩토리: 설정/라우터/핸들러를 조립해 FastAPI 인스턴스를 만든다."""
    app = FastAPI(
        title="joo_mcp 예제: FastAPI + Gemini + MCP",
        description="표준 레이어드 아키텍처로 구성한 메모 CRUD. "
        "자연어(/chat)와 직접 REST(/notes) 두 방식을 제공합니다.",
        version="2.0.0",
        lifespan=lifespan,
    )

    # 라우터 등록
    app.include_router(notes.router)
    app.include_router(chat.router)

    # 도메인 예외 → HTTP 404 변환 (웹 계층에서만 HTTP 를 안다)
    @app.exception_handler(NoteNotFoundError)
    async def _note_not_found(request: Request, exc: NoteNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc)},
        )

    @app.get("/", tags=["health"], summary="헬스 체크")
    def root():
        return {"status": "ok", "docs": "/docs"}

    return app


app = create_app()
