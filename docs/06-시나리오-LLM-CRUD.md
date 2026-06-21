# 06 — LLM 으로 메모를 MCP CRUD 하는 시나리오

이 문서는 **사용자가 자연어로 말하면 Gemini(LLM)가 MCP 도구를 골라 메모를
CRUD 하는 과정**을, 흐름도 → 도구별 상세 → 코드 라인 추적 → 엣지케이스 순으로
설명합니다. `/chat` 경로(`app/services/chat_service.py`)가 주인공입니다.

> 비교용으로 `/intent`(LangGraph) 경로는 [docs/05](05-랭그래프-의도파악.md) 와
> 이 문서 마지막 절에서 다룹니다.

---

## 1. 한 장으로 보는 전체 흐름

```
사용자(자연어)
   │  POST /chat {"message": "..."}
   ▼
FastAPI (app/api/routes/chat.py)
   │  service.handle(message)
   ▼
ChatService.handle()  ── 함수 호출 루프(최대 5왕복) ──┐
   │                                                  │
   ▼                                                  │
Gemini  ──"이 도구를 써라(create_note 등)"──►          │
   │                                                  │
   ▼                                                  │
McpSessionManager.call_tool()  (asyncio.Lock 직렬화)   │
   │  stdio                                           │
   ▼                                                  │
MCP 서버 (mcp_server/server.py)                        │
   │  @mcp.tool() 함수 실행                            │
   ▼                                                  │
NoteRepository  →  SQLite (notes.db)                   │
   │  결과(dict/list)                                  │
   └──────── 도구 결과를 대화에 다시 주입 ──────────────┘
   ▼
Gemini  ── 도구가 더 필요 없으면 ──►  자연어 최종 답변
   │
   ▼
사용자  {"reply": "id=1 로 ... 만들었습니다"}
```

**핵심 한 줄**: 사용자는 자연어만 말하고, **무슨 도구를 어떤 인자로 부를지는 Gemini가
판단**하며, **실제 DB 작업은 MCP 도구가** 수행한다.

---

## 2. 5개 도구와 자연어 매핑 (요약표)

MCP 서버가 제공하는 도구 5개(`mcp_server/server.py`)와, 그것을 부르는 자연어 예시.

| 동작 | 사용자 자연어 예시 | Gemini가 고르는 도구 | DB 작업 | 답변 예시 |
|---|---|---|---|---|
| **C**reate | "회의록이라는 메모 만들어줘" | `create_note(title, content?)` | INSERT | "id=1 로 '회의록' 메모를 만들었습니다" |
| **R**ead(전체) | "메모 목록 보여줘" | `list_notes()` | SELECT(전체) | "메모가 3개 있습니다 ..." |
| **R**ead(단건) | "1번 메모 보여줘" | `get_note(note_id)` | SELECT(단건) | "1번 메모: 회의록" |
| **U**pdate | "1번 내용 '완료'로 바꿔줘" | `update_note(note_id, title?, content?)` | UPDATE | "1번 메모를 수정했습니다" |
| **D**elete | "1번 메모 삭제해줘" | `delete_note(note_id)` | DELETE | "1번 메모를 삭제했습니다" |

---

## 3. 도구별 상세 시나리오 (시퀀스)

각 시나리오의 `[n]` 단계는 4절의 코드 라인 추적과 번호가 대응됩니다.

### 3-1. Create — 생성

요청: `POST /chat {"message": "내일 회의 준비라는 제목으로 메모 만들어줘"}`

```
[1] chat.py → ChatService.handle("내일 회의 준비라는 ...")
[2] contents=[user msg]; Gemini 호출(tools=5, temperature=0)
[3] Gemini 판단 → function_calls=[ create_note(title="내일 회의 준비") ]
      (content 미언급 → 인자에서 생략 → 도구 기본값 "")
[4] call_tool("create_note", {"title":"내일 회의 준비"})
      → server.create_note → repo.create → INSERT → SELECT 재조회
      → {"id":1,"title":"내일 회의 준비","content":"",
         "created_at":"2026-..","updated_at":"2026-.."}
[5] 대화에 주입: [model: function_call] + [user: function_response]
[6] Gemini 재호출 → function_calls 없음 → text 생성
[7] reply="id=1 로 '내일 회의 준비' 메모를 만들었습니다."
```

### 3-2. Read(전체) — 목록

요청: `{"message": "메모 목록 보여줘"}`

```
[3] Gemini → function_calls=[ list_notes() ]   (인자 없음)
[4] call_tool("list_notes", {})
      → repo.list() → SELECT * ORDER BY id DESC
      → ★ 리스트 반환이라 structuredContent={"result":[{...},{...}]}
[6] Gemini → "메모가 2개 있습니다. 1) ... 2) ..."
```

> ★ **리스트 vs dict 파싱 차이**: FastMCP 는 리스트 반환 도구(`list_notes`)는
> `structuredContent={"result":[...]}` 에, dict 반환 도구(`create_note` 등)는
> `content[0].text`(JSON 문자열)에 결과를 담는다. 이 둘을 모두 처리하는 곳이
> `ChatService._tool_result_to_dict`(chat_service.py).

### 3-3. Read(단건) — 조회

요청: `{"message": "1번 메모 보여줘"}`

```
[3] Gemini → get_note(note_id=1)   ("1번"에서 id=1 추출)
[4] call_tool("get_note", {"note_id":1})
      → repo.get(1)
      → 있으면 {"id":1,...}
        없으면 {"error":"id=1 메모를 찾을 수 없습니다."}   ← 예외 아님, dict
[6] Gemini → 있으면 "1번 메모: ...",  없으면 "1번 메모를 찾을 수 없습니다."
```

> MCP 도구는 "없음"을 **예외가 아니라 `{"error":...}` dict 로 반환**한다
> (server.py `get_note`). REST 경로가 같은 상황에서 404 예외를 던지는 것과 대조.
> → 6절(엣지케이스) "REST vs MCP 에러 처리 비대칭" 참고.

### 3-4. Update — 수정

요청: `{"message": "1번 메모 내용을 '자료 출력 완료'로 바꿔줘"}`

```
[3] Gemini → update_note(note_id=1, content="자료 출력 완료")
      (title 미언급 → 인자에서 생략)
[4] repo.update(1, title=None, content="자료 출력 완료")
      → title=None 이면 기존 제목 유지(부분 수정), content 교체, updated_at 갱신
[6] Gemini → "1번 메모 내용을 '자료 출력 완료'로 수정했습니다."
```

> **부분 수정 규칙**: 전달 안 한 필드는 `None` 으로 가서 기존 값 유지
> (note_repository.py `update`). "내용만 바꿔줘"가 제목을 지우지 않는 이유.

### 3-5. Delete — 삭제

요청: `{"message": "1번 메모 삭제해줘"}`

```
[3] Gemini → delete_note(note_id=1)
[4] repo.delete(1) → DELETE → rowcount>0 이면 성공
      → {"deleted": true, "note_id": 1}
[6] Gemini → "1번 메모를 삭제했습니다."
      (deleted=false 였다면 "삭제할 메모를 찾지 못했습니다." 류)
```

### 3-6. 멀티턴 — 한 메시지에 도구가 여러 번 (루프의 진가)

요청: `{"message": "빈 메모 다 지워줘"}`

```
[루프1] Gemini → list_notes()                 "먼저 목록을 봐야겠다"
[루프2] 결과 보고 → delete_note(2), delete_note(5)  "빈 건 2,5번이군"
[루프3] 결과 확인 → text "2번, 5번 빈 메모를 삭제했습니다."
```

한 번의 `/chat` 호출 안에서 **도구→결과→재판단**을 반복한다. 이래서 `/chat` 은
단순 도구 1회 호출이 아니라 **agentic 루프**다. 상한은 `MAX_TOOL_TURNS=5`.

---

## 4. 코드 라인 단위 추적

3절의 `[n]` 단계를 실제 코드 위치와 변수 상태로 따라간다.
(라인 번호는 현재 리포 기준 — 코드가 바뀌면 함수명으로 찾으면 된다.)

### 4-0. 사전 준비 (앱 시작 시 1회) — `app/main.py` lifespan

```
main.py:44  async with AsyncExitStack() as stack:
main.py:46    manager = await stack.enter_async_context(McpSessionManager())
                ├─ mcp_session.py __aenter__:
                │    :41  StdioServerParameters(command=sys.executable,
                │            args=[server.py], env=...DB_PATH...)
                │    :47  stdio_client(params) → MCP 서버 subprocess 1회 spawn
                │    :48  ClientSession(read, write)
                │    :49  session.initialize()
                │    :51  self.tool = _build_tool(session)
                │           └─ list_tools() → 5개 → Gemini FunctionDeclaration 변환
main.py:47    app.state.chat_service = ChatService(manager)
```

→ 이 시점에 **MCP 세션과 Gemini 도구 정의가 메모리에 준비**된다. 이후 모든
`/chat` 요청은 이것을 재사용한다(요청당 subprocess 안 띄움).

### 4-1~4-7. 요청 처리 — `app/services/chat_service.py` `handle()`

```
[1] chat.py:27      reply = await service.handle(body.message)

[2] chat_service.py:56  config = GenerateContentConfig(
        :57    temperature=0,
        :58    system_instruction=SYSTEM_INSTRUCTION,   # "너는 메모 관리 비서다..."
        :59    tools=[self._mcp.tool],                  # 4-0에서 만든 도구 재사용
        :60    automatic_function_calling=...(disable=True),  # ← 자동 끔(이유는 아래 ★)
    )
    :65  contents = [ Content(role="user", parts=[Part(text=message)]) ]

[2,6] :70  for _ in range(MAX_TOOL_TURNS):            # 최대 5왕복
    :71      response = await client.aio.models.generate_content(
                 model=settings.gemini_model, contents=contents, config=config)

[3] :77      calls = response.function_calls
    :78      if not calls:                            # 도구 안 부름 → 끝
    :79          return response.text or "(응답이 비어 있습니다)"

[5] :82      contents.append(response.candidates[0].content)   # 모델의 도구호출 턴 추가
    :85      tool_parts = []
    :86      for call in calls:
[4] :87          result = await self._mcp.call_tool(call.name, dict(call.args or {}))
                     └─ mcp_session.py:61 async with self._call_lock:   # 직렬화
                        :62   return await self.session.call_tool(name, arguments)
                            └─ stdio → server.py 의 @mcp.tool() 함수 실행
                               → NoteRepository → SQLite
    :89          tool_parts.append(Part.from_function_response(
                     name=call.name,
                     response=self._tool_result_to_dict(result)))   # ★ 파싱
    :95      contents.append(Content(role="user", parts=tool_parts)) # 결과 턴 추가
             # → 루프 처음으로 돌아가 Gemini 재호출([6])

[7] :97  if response.text: return response.text
    :99  return "(도구 호출이 너무 많아 처리를 중단했습니다)"   # 5왕복 초과 시
```

**★ `_tool_result_to_dict`** (chat_service.py:101) — MCP 결과를 Gemini 가 먹을
dict 로 정규화:
```
:108  if structuredContent is not None: return structuredContent   # list_notes
:110  if content: text=content[0].text; json.loads → dict 반환      # create 등
```

**★ 왜 자동 함수호출을 끄고 루프를 손으로 짰나** (chat_service.py:18-20 주석):
google-genai 가 `config` 를 deepcopy 하는데, `tools=[MCP세션]` 안의 세션이
asyncio Future 를 품고 있어 복사에 실패한다. 그래서 `disable=True` 로 자동을 끄고
도구 변환·호출·결과 주입을 직접 처리한다. (커밋 `c530266`)

### MCP 서버 쪽 — `mcp_server/server.py`

도구는 SQL 을 직접 쓰지 않고 **REST 와 동일한 Repository 를 재사용**한다.
```
server.py:32  repo = NoteRepository()          # ← REST 와 같은 클래스
server.py:36  @mcp.tool() def create_note(...): return asdict(repo.create(...))
server.py:50  @mcp.tool() def list_notes():     return [asdict(n) for n in repo.list()]
server.py:60  @mcp.tool() def get_note(id):     없으면 {"error": ...}
server.py:76  @mcp.tool() def update_note(...): 없으면 {"error": ...}
server.py:94  @mcp.tool() def delete_note(id):  return {"deleted": ok, "note_id": id}
```

→ 사람(REST)이 만든 메모와 AI(MCP)가 만든 메모가 **같은 notes.db** 에 들어가
서로 보인다. 이것이 이 예제가 보여주려는 MCP 의 핵심 가치.

---

## 5. 같은 시나리오를 `/intent`(LangGraph)로 하면

`/chat` 과 달리 **LLM 은 엔티티 추출 1회만**, 나머지는 결정론적.

```
"회의록 메모 만들어줘"
  → extract_entities [LLM] : {action:"create", title:"회의록", content:null}
  → classify_intent  [규칙]: title 있음 → intent="create"
  → execute          [MCP] : create_note(title="회의록", content="")
  → respond          [템플릿/LLM 없음]: "메모를 생성했습니다. (id=1)"
```

| | `/chat` | `/intent` |
|---|---|---|
| LLM 호출 횟수 | 루프마다 (보통 2~6회) | 엔티티 추출 1회 |
| 도구 선택 주체 | Gemini 자율 | 규칙(classify_intent) |
| 답변 생성 | Gemini(자연스러움) | 템플릿(고정) |
| 멀티 도구 | 가능 | 1개 고정 |
| 비용 / 예측성 | 높음 / 낮음 | 낮음 / 높음 |

자세한 그래프는 [docs/05](05-랭그래프-의도파악.md).

---

## 6. 엣지케이스 / 실패·경계 시나리오

LLM 경로에서 실제로 마주치는 경계 상황들.

### 6-1. 없는 id 수정/삭제 — "999번 메모 삭제해줘"
```
[3] delete_note(note_id=999)
[4] repo.delete(999) → rowcount=0 → {"deleted": false, "note_id": 999}
[6] Gemini → "999번 메모를 찾지 못해 삭제하지 못했습니다." 류로 안내
```
update/get 도 마찬가지로 `{"error": "id=999 ..."}` 를 받아 Gemini 가 풀어 설명.
**서버는 죽지 않고 정상 dict 로 실패를 표현** → LLM 이 사용자 친화적으로 전달.

### 6-2. 제목 없는 생성 — "메모 하나 만들어줘" (제목 미지정)
- `/chat`: Gemini 가 제목을 추론해 채우거나, 되물을 수 있음(비결정적).
- **REST `POST /notes`**: `title` `min_length=1` 검증에 걸려 **422**
  (schemas/note.py `NoteCreate`).
- **`/intent`**: `classify_intent` 가 title 없는 create 를 **`unknown`** 으로
  보정 → "요청 의도를 파악하지 못했습니다 ..." 안내(intent_graph.py).
  → 세 경로의 처리 방식이 다르다는 점이 학습 포인트.

### 6-3. 멀티턴 상한 초과 — 도구를 6번 이상 부르려는 경우
`MAX_TOOL_TURNS=5` 왕복을 넘으면 루프 종료 후
`"(도구 호출이 너무 많아 처리를 중단했습니다)"` 반환(chat_service.py:99).
**무한 루프 방지 안전장치.**

### 6-4. Gemini API 오류 (429 쿼터 초과, 5xx 등)
무료 티어 쿼터를 넘기면 google-genai 가 `APIError` 를 던진다.
```
chat.py:28  except genai_errors.APIError as e:
chat.py:30    code = getattr(e,"code",None) or 502
chat.py:31    status_code = code if 400<=code<600 else 502
chat.py:32    raise HTTPException(status_code, "Gemini API 오류: ...")
```
→ 원래 상태코드(예: 429)를 최대한 보존해 깔끔한 HTTP 응답으로 변환.
intent.py 도 동일 처리.

### 6-5. GEMINI_API_KEY 미설정
lifespan 이 `chat_service`/`intent_service` 를 만들지 않음(None).
```
deps.py:28  service = getattr(request.app.state, "chat_service", None)
deps.py:30  if service is None: raise HTTPException(503, "GEMINI_API_KEY ...")
```
→ `/chat`·`/intent` 는 **503**, 하지만 `/notes`(REST)는 **정상 동작**.
키 없이도 REST·MCP 도구 계층은 쓸 수 있다(우아한 성능 저하, graceful degradation).

### 6-6. 동시 요청과 stdio 경합
공유 MCP 세션은 stdio 스트림 하나다. 두 요청이 동시에 도구를 부르면 스트림이
섞일 수 있어 `asyncio.Lock` 으로 **직렬화**한다(mcp_session.py:61).
→ 안전하지만, 이 Lock 이 처리량 병목이 된다(교육 예제 한계; 실제론 세션 풀 필요).

### 6-7. REST vs MCP 에러 처리 비대칭 (설계 의도)
| 상황 | REST(`/notes`) | MCP 도구 |
|---|---|---|
| 없는 메모 조회 | `NoteNotFoundError` → **404** | `{"error": "..."}` **dict** |
| 빈 제목 생성 | pydantic **422** | 도구는 그대로 생성(검증은 LLM/그래프 몫) |

같은 `NoteRepository` 를 쓰지만 **상위 계약이 다르다**: REST 는 HTTP 시맨틱(예외),
MCP 는 LLM 이 읽고 판단할 데이터(dict). 둘 다 맞는 설계 — 소비자가 다르기 때문.

---

## 7. 직접 해보기 (curl)

서버 실행: `uvicorn app.main:app --reload` (사전에 `.env` 에 `GEMINI_API_KEY` 필요)

```bash
# Create
curl -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" \
  -d '{"message":"내일 회의 준비라는 제목으로 메모 만들어줘"}'

# Read (전체)
curl -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" \
  -d '{"message":"메모 목록 보여줘"}'

# Update
curl -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" \
  -d '{"message":"1번 메모 내용을 완료로 바꿔줘"}'

# Delete
curl -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" \
  -d '{"message":"1번 메모 삭제해줘"}'

# 같은 DB 공유 확인 (REST 로도 보임)
curl http://127.0.0.1:8000/notes
```

키 없이 **도구 계층만** 검증하려면(LLM 없이 MCP 서버 직접 호출):
```bash
pytest tests/test_mcp_server_e2e.py -v   # 실제 server.py 를 stdio 로 띄워 CRUD 검증
```

---

## 8. 실제 검증 로그 (이 문서의 주장이 사실임을 증명)

Gemini 키 없이도 **LLM 호출 직전까지의 흐름**과 **도구 계층**은 실제로 검증된다.
아래는 이 리포에서 직접 실행한 결과다.

### 8-1. 테스트 통과 (도구 계층 + REST)
```
tests/test_mcp_server_e2e.py ....                      4 passed   (실제 server.py stdio)
tests/test_notes_api_e2e.py + test_intent.py    23 passed, 1 skipped
                                          (skip = 실제 Gemini 필요한 e2e 1건)
```

### 8-2. MCP 도구 → Gemini FunctionDeclaration 변환 (문서 4-0 단계)
`McpSessionManager` 가 시작 시 만들어 두는, **LLM 이 실제로 보는 도구 정의**:
```
• create_note(title, content)             required=['title']
• list_notes()                            required=[]
• get_note(note_id)                       required=['note_id']
• update_note(note_id, title, content)    required=['note_id']   ← id만 필수(부분 수정)
• delete_note(note_id)                    required=['note_id']
```
→ Gemini 는 이 시그니처를 보고 "어떤 도구를 어떤 인자로" 부를지 판단한다.

### 8-3. 도구 직접 호출 결과 (문서 [4] 단계 / 파싱 비대칭 / 엣지케이스)
```
create_note  → {'id':1, 'title':'데모 메모', 'content':'본문', 'created_at':..., 'updated_at':...}
list_notes   → {'result':[ {...} ]}                  ← ★ 리스트는 result 키로 감쌈(3-2 ★)
get_note(999)→ {'error':'id=999 메모를 찾을 수 없습니다.'}  ← 예외 아닌 dict(6-1)
```
→ 3-2 의 "리스트 vs dict 파싱 차이"와 6-1 의 "없는 id 는 error dict" 가 실제로 그렇다.

> `/chat` 의 LLM 부분(실제 Gemini 호출)은 `GEMINI_API_KEY` 와 `RUN_CHAT_E2E=1` 가
> 있어야 `tests/test_chat_e2e.py` 로 검증된다. 위 8-1~8-3 은 키 없이도 재현 가능.
```
