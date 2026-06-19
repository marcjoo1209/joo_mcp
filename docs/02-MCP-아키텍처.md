# 02. MCP 아키텍처

> 대상: MCP의 구성 요소와 통신 흐름을 이해하고 싶은 사람

## 3개의 등장인물: Host / Client / Server

MCP는 세 역할로 구성됩니다.

```
┌─────────────────────────────────────────────┐
│  Host (호스트)  =  우리의 FastAPI 앱           │
│                                               │
│   ┌─────────────────────┐                     │
│   │  Client (클라이언트)  │ ←── 1:1 연결 ──┐    │
│   └─────────────────────┘               │    │
└──────────────────────────────────────────│───┘
                                           │ (stdio: 표준입출력)
                                  ┌────────▼─────────┐
                                  │ Server (서버)     │
                                  │ mcp_server/server │
                                  │  - create_note    │
                                  │  - list_notes     │
                                  │  - ...            │
                                  └──────────────────┘
```

| 역할 | 정의 | 이 예제에서 |
|---|---|---|
| **Host** | AI를 품고 사용자와 대화하는 앱 | FastAPI 앱 (`app/main.py`) + Gemini |
| **Client** | Host 안에서 **서버 하나**와 연결을 담당 | `app/gemini_mcp.py` 의 `ClientSession` |
| **Server** | 도구/데이터를 제공 | `mcp_server/server.py` |

> 한 Host는 여러 Client를 가질 수 있고, 각 Client는 서버 하나와 1:1로 연결됩니다.
> (예: 메모 서버 + 날씨 서버를 동시에 붙이면 Client가 2개)

---

## Transport: Host와 Server는 어떻게 대화하나?

MCP는 주로 두 가지 통신 방식을 씁니다.

| 방식 | 설명 | 언제 |
|---|---|---|
| **stdio** | 서버를 **하위 프로세스로 실행**하고 표준입출력으로 통신 | 로컬에서 함께 돌릴 때 (이 예제) |
| **HTTP (SSE/Streamable)** | 네트워크 너머의 원격 서버와 통신 | 서버가 다른 기계/클라우드에 있을 때 |

이 예제는 **stdio**를 씁니다.
FastAPI 앱이 `python mcp_server/server.py`를 하위 프로세스로 띄우고,
그 프로세스의 입출력 파이프로 JSON-RPC 메시지를 주고받습니다.
별도로 서버를 켜둘 필요가 없어 학습에 편합니다.

---

## 도구 호출 전체 흐름 (가장 중요)

사용자가 `"회의 메모 만들어줘"`라고 했을 때 일어나는 일:

```
1. 사용자 ──"회의 메모 만들어줘"──► FastAPI (/chat)

2. FastAPI ──► MCP 서버 프로세스 실행 + 연결(initialize)

3. Client가 서버에게 "어떤 도구 있어?" (tools/list)
   서버 응답: create_note, list_notes, get_note, update_note, delete_note
   (각 도구의 이름·설명·인자 스키마 포함)

4. FastAPI ──► Gemini 호출
   "사용자 메시지 + 사용 가능한 도구 목록"을 함께 전달

5. Gemini 판단: "create_note 도구를 써야겠다. title='회의 메모'"
   ──► 도구 호출 요청을 반환

6. SDK가 Client를 통해 서버에게 실제 호출 (tools/call: create_note)
   서버가 DB에 INSERT 하고 결과({id:1,...}) 반환

7. 도구 결과를 다시 Gemini에게 전달
   ──► Gemini가 최종 자연어 답변 생성
       "id=1로 '회의 메모'를 만들었습니다."

8. FastAPI ──► 사용자에게 답변 반환
```

**핵심 3가지**
- **3번 (도구 발견)**: 서버가 스스로 "내가 가진 도구는 이거다"라고 알려줌 → AI가 미리 알 필요 없음
- **5번 (판단)**: 어떤 도구를 쓸지는 **AI가 결정**. 우리는 if-else를 짜지 않음
- **6번 (실행)**: 실제 일(DB 작업)은 **서버 도구**가 함. AI는 "시키기"만 함

> 이 예제에서는 `google-genai` SDK가 **3~7번을 자동으로** 처리합니다.
> (코드: `tools=[session]` 한 줄. 자세한 내용은 다음 문서에서.)

---

## JSON-RPC 메시지 (참고)

내부적으로 오가는 메시지는 JSON-RPC 2.0 형식입니다. 예:

```jsonc
// Client → Server : 도구 호출
{ "jsonrpc": "2.0", "id": 7, "method": "tools/call",
  "params": { "name": "create_note", "arguments": { "title": "회의 메모", "content": "" } } }

// Server → Client : 결과
{ "jsonrpc": "2.0", "id": 7,
  "result": { "content": [ { "type": "text", "text": "{\"id\":1, ...}" } ] } }
```

이 메시지를 직접 다룰 일은 거의 없습니다. SDK가 처리해 줍니다.

---

다음 문서 → [03. 이 프로젝트 동작 방식](03-프로젝트-동작-방식.md)
