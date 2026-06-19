"""
도메인 모델 (Domain 계층)

DB 행(row)이나 HTTP 요청과 무관한 '메모'의 순수한 표현입니다.
Repository 는 DB row 를 이 Note 객체로 변환해 돌려주고,
Service 는 이 객체로 비즈니스 로직을 다룹니다.
"""

from dataclasses import dataclass


@dataclass
class Note:
    id: int
    title: str
    content: str
    created_at: str
    updated_at: str
