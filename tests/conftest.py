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
def client(temp_db, monkeypatch):
    """REST 전용 TestClient (Gemini/MCP 비활성).

    REST CRUD 테스트는 Gemini 가 필요 없다. 키를 비워 lifespan 이 MCP 세션을
    띄우지 않게 해(빠르고 격리), 불필요한 subprocess 기동을 막는다.
    """
    monkeypatch.setattr(settings, "gemini_api_key", "")
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def chat_client(temp_db):
    """AI 경로용 TestClient.

    실제 키를 유지하므로 lifespan 이 영속 MCP 세션을 1회 열고, 종료 시 닫는다.
    """
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
