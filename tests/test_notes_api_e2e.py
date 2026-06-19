"""
REST CRUD e2e 테스트 (Presentation → Service → Repository → DB 전 계층)

실제 HTTP 요청을 TestClient 로 보내, 응답과 DB 상태 변화를 검증한다.
모든 테스트는 `client` 픽스처(임시 DB)로 격리된다.
"""


def test_create_note(client):
    """[Create] 메모 생성 → 201 + 본문 반환."""
    res = client.post("/notes", json={"title": "회의록", "content": "안건 정리"})
    assert res.status_code == 201
    body = res.json()
    assert body["id"] >= 1
    assert body["title"] == "회의록"
    assert body["content"] == "안건 정리"
    assert body["created_at"] and body["updated_at"]


def test_create_note_default_content(client):
    """content 생략 시 빈 문자열로 생성된다."""
    res = client.post("/notes", json={"title": "제목만"})
    assert res.status_code == 201
    assert res.json()["content"] == ""


def test_list_notes_empty(client):
    """[Read] 메모가 없으면 빈 목록."""
    res = client.get("/notes")
    assert res.status_code == 200
    assert res.json() == []


def test_list_notes_orders_newest_first(client):
    """[Read] 목록은 최신순(id 내림차순)."""
    client.post("/notes", json={"title": "첫번째"})
    client.post("/notes", json={"title": "두번째"})
    res = client.get("/notes")
    assert res.status_code == 200
    titles = [n["title"] for n in res.json()]
    assert titles == ["두번째", "첫번째"]


def test_get_note(client):
    """[Read] 단건 조회."""
    nid = client.post("/notes", json={"title": "단건"}).json()["id"]
    res = client.get(f"/notes/{nid}")
    assert res.status_code == 200
    assert res.json()["id"] == nid


def test_update_note(client):
    """[Update] 내용 수정 → updated_at 갱신, 전달 안 한 필드는 유지."""
    created = client.post("/notes", json={"title": "원본", "content": "old"}).json()
    nid = created["id"]
    res = client.put(f"/notes/{nid}", json={"content": "new"})
    assert res.status_code == 200
    body = res.json()
    assert body["content"] == "new"
    assert body["title"] == "원본"  # 제목은 유지
    assert body["updated_at"] >= created["updated_at"]


def test_delete_note(client):
    """[Delete] 삭제 → 이후 조회 시 404."""
    nid = client.post("/notes", json={"title": "삭제대상"}).json()["id"]
    res = client.delete(f"/notes/{nid}")
    assert res.status_code == 200
    assert res.json() == {"deleted": True, "note_id": nid}
    assert client.get(f"/notes/{nid}").status_code == 404


# ---- 에러/검증 케이스 ----

def test_get_not_found_returns_404(client):
    assert client.get("/notes/99999").status_code == 404


def test_update_not_found_returns_404(client):
    res = client.put("/notes/99999", json={"content": "x"})
    assert res.status_code == 404


def test_delete_not_found_returns_404(client):
    assert client.delete("/notes/99999").status_code == 404


def test_create_empty_title_returns_422(client):
    """빈 제목은 스키마 검증(min_length=1)에 걸려 422."""
    assert client.post("/notes", json={"title": ""}).status_code == 422


def test_create_missing_title_returns_422(client):
    assert client.post("/notes", json={"content": "본문만"}).status_code == 422


# ---- 전체 라이프사이클 ----

def test_full_crud_lifecycle(client):
    """Create → Read → Update → Delete 한 번에 흐름 검증."""
    # Create
    nid = client.post("/notes", json={"title": "라이프사이클", "content": "1"}).json()["id"]

    # Read (목록 + 단건)
    assert len(client.get("/notes").json()) == 1
    assert client.get(f"/notes/{nid}").json()["content"] == "1"

    # Update
    assert client.put(f"/notes/{nid}", json={"content": "2"}).json()["content"] == "2"

    # Delete
    assert client.delete(f"/notes/{nid}").status_code == 200
    assert client.get("/notes").json() == []
