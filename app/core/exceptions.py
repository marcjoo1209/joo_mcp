"""
도메인 예외 (Exception 계층)

서비스 계층은 HTTP 를 모릅니다. 그래서 "메모를 못 찾음" 같은 상황을
HTTP 404 가 아니라 도메인 예외로 표현합니다.
HTTP 로의 변환은 라우터/예외 핸들러(main.py)가 담당합니다.
이렇게 하면 비즈니스 로직과 웹 계층이 분리됩니다.
"""


class NoteNotFoundError(Exception):
    """요청한 메모가 존재하지 않을 때 발생."""

    def __init__(self, note_id: int):
        self.note_id = note_id
        super().__init__(f"id={note_id} 메모를 찾을 수 없습니다.")
