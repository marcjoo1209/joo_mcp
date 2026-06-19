"""
의도 파악 서비스 (LangGraph)

목적: 자연어에서 **엔티티를 추출**해 **사용자의 질문 의도**를 파악하고,
      그 의도에 따라 **결정론적으로** 알맞은 MCP 도구를 실행한다.

`/chat`(기존)과의 차이:
  - /chat   : Gemini 가 어떤 도구를 쓸지 '직접' 정한다(유연하지만 덜 예측적).
  - /intent : 그래프가 '엔티티 추출 → 의도 분류 → 라우팅 → 실행 → 응답'을
              명시적 단계로 처리한다(예측 가능, 각 단계 관찰 가능).

LangGraph 그래프 구조:

    START → extract_entities → classify_intent → execute → respond → END
            (Gemini 구조화 추출)  (규칙 기반)      (MCP 호출)  (템플릿)

  - LLM 호출은 extract_entities 한 단계뿐(엔티티 추출). 나머지는 결정론적.
  - 상태(IntentState)가 노드들을 따라 흐르며 채워진다.
"""

import json
from typing import Any, TypedDict

from google import genai
from google.genai import types
from langgraph.graph import END, START, StateGraph

from app.core.config import settings
from app.schemas.note import ExtractedEntities
from app.services.mcp_session import McpSessionManager

EXTRACTION_PROMPT = (
    "다음 한국어 요청에서 메모(note) 작업 의도를 추출해라.\n"
    "- action: 새로 만들기=create, 전체 목록=read_all, 특정 메모 조회=read_one, "
    "수정=update, 삭제=delete, 해당 없음=unknown\n"
    "- note_id: '3번', 'id 3' 처럼 대상 메모 번호가 있으면 정수로, 없으면 비움\n"
    "- title/content: 제목·내용이 명시되면 채우고, 없으면 비움\n\n"
    "요청: {message}"
)


class IntentState(TypedDict, total=False):
    """그래프를 따라 흐르는 상태."""

    message: str
    entities: ExtractedEntities
    intent: str
    result: Any
    reply: str


class IntentService:
    """LangGraph 로 엔티티 기반 의도 파악 + MCP 실행을 수행한다."""

    def __init__(self, session_manager: McpSessionManager) -> None:
        if not settings.gemini_api_key:
            raise RuntimeError(
                "GEMINI_API_KEY 가 설정되지 않았습니다. .env 파일을 확인하세요."
            )
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._mcp = session_manager
        self._graph = self._build_graph()

    # ---- 그래프 정의 ----
    def _build_graph(self):
        builder = StateGraph(IntentState)
        builder.add_node("extract_entities", self._extract_entities)
        builder.add_node("classify_intent", self._classify_intent)
        builder.add_node("execute", self._execute)
        builder.add_node("respond", self._respond)

        builder.add_edge(START, "extract_entities")
        builder.add_edge("extract_entities", "classify_intent")
        builder.add_edge("classify_intent", "execute")
        builder.add_edge("execute", "respond")
        builder.add_edge("respond", END)
        return builder.compile()

    async def analyze(self, message: str) -> IntentState:
        """그래프를 실행하고 최종 상태(엔티티/의도/결과/답변)를 반환한다."""
        return await self._graph.ainvoke({"message": message})

    # ---- 노드들 ----
    async def _extract_entities(self, state: IntentState) -> dict:
        """[LLM] Gemini 구조화 출력으로 엔티티를 추출한다."""
        response = await self._client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=EXTRACTION_PROMPT.format(message=state["message"]),
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
                response_schema=ExtractedEntities,
            ),
        )
        entities = response.parsed
        if not isinstance(entities, ExtractedEntities):
            # 안전장치: 파싱 실패 시 unknown 으로
            entities = ExtractedEntities(action="unknown")
        return {"entities": entities}

    @staticmethod
    def _classify_intent(state: IntentState) -> dict:
        """[규칙] 엔티티로부터 의도를 확정한다(엔티티 보정 포함)."""
        e = state["entities"]
        action = e.action
        # 보정: read 인데 note_id 가 있으면 단건, 없으면 전체
        if action == "read_one" and e.note_id is None:
            action = "read_all"
        # 보정: id 가 필요한 동작인데 없으면 unknown 처리
        if action in ("read_one", "update", "delete") and e.note_id is None:
            action = "unknown"
        if action == "create" and not e.title:
            action = "unknown"
        return {"intent": action}

    async def _execute(self, state: IntentState) -> dict:
        """[MCP] 의도에 맞는 도구를 결정론적으로 호출한다."""
        e = state["entities"]
        intent = state["intent"]

        async def call(name: str, args: dict):
            return self._tool_to_obj(await self._mcp.call_tool(name, args))

        if intent == "create":
            result = await call("create_note", {"title": e.title, "content": e.content or ""})
        elif intent == "read_all":
            result = await call("list_notes", {})
        elif intent == "read_one":
            result = await call("get_note", {"note_id": e.note_id})
        elif intent == "update":
            args: dict = {"note_id": e.note_id}
            if e.title is not None:
                args["title"] = e.title
            if e.content is not None:
                args["content"] = e.content
            result = await call("update_note", args)
        elif intent == "delete":
            result = await call("delete_note", {"note_id": e.note_id})
        else:  # unknown
            result = None
        return {"result": result}

    @staticmethod
    def _respond(state: IntentState) -> dict:
        """[템플릿] 결과를 결정론적 한국어 답변으로 만든다(LLM 미사용)."""
        intent = state["intent"]
        result = state.get("result")

        if intent == "create":
            reply = f"메모를 생성했습니다. (id={result.get('id')})"
        elif intent == "read_all":
            items = result.get("result", []) if isinstance(result, dict) else result
            reply = f"메모가 {len(items)}개 있습니다."
        elif intent == "read_one":
            if isinstance(result, dict) and "error" in result:
                reply = result["error"]
            else:
                reply = f"메모 #{result.get('id')}: {result.get('title')}"
        elif intent == "update":
            if isinstance(result, dict) and "error" in result:
                reply = result["error"]
            else:
                reply = f"메모 #{result.get('id')} 를 수정했습니다."
        elif intent == "delete":
            ok = isinstance(result, dict) and result.get("deleted")
            reply = "메모를 삭제했습니다." if ok else "삭제할 메모를 찾지 못했습니다."
        else:
            reply = (
                "요청 의도를 파악하지 못했습니다. "
                "예: '회의록 메모 만들어줘', '메모 목록 보여줘', '3번 메모 삭제해줘'"
            )
        return {"reply": reply}

    @staticmethod
    def _tool_to_obj(call_result) -> Any:
        """MCP 도구 결과 → 파이썬 객체.

        - 리스트 반환(list_notes): structuredContent = {"result": [...]}
        - dict 반환: content[0].text(JSON) 파싱
        """
        if call_result.structuredContent is not None:
            return call_result.structuredContent
        if call_result.content:
            try:
                return json.loads(call_result.content[0].text)
            except json.JSONDecodeError:
                return {"result": call_result.content[0].text}
        return None
