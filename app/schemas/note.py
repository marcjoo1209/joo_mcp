"""
요청/응답 스키마 (DTO, Presentation 계층)

HTTP 경계에서 들어오고 나가는 데이터의 모양을 정의합니다.
도메인 모델(models/note.py)과 분리하는 이유:
  - 입력 검증(예: 빈 제목 거부)을 API 경계에서 처리
  - 내부 모델을 바꿔도 외부 API 계약을 안정적으로 유지
"""

from pydantic import BaseModel, Field

from app.models.note import Note


# ---- 입력 ----
class NoteCreate(BaseModel):
    title: str = Field(min_length=1, description="메모 제목 (필수)")
    content: str = Field(default="", description="메모 본문")


class NoteUpdate(BaseModel):
    title: str | None = Field(default=None, description="새 제목 (생략 시 유지)")
    content: str | None = Field(default=None, description="새 내용 (생략 시 유지)")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, description="자연어 요청")


# ---- 출력 ----
class NoteOut(BaseModel):
    id: int
    title: str
    content: str
    created_at: str
    updated_at: str

    @classmethod
    def from_model(cls, note: Note) -> "NoteOut":
        """도메인 모델 Note → 응답 DTO 로 변환."""
        return cls(
            id=note.id,
            title=note.title,
            content=note.content,
            created_at=note.created_at,
            updated_at=note.updated_at,
        )


class ChatResponse(BaseModel):
    reply: str


class DeleteResponse(BaseModel):
    deleted: bool
    note_id: int
