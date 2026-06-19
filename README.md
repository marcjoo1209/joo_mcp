# joo_mcp — FastAPI + Gemini + MCP 학습 예제

MCP를 처음 접하는 사람도 따라 할 수 있도록 만든 교육용 예제입니다.
**자연어로 메모(note)를 CRUD** 하는 작은 앱을 만들면서 MCP의 핵심을 익힙니다.

```
사용자: "내일 회의 준비라는 메모 만들어줘"
   │
   ▼  (HTTP POST /chat)
FastAPI 앱  ──►  Gemini API  ──►  MCP 서버(도구: create_note 등)  ──►  SQLite DB
   │                                                                      │
   ◄──────────────  "id=1 로 '내일 회의 준비' 메모를 만들었습니다" ◄──────────┘
```

---

## 1. 먼저 읽어보세요 (MCP 개념)

MCP가 처음이라면 아래 문서를 순서대로 읽으면 됩니다.

| 순서 | 문서 | 내용 |
|---|---|---|
| 1 | [docs/01-MCP란-무엇인가.md](docs/01-MCP란-무엇인가.md) | MCP가 무엇이고 왜 필요한가 (비유로 설명) |
| 2 | [docs/02-MCP-아키텍처.md](docs/02-MCP-아키텍처.md) | Host / Client / Server 구조와 도구 호출 흐름 |
| 3 | [docs/03-프로젝트-동작-방식.md](docs/03-프로젝트-동작-방식.md) | 이 코드가 실제로 어떻게 동작하는지 줄줄이 설명 |

---

## 2. 프로젝트 구조 (표준 레이어드 아키텍처)

요청은 위에서 아래로만 흐릅니다: **Router → Service → Repository → DB**

```
joo_mcp/
├── README.md
├── requirements.txt
├── .env.example
│
├── docs/                          ← MCP 교육 자료
│   ├── 01-MCP란-무엇인가.md
│   ├── 02-MCP-아키텍처.md
│   └── 03-프로젝트-동작-방식.md
│
├── mcp_server/
│   └── server.py                  ← ★ MCP 서버: 메모 CRUD 도구 5개 (Repository 재사용)
│
└── app/
    ├── main.py                    ← ★ 앱 팩토리: 라우터/예외/lifespan 조립
    ├── core/
    │   ├── config.py              ←   설정(pydantic-settings)
    │   └── exceptions.py          ←   도메인 예외
    ├── api/
    │   ├── deps.py                ←   의존성 주입(DI) 제공자
    │   └── routes/
    │       ├── notes.py           ←   /notes 라우터 (직접 REST CRUD)
    │       └── chat.py            ←   /chat 라우터 (AI CRUD)
    ├── services/
    │   ├── note_service.py        ←   메모 비즈니스 로직
    │   └── chat_service.py        ← ★ Gemini ↔ MCP 오케스트레이션 (핵심)
    ├── repositories/
    │   └── note_repository.py     ← ★ 데이터 접근(SQL). REST와 MCP가 공유
    ├── models/note.py             ←   도메인 모델
    ├── schemas/note.py            ←   요청/응답 DTO
    └── db/database.py             ←   DB 연결/초기화
```

★ 표시가 핵심 파일입니다. 계층별 책임은
[docs/03-프로젝트-동작-방식.md](docs/03-프로젝트-동작-방식.md)에서 코드와 함께 설명합니다.

---

## 3. 설치 및 실행

### (1) 가상환경 + 패키지 설치

```powershell
# Windows PowerShell 기준
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### (2) API 키 설정

[Google AI Studio](https://aistudio.google.com/apikey)에서 Gemini API 키를 발급받은 뒤:

```powershell
copy .env.example .env      # macOS/Linux: cp .env.example .env
```

`.env` 파일을 열어 `GEMINI_API_KEY` 값을 채웁니다.

### (3) 서버 실행

```bash
uvicorn app.main:app --reload
```

> MCP 서버(`mcp_server/server.py`)는 따로 실행하지 않습니다.
> FastAPI 앱이 필요할 때 자동으로 하위 프로세스로 띄웁니다.

실행 후 브라우저에서 **http://127.0.0.1:8000/docs** 를 열면
Swagger UI로 모든 API를 직접 눌러볼 수 있습니다.

---

## 4. 사용해보기

### A. 직접 REST CRUD (MCP/AI 없이)

```bash
# Create
curl -X POST http://127.0.0.1:8000/notes -H "Content-Type: application/json" -d "{\"title\":\"장보기\",\"content\":\"우유, 계란\"}"

# Read (전체)
curl http://127.0.0.1:8000/notes

# Update
curl -X PUT http://127.0.0.1:8000/notes/1 -H "Content-Type: application/json" -d "{\"content\":\"우유, 계란, 빵\"}"

# Delete
curl -X DELETE http://127.0.0.1:8000/notes/1
```

### B. AI 기반 CRUD (FastAPI → Gemini → MCP)

```bash
curl -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" -d "{\"message\":\"내일 회의 준비라는 제목으로 메모 만들어줘\"}"

curl -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" -d "{\"message\":\"메모 목록 보여줘\"}"

curl -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" -d "{\"message\":\"1번 메모 삭제해줘\"}"
```

`/chat`으로 만든 메모는 `GET /notes`로도 똑같이 보입니다.
**같은 DB를 사람과 AI가 공유**하기 때문입니다. — 이것이 MCP의 핵심 가치입니다.

---

## 5. 테스트 (e2e)

CRUD 전체를 두 경로로 검증하는 e2e 테스트가 `tests/` 에 있습니다.
각 테스트는 **임시 SQLite 파일**로 격리되어 실제 `notes.db` 를 건드리지 않습니다.

```powershell
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

| 파일 | 검증 대상 |
|---|---|
| `tests/test_notes_api_e2e.py` | 직접 REST CRUD (생성/조회/수정/삭제 + 404·422) |
| `tests/test_mcp_server_e2e.py` | MCP 서버 도구 CRUD (실제 서버를 stdio 로 띄워 호출) |
| `tests/test_chat_e2e.py` | AI 경로(FastAPI→Gemini→MCP). 기본 SKIP |

`test_chat_e2e.py` 는 실제 Gemini 를 호출하므로 비용/비결정성 때문에 기본으로 건너뜁니다.
돌리려면 `GEMINI_API_KEY` 설정 후:

```powershell
$env:RUN_CHAT_E2E="1"; pytest tests/test_chat_e2e.py -v
```

---

## 6. 무엇을 배우게 되나요?

- **MCP 서버 만들기**: `@mcp.tool()` 로 함수를 AI가 쓸 수 있는 도구로 노출
- **MCP 클라이언트 연결**: stdio 로 서버 프로세스를 띄우고 세션 연결
- **Gemini 도구 연동**: MCP 도구를 Gemini FunctionDeclaration 으로 변환하고 함수 호출 루프로 실행
- **CRUD 설계**: 같은 데이터 저장소를 REST API 와 AI 도구가 함께 사용
