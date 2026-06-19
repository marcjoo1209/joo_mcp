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

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api.routes import chat, notes
from app.core.exceptions import NoteNotFoundError
from app.db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 앱 시작 시 1회: 테이블 보장
    init_db()
    yield
    # 종료 시 정리할 리소스가 있다면 여기서


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
