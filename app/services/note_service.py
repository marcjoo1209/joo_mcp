"""
메모 서비스 (Service / Business 계층)

비즈니스 규칙과 흐름을 담당합니다. Repository 를 사용하지만 HTTP/SQL 세부사항은 모릅니다.
"없는 메모를 수정/삭제" 같은 상황은 도메인 예외(NoteNotFoundError)로 표현하고,
HTTP 변환은 라우터/예외 핸들러가 처리합니다.
"""

from app.core.exceptions import NoteNotFoundError
from app.models.note import Note
from app.repositories.note_repository import NoteRepository


class NoteService:
    def __init__(self, repository: NoteRepository):
        # 의존성 주입: Repository 를 외부에서 받는다 → 테스트 시 교체 가능.
        self.repository = repository

    def create_note(self, title: str, content: str = "") -> Note:
        return self.repository.create(title, content)

    def list_notes(self) -> list[Note]:
        return self.repository.list()

    def get_note(self, note_id: int) -> Note:
        note = self.repository.get(note_id)
        # Repository 는 "없음"을 None 으로 알린다 → Service 는 도메인 예외로 승격.
        # (HTTP 404 변환은 main.py 의 예외 핸들러가 담당)
        if note is None:
            raise NoteNotFoundError(note_id)
        return note

    def update_note(
        self,
        note_id: int,
        title: str | None = None,
        content: str | None = None,
    ) -> Note:
        note = self.repository.update(note_id, title, content)
        if note is None:
            raise NoteNotFoundError(note_id)
        return note

    def delete_note(self, note_id: int) -> None:
        if not self.repository.delete(note_id):
            raise NoteNotFoundError(note_id)
