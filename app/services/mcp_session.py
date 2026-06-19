"""
MCP 세션 매니저 (세션 영속화로 요청당 오버헤드 제거)

[기존] /chat 요청마다 MCP 서버 subprocess 를 새로 spawn + initialize 했다.
       → 요청마다 프로세스 기동 지연 + 도구 목록 재조회.
[개선] 앱 시작(lifespan) 시 MCP 세션을 '한 번만' 열고, 모든 요청이 재사용한다.
       → subprocess/initialize/도구변환을 1회만. 지연·CPU·메모리 절감.

⚠️ 토큰(돈) 절감과는 별개다. 토큰 비용은 컨텍스트 캐싱 영역이며,
   이 예제의 반복 prefix(시스템+도구)는 약 744토큰으로 캐시 임계값(1,024)
   미만이라 현재는 캐싱 이득이 없다. (docs/04-비용과-세션-최적화.md 참고)

[anyio 규칙] stdio_client 가 만드는 task group 은 '연 task 에서 닫아야' 한다.
   그래서 이 매니저는 lifespan 안에서 async with 로 열고 닫는다(같은 task).
   요청 핸들러(다른 task)에서는 session.call_tool 만 호출한다(허용됨).
"""

import asyncio
import contextlib
import os
import sys

from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.core.config import settings


class McpSessionManager:
    """앱 수명 동안 살아 있는 단일 MCP 세션 + 변환된 Gemini 도구."""

    def __init__(self) -> None:
        self._stack = contextlib.AsyncExitStack()
        self.session: ClientSession | None = None
        self.tool: types.Tool | None = None
        # 공유 세션에 여러 요청의 도구 호출이 뒤섞이지 않도록 직렬화한다.
        self._call_lock = asyncio.Lock()

    async def __aenter__(self) -> "McpSessionManager":
        params = StdioServerParameters(
            command=sys.executable,
            args=[settings.mcp_server_path],
            env={**os.environ, "DB_PATH": settings.db_path},
        )
        # stdio_client 와 ClientSession 을 같은 task(lifespan)에서 연다.
        read, write = await self._stack.enter_async_context(stdio_client(params))
        self.session = await self._stack.enter_async_context(ClientSession(read, write))
        await self.session.initialize()
        # 도구 목록 조회 + Gemini 도구 변환을 시작 시 1회만 수행해 캐싱.
        self.tool = await self._build_tool(self.session)
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self._stack.aclose()
        self.session = None
        self.tool = None

    async def call_tool(self, name: str, arguments: dict):
        """공유 세션으로 MCP 도구를 호출한다(직렬화)."""
        async with self._call_lock:
            return await self.session.call_tool(name, arguments)

    @staticmethod
    async def _build_tool(session: ClientSession) -> types.Tool:
        """MCP 도구 목록 → Gemini FunctionDeclaration 으로 변환."""
        mcp_tools = (await session.list_tools()).tools
        return types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name=t.name,
                    description=t.description or "",
                    parameters_json_schema=t.inputSchema,
                )
                for t in mcp_tools
            ]
        )
