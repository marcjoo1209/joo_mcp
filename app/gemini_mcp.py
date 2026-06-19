"""
Gemini <-> MCP 연결 부분 (이 프로젝트의 핵심)

흐름:
  사용자 자연어 메시지
    -> FastAPI (/chat)
    -> 이 모듈의 chat_with_tools()
    -> Gemini API 에 "MCP 서버의 도구들"을 함께 넘김
    -> Gemini 가 필요하다고 판단하면 MCP 도구(create_note 등)를 자동 호출
    -> 도구 실행 결과(CRUD 수행)를 다시 Gemini 가 읽고 최종 답변 생성
    -> 사람이 읽을 수 있는 자연어 답변을 반환

핵심 포인트:
  google-genai SDK 는 MCP 의 ClientSession 객체를 tools 로 그대로 받을 수 있다.
  그러면 SDK 가 "도구 목록 조회 -> 호출 -> 결과 전달" 과정을 자동으로 처리한다.
  (즉, 우리가 직접 function-calling 루프를 돌리지 않아도 된다.)
"""

import os
import sys

from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 우리가 사용할 Gemini 모델.
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# MCP 서버(server.py)의 절대 경로. 이 파일을 하위 프로세스로 실행해서 연결한다.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SERVER_PATH = os.path.join(_PROJECT_ROOT, "mcp_server", "server.py")

SYSTEM_INSTRUCTION = (
    "너는 메모(note) 관리 비서다. "
    "사용자의 요청을 이해하고, 필요할 때 제공된 도구를 사용해서 "
    "메모를 생성/조회/수정/삭제한 뒤 결과를 한국어로 간결하게 설명한다. "
    "도구 실행 결과(예: 생성된 메모의 id)를 답변에 자연스럽게 포함한다."
)


def _build_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY 환경변수가 없습니다. .env 파일에 키를 설정하세요."
        )
    return genai.Client(api_key=api_key)


async def chat_with_tools(message: str) -> str:
    """자연어 메시지를 받아 Gemini + MCP 도구로 처리하고 자연어 답변을 반환한다.

    교육용으로 단순하게, 요청마다 MCP 서버 프로세스를 새로 띄우고 닫는다.
    (운영 환경이라면 세션을 재사용해 성능을 높일 수 있다.)
    """
    client = _build_client()

    # MCP 서버를 어떻게 실행할지 정의: 현재 파이썬으로 server.py 실행
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[_SERVER_PATH],
    )

    # 1) MCP 서버 프로세스를 띄우고 stdio 로 연결
    async with stdio_client(server_params) as (read, write):
        # 2) MCP 세션 생성 및 핸드셰이크(initialize)
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 3) Gemini 호출 - tools 에 MCP 세션을 그대로 넘긴다.
            #    SDK 가 도구 호출을 자동으로 처리(automatic function calling).
            response = await client.aio.models.generate_content(
                model=MODEL,
                contents=message,
                config=types.GenerateContentConfig(
                    temperature=0,
                    system_instruction=SYSTEM_INSTRUCTION,
                    tools=[session],
                ),
            )

    return response.text or "(응답이 비어 있습니다)"
