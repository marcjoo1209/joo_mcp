"""
메모 라우터 (Presentation 계층) — 직접 REST CRUD

HTTP 요청을 받아 Service 에 위임하고, 결과를 응답 DTO 로 변환만 한다.
비즈니스 로직은 두지 않는다(=얇은 컨트롤러).
"""

from fastapi import APIRouter, Depends, status

from app.api.deps import get_note_service
from app.schemas.note import DeleteResponse, NoteCreate, NoteOut, NoteUpdate
from app.services.note_service import NoteService

router = APIRouter(prefix="/notes", tags=["notes (직접 REST CRUD)"])


@router.post("", response_model=NoteOut, status_code=status.HTTP_201_CREATED, summary="[Create] 메모 생성")
def create_note(body: NoteCreate, service: NoteService = Depends(get_note_service)):
    note = service.create_note(body.title, body.content)
    return NoteOut.from_model(note)


@router.get("", response_model=list[NoteOut], summary="[Read] 메모 전체 조회")
def list_notes(service: NoteService = Depends(get_note_service)):
    return [NoteOut.from_model(n) for n in service.list_notes()]


@router.get("/{note_id}", response_model=NoteOut, summary="[Read] 메모 단건 조회")
def get_note(note_id: int, service: NoteService = Depends(get_note_service)):
    return NoteOut.from_model(service.get_note(note_id))


@router.put("/{note_id}", response_model=NoteOut, summary="[Update] 메모 수정")
def update_note(note_id: int, body: NoteUpdate, service: NoteService = Depends(get_note_service)):
    return NoteOut.from_model(service.update_note(note_id, body.title, body.content))


@router.delete("/{note_id}", response_model=DeleteResponse, summary="[Delete] 메모 삭제")
def delete_note(note_id: int, service: NoteService = Depends(get_note_service)):
    service.delete_note(note_id)
    return DeleteResponse(deleted=True, note_id=note_id)
