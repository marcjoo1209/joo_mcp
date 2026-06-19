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

## 2. 프로젝트 구조

```
joo_mcp/
├── README.md                ← 지금 이 문서
├── requirements.txt         ← 설치할 파이썬 패키지
├── .env.example             ← 환경변수 템플릿 (복사해서 .env 로)
│
├── docs/                    ← MCP 교육 자료
│   ├── 01-MCP란-무엇인가.md
│   ├── 02-MCP-아키텍처.md
│   └── 03-프로젝트-동작-방식.md
│
├── common/
│   └── database.py          ← 공용 SQLite CRUD (서버/앱이 함께 사용)
│
├── mcp_server/
│   └── server.py            ← ★ MCP 서버: 메모 CRUD 도구 5개 제공
│
└── app/
    ├── main.py              ← ★ FastAPI: REST CRUD + /chat (AI CRUD)
    └── gemini_mcp.py        ← ★ Gemini ↔ MCP 연결 (핵심 로직)
```

★ 표시가 직접 들여다봐야 할 핵심 파일입니다.

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

## 5. 무엇을 배우게 되나요?

- **MCP 서버 만들기**: `@mcp.tool()` 로 함수를 AI가 쓸 수 있는 도구로 노출
- **MCP 클라이언트 연결**: stdio 로 서버 프로세스를 띄우고 세션 연결
- **Gemini 도구 연동**: `google-genai` SDK 에 MCP 세션을 `tools` 로 넘겨 자동 호출
- **CRUD 설계**: 같은 데이터 저장소를 REST API 와 AI 도구가 함께 사용
