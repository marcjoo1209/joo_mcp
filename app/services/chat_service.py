"""
챗 서비스 (Service 계층) — FastAPI ↔ Gemini ↔ MCP 오케스트레이션

이 프로젝트의 핵심 로직입니다.
  자연어 메시지 → Gemini 에 MCP 도구를 함께 전달 → Gemini 가 도구 호출 → 자연어 답변

구현 방식(함수 호출 루프, function calling loop):
  1) MCP 서버에서 도구 목록을 받아 Gemini 의 FunctionDeclaration 으로 변환한다.
  2) Gemini 를 호출한다. Gemini 가 "이 도구를 써라"라고 하면,
  3) 그 도구를 MCP 세션으로 실제 실행하고, 결과를 Gemini 에 돌려준다.
  4) Gemini 가 더는 도구를 부르지 않을 때까지 2~3을 반복한 뒤 최종 답변을 낸다.

  ※ google-genai 에는 MCP 세션을 tools 로 바로 넘기는 '자동' 기능도 있지만,
     현재 버전(2.8.0)은 config 를 deepcopy 하다가 MCP 세션(asyncio Future)을
     복사하지 못해 실패한다. 그래서 여기서는 변환/호출을 직접 다뤄 버전에
     안정적이고, '자동' 기능이 내부에서 무엇을 하는지도 드러나게 했다.
"""

import json
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

# 한 요청에서 허용하는 최대 도구 호출 왕복 횟수 (무한 루프 방지).
MAX_TOOL_TURNS = 5


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
        """
        async with stdio_client(self._server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # 1) MCP 도구 목록 → Gemini 도구로 변환
                tool = await self._build_gemini_tool(session)
                config = types.GenerateContentConfig(
                    temperature=0,
                    system_instruction=SYSTEM_INSTRUCTION,
                    tools=[tool],
                    # 우리가 도구 호출 루프를 직접 돌리므로 SDK 자동 호출은 끈다.
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        disable=True
                    ),
                )

                contents: list[types.Content] = [
                    types.Content(role="user", parts=[types.Part(text=message)])
                ]

                # 2~4) 도구 호출 루프
                response = None
                for _ in range(MAX_TOOL_TURNS):
                    response = await self._client.aio.models.generate_content(
                        model=settings.gemini_model,
                        contents=contents,
                        config=config,
                    )

                    calls = response.function_calls
                    if not calls:
                        # 더 부를 도구가 없다 → 최종 답변
                        return response.text or "(응답이 비어 있습니다)"

                    # 모델이 만든 '도구 호출' 턴을 대화에 추가
                    contents.append(response.candidates[0].content)

                    # 각 도구를 MCP 로 실제 실행하고 결과를 모은다
                    tool_parts = []
                    for call in calls:
                        result = await session.call_tool(call.name, dict(call.args or {}))
                        tool_parts.append(
                            types.Part.from_function_response(
                                name=call.name,
                                response=self._tool_result_to_dict(result),
                            )
                        )
                    # 도구 결과 턴을 대화에 추가 (Gemini 는 role="user" 로 받음)
                    contents.append(types.Content(role="user", parts=tool_parts))

                # 루프 한계 초과
                if response is not None and response.text:
                    return response.text
                return "(도구 호출이 너무 많아 처리를 중단했습니다)"

    @staticmethod
    async def _build_gemini_tool(session: ClientSession) -> types.Tool:
        """MCP 서버의 도구 목록을 Gemini FunctionDeclaration 으로 변환한다."""
        mcp_tools = (await session.list_tools()).tools
        declarations = [
            types.FunctionDeclaration(
                name=t.name,
                description=t.description or "",
                # MCP 의 inputSchema(JSON Schema)를 그대로 전달.
                parameters_json_schema=t.inputSchema,
            )
            for t in mcp_tools
        ]
        return types.Tool(function_declarations=declarations)

    @staticmethod
    def _tool_result_to_dict(call_result) -> dict:
        """MCP 도구 실행 결과를 Gemini function_response 용 dict 로 변환한다.

        - 리스트 반환 도구: structuredContent = {"result": [...]} → 그대로 사용
        - dict 반환 도구:   content[0].text(JSON) 파싱
        """
        if call_result.structuredContent is not None:
            return call_result.structuredContent
        if call_result.content:
            text = call_result.content[0].text
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                return {"result": text}
            return data if isinstance(data, dict) else {"result": data}
        return {"result": None}
