"""
챗 서비스 (Service 계층) — FastAPI ↔ Gemini ↔ MCP 오케스트레이션

이 프로젝트의 핵심 로직입니다.
  자연어 메시지 → Gemini 에 MCP 도구를 함께 전달 → Gemini 가 도구 호출 → 자연어 답변

구현 방식(함수 호출 루프, function calling loop):
  1) (시작 시 1회) MCP 도구 목록을 Gemini FunctionDeclaration 으로 변환해 둔다.
  2) Gemini 를 호출한다. Gemini 가 "이 도구를 써라"라고 하면,
  3) 그 도구를 MCP 세션으로 실제 실행하고, 결과를 Gemini 에 돌려준다.
  4) Gemini 가 더는 도구를 부르지 않을 때까지 2~3을 반복한 뒤 최종 답변을 낸다.

성능 메모:
  MCP 세션과 도구 변환은 McpSessionManager 가 앱 수명 동안 '재사용'한다.
  요청마다 subprocess 를 띄우던 비용이 사라진다(지연 절감). 단, 토큰 비용은
  컨텍스트 캐싱 영역이며 현재 prefix 크기에선 이득이 없다(docs/04 참고).

  ※ google-genai 에는 MCP 세션을 tools 로 바로 넘기는 '자동' 기능도 있지만,
     현재 버전(2.8.0)은 config 를 deepcopy 하다가 MCP 세션(asyncio Future)을
     복사하지 못해 실패한다. 그래서 변환/호출을 직접 다룬다.
"""

import json

from google import genai
from google.genai import types

from app.core.config import settings
from app.services.mcp_session import McpSessionManager

SYSTEM_INSTRUCTION = (
    "너는 메모(note) 관리 비서다. "
    "사용자의 요청을 이해하고, 필요할 때 제공된 도구를 사용해서 "
    "메모를 생성/조회/수정/삭제한 뒤 결과를 한국어로 간결하게 설명한다. "
    "도구 실행 결과(예: 생성된 메모의 id)를 답변에 자연스럽게 포함한다."
)

# 한 요청에서 허용하는 최대 도구 호출 왕복 횟수 (무한 루프 방지).
MAX_TOOL_TURNS = 5


class ChatService:
    """Gemini + (영속) MCP 세션을 묶어 자연어 요청을 처리한다."""

    def __init__(self, session_manager: McpSessionManager) -> None:
        if not settings.gemini_api_key:
            raise RuntimeError(
                "GEMINI_API_KEY 가 설정되지 않았습니다. .env 파일을 확인하세요."
            )
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._mcp = session_manager  # 앱 수명 동안 공유되는 MCP 세션

    async def handle(self, message: str) -> str:
        """자연어 메시지를 처리해 자연어 답변을 반환한다."""
        # 시작 시 변환해 둔 도구를 재사용 (요청마다 list_tools 하지 않음).
        config = types.GenerateContentConfig(
            temperature=0,
            system_instruction=SYSTEM_INSTRUCTION,
            tools=[self._mcp.tool],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        )

        contents: list[types.Content] = [
            types.Content(role="user", parts=[types.Part(text=message)])
        ]

        response = None
        for _ in range(MAX_TOOL_TURNS):
            response = await self._client.aio.models.generate_content(
                model=settings.gemini_model,
                contents=contents,
                config=config,
            )

            calls = response.function_calls
            if not calls:
                return response.text or "(응답이 비어 있습니다)"

            # 모델의 '도구 호출' 턴을 대화에 추가
            contents.append(response.candidates[0].content)

            # 각 도구를 공유 MCP 세션으로 실행하고 결과를 모은다
            tool_parts = []
            for call in calls:
                result = await self._mcp.call_tool(call.name, dict(call.args or {}))
                tool_parts.append(
                    types.Part.from_function_response(
                        name=call.name,
                        response=self._tool_result_to_dict(result),
                    )
                )
            # 도구 결과 턴을 대화에 추가 (Gemini 는 role="user" 로 받음)
            contents.append(types.Content(role="user", parts=tool_parts))

        if response is not None and response.text:
            return response.text
        return "(도구 호출이 너무 많아 처리를 중단했습니다)"

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
