def test_health_and_status(client):
    assert client.get("/api/health").json()["status"] == "ok"
    st = client.get("/api/system/status").json()
    assert any(p["name"] == "mock" and p["configured"] for p in st["llm_providers"])
    assert client.get("/metrics").status_code == 200


def test_auth_flow(client):
    r = client.post("/api/auth/register", json={"email": "a@b.com", "password": "secret123"})
    assert r.status_code == 201
    dup = client.post("/api/auth/register", json={"email": "a@b.com", "password": "secret123"})
    assert dup.status_code == 409
    bad = client.post("/api/auth/login", json={"email": "a@b.com", "password": "nope"})
    assert bad.status_code == 401
    tok = client.post("/api/auth/login", json={"email": "a@b.com", "password": "secret123"}).json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert me.json()["email"] == "a@b.com"
    assert client.get("/api/collections").status_code == 401


def test_single_video_pipeline(auth_client):
    c = auth_client
    r = c.post("/api/collections", json={"url": "https://youtu.be/ENvideo0001"})
    assert r.status_code == 201, r.text
    col = c.get(f"/api/collections/{r.json()['id']}").json()
    assert col["status"] == "completed", col
    v = col["videos"][0]
    assert v["status"] == "completed" and v["language"] == "en" and v["progress"] == 1.0
    formats = sorted(d["format"] for d in col["documents"])
    assert formats == ["md", "pdf"]

    detail = c.get(f"/api/videos/{v['id']}").json()
    assert detail["knowledge"]["concepts"]
    assert detail["quality"]["chunks"] >= 1
    tr = c.get(f"/api/videos/{v['id']}/transcript").json()
    assert tr["segments"] and tr["source"] == "captions"

    pdf_doc = next(d for d in col["documents"] if d["format"] == "pdf")
    dl = c.get(f"/api/documents/{pdf_doc['id']}/download")
    assert dl.status_code == 200 and dl.content.startswith(b"%PDF")

    logs = c.get(f"/api/collections/{col['id']}/logs").json()
    assert any("completed" in entry["message"] for entry in logs)


def test_playlist_pipeline_and_ask(auth_client):
    c = auth_client
    r = c.post("/api/collections", json={
        "url": "https://www.youtube.com/playlist?list=PLtest1234567890",
        "settings": {"output_language": "auto"},
    })
    assert r.status_code == 201, r.text
    col = c.get(f"/api/collections/{r.json()['id']}").json()
    assert col["kind"] == "playlist" and col["video_count"] == 3
    assert col["status"] == "completed", col
    assert col["videos"][2]["language"] == "mixed"
    kinds = {(d["kind"], d["format"]) for d in col["documents"]}
    assert ("collection", "pdf") in kinds and ("collection", "md") in kinds
    assert col["synthesis"]["concepts"]

    ans = c.post("/api/ask", json={"question": "What is supervised learning?", "collection_id": col["id"]})
    assert ans.status_code == 200, ans.text
    body = ans.json()
    assert body["sources"] and body["answer"]
    assert body["sources"][0]["url"].startswith("https://www.youtube.com/watch")

    hits = c.get("/api/search", params={"q": "gradient descent"}).json()
    assert hits and hits[0]["score"] > 0
    hits_ar = c.get("/api/search", params={"q": "التعلم الآلي"}).json()
    assert hits_ar


def test_failed_video_and_retry(auth_client, monkeypatch):
    c = auth_client
    r = c.post("/api/collections", json={"url": "https://youtu.be/XXvideo0001"})
    col = c.get(f"/api/collections/{r.json()['id']}").json()
    assert col["status"] == "failed"
    v = col["videos"][0]
    assert v["status"] == "failed" and "No transcript" in v["error"]
    assert v["attempts"] == 1  # non-retryable -> no automatic retries

    # Make the transcript available and retry only this video.
    from app.services import transcripts as tx
    from tests.conftest import fake_transcript

    monkeypatch.setattr(tx, "get_youtube_transcript", lambda vid: fake_transcript("EN" + vid[2:]))
    rr = c.post(f"/api/videos/{v['id']}/retry")
    assert rr.status_code == 200
    col = c.get(f"/api/collections/{col['id']}").json()
    assert col["status"] == "completed"


def test_ownership_is_enforced(auth_client, client):
    r = auth_client.post("/api/collections", json={"url": "https://youtu.be/ENvideo0001"})
    cid = r.json()["id"]
    other = client.post("/api/auth/register", json={"email": "other@x.com", "password": "secret123"}).json()
    h = {"Authorization": f"Bearer {other['access_token']}"}
    assert client.get(f"/api/collections/{cid}", headers=h).status_code == 404


def test_upload_requires_known_type(auth_client):
    r = auth_client.post("/api/collections/upload", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert r.status_code == 400


def test_invalid_url(auth_client):
    r = auth_client.post("/api/collections", json={"url": "https://vimeo.com/12345"})
    assert r.status_code == 400
