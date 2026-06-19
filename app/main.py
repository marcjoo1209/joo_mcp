"""
FastAPI 애플리케이션

이 앱은 두 가지 방식의 CRUD 를 동시에 보여준다.

1) 직접 REST CRUD  (/notes ...)
   - 사람이 정확한 입력으로 메모를 다룬다. MCP/Gemini 와 무관한 평범한 CRUD API.
   - "CRUD 가 무엇인지" 감을 잡는 용도.

2) AI 기반 CRUD   (/chat)
   - "회의 메모 만들어줘" 같은 자연어를 받아 Gemini 가 MCP 도구를 호출해 CRUD 를 수행.
   - 이것이 'FastAPI -> Gemini -> MCP' 흐름의 핵심.

두 방식은 같은 SQLite DB(notes.db)를 공유하므로,
/chat 으로 만든 메모를 GET /notes 로 즉시 확인할 수 있다.

실행:
    uvicorn app.main:app --reload
문서(Swagger UI):
    http://127.0.0.1:8000/docs
"""

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# .env 파일을 읽어 환경변수(GEMINI_API_KEY 등)를 로드한다.
load_dotenv()

from common import database  # noqa: E402  (load_dotenv 이후 import)
from app.gemini_mcp import chat_with_tools  # noqa: E402

app = FastAPI(
    title="joo_mcp 예제: FastAPI + Gemini + MCP",
    description="자연어(/chat)와 직접 REST(/notes) 두 방식으로 메모 CRUD 를 다룹니다.",
    version="1.0.0",
)


@app.on_event("startup")
def _startup() -> None:
    # 앱 시작 시 DB 테이블을 보장한다.
    database.init_db()


# ---------------------------------------------------------------------------
# 요청/응답 스키마 (pydantic)
# ---------------------------------------------------------------------------
class NoteCreate(BaseModel):
    title: str
    content: str = ""


class NoteUpdate(BaseModel):
    title: str | None = None
    content: str | None = None


class ChatRequest(BaseModel):
    message: str


# ---------------------------------------------------------------------------
# 1) 직접 REST CRUD
# ---------------------------------------------------------------------------
@app.post("/notes", summary="[Create] 메모 생성")
def create_note(body: NoteCreate):
    return database.create_note(body.title, body.content)


@app.get("/notes", summary="[Read] 메모 전체 조회")
def list_notes():
    return database.list_notes()


@app.get("/notes/{note_id}", summary="[Read] 메모 단건 조회")
def get_note(note_id: int):
    note = database.get_note(note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="메모를 찾을 수 없습니다.")
    return note


@app.put("/notes/{note_id}", summary="[Update] 메모 수정")
def update_note(note_id: int, body: NoteUpdate):
    note = database.update_note(note_id, body.title, body.content)
    if note is None:
        raise HTTPException(status_code=404, detail="메모를 찾을 수 없습니다.")
    return note


@app.delete("/notes/{note_id}", summary="[Delete] 메모 삭제")
def delete_note(note_id: int):
    ok = database.delete_note(note_id)
    if not ok:
        raise HTTPException(status_code=404, detail="메모를 찾을 수 없습니다.")
    return {"deleted": True, "note_id": note_id}


# ---------------------------------------------------------------------------
# 2) AI 기반 CRUD (FastAPI -> Gemini -> MCP)
# ---------------------------------------------------------------------------
@app.post("/chat", summary="[AI] 자연어로 메모 CRUD 수행")
async def chat(body: ChatRequest):
    """자연어 메시지를 Gemini 에게 보내고, Gemini 가 MCP 도구로 CRUD 를 처리한다.

    예시 메시지:
      - "내일 회의 준비라는 제목으로 메모 만들어줘"
      - "메모 목록 보여줘"
      - "3번 메모 내용을 '완료'로 바꿔줘"
      - "1번 메모 삭제해줘"
    """
    try:
        answer = await chat_with_tools(body.message)
    except RuntimeError as e:
        # 예: API 키 미설정
        raise HTTPException(status_code=500, detail=str(e))
    return {"reply": answer}


@app.get("/", summary="헬스 체크")
def root():
    return {"status": "ok", "docs": "/docs"}
