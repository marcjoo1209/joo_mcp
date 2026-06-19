"""
pytest 공용 픽스처

핵심 원칙: 테스트는 실제 notes.db 를 건드리지 않는다.
각 테스트마다 임시 디렉터리에 별도 SQLite 파일을 만들어 격리한다.
  - REST 테스트: settings.db_path 를 임시 파일로 바꿔치기(monkeypatch)
  - MCP 테스트:  서버 하위 프로세스에 환경변수 DB_PATH 로 임시 파일 주입
"""

import os
import sys

import pytest

# 프로젝트 루트를 import 경로에 추가 (pytest 를 어디서 실행하든 동작하도록)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.config import settings  # noqa: E402
from app.db.database import init_db  # noqa: E402


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """테스트 전용 임시 SQLite 파일을 만들고 settings.db_path 를 그쪽으로 돌린다."""
    db_file = tmp_path / "test_notes.db"
    monkeypatch.setattr(settings, "db_path", str(db_file))
    init_db()
    yield str(db_file)


@pytest.fixture
def client(temp_db):
    """임시 DB 에 연결된 FastAPI TestClient.

    `with TestClient(app)` 형태로 써야 lifespan(시작 시 init_db)이 실행된다.
    """
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
