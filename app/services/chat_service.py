"""
챗 서비스 (Service 계층) — FastAPI ↔ Gemini ↔ MCP 오케스트레이션

이 프로젝트의 핵심 로직입니다.
  자연어 메시지 → Gemini 에 MCP 도구를 함께 전달 → Gemini 가 도구 자동 호출 → 자연어 답변

핵심: google-genai SDK 는 MCP 의 ClientSession 을 tools 로 직접 받을 수 있어,
'도구 목록 조회 → 호출 → 결과 전달' 루프를 SDK 가 자동 처리한다.
"""

import os
import sys

from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.core.config import settings

SYSTEM_INSTRUCTION = (
    "너는 메모(note) 관리 비서다. "
    "사용자의 요청을 이해하고, 필요할 때 제공된 도구를 사용해서 "
    "메모를 생성/조회/수정/삭제한 뒤 결과를 한국어로 간결하게 설명한다. "
    "도구 실행 결과(예: 생성된 메모의 id)를 답변에 자연스럽게 포함한다."
)


class ChatService:
    """Gemini + MCP 를 묶어 자연어 요청을 처리한다."""

    def __init__(self) -> None:
        if not settings.gemini_api_key:
            # API 키가 없으면 호출 시점이 아니라 생성 시점에 명확히 알린다.
            raise RuntimeError(
                "GEMINI_API_KEY 가 설정되지 않았습니다. .env 파일을 확인하세요."
            )
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._server_params = StdioServerParameters(
            command=sys.executable,
            args=[settings.mcp_server_path],
            # 앱과 MCP 서버가 같은 DB 를 쓰도록 db_path 를 자식 프로세스에 전달.
            env={**os.environ, "DB_PATH": settings.db_path},
        )

    async def handle(self, message: str) -> str:
        """자연어 메시지를 처리해 자연어 답변을 반환한다.

        교육용으로 요청마다 MCP 서버 프로세스를 새로 띄우고 닫는다.
        (운영 환경이라면 세션을 재사용해 성능을 높일 수 있다.)
        """
        # 1) MCP 서버 프로세스 실행 + stdio 연결
        async with stdio_client(self._server_params) as (read, write):
            # 2) MCP 세션 핸드셰이크
            async with ClientSession(read, write) as session:
                await session.initialize()

                # 3) Gemini 호출 — MCP 세션을 tools 로 직접 전달(자동 도구 호출)
                response = await self._client.aio.models.generate_content(
                    model=settings.gemini_model,
                    contents=message,
                    config=types.GenerateContentConfig(
                        temperature=0,
                        system_instruction=SYSTEM_INSTRUCTION,
                        tools=[session],
                    ),
                )

        return response.text or "(응답이 비어 있습니다)"
