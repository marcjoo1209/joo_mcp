"""
애플리케이션 설정 (Configuration 계층)

표준 아키텍처에서는 환경변수/설정을 한곳에 모아 관리합니다.
여기서는 pydantic-settings 로 .env 파일과 환경변수를 읽어 타입 검증까지 합니다.
다른 모듈은 `from app.core.config import settings` 로 설정을 주입받습니다.
"""

import os

from pydantic_settings import BaseSettings, SettingsConfigDict

# 프로젝트 루트(joo_mcp/) 경로. 이 파일: app/core/config.py → 세 번 상위.
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)


class Settings(BaseSettings):
    """환경변수/.env 에서 읽어오는 설정 값."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # 데이터베이스
    db_path: str = os.path.join(PROJECT_ROOT, "notes.db")

    # MCP 서버 실행 경로 (stdio 로 띄울 server.py)
    mcp_server_path: str = os.path.join(PROJECT_ROOT, "mcp_server", "server.py")


# 앱 전역에서 공유하는 단일 설정 인스턴스.
settings = Settings()
