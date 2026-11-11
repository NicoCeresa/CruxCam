"""API behaviour with Redis replaced by an in-memory fake, via dependency overrides."""
import json

import pytest
from fastapi.testclient import TestClient

from api.deps import get_job_store, get_preview_store, get_settings
from api.jobs import JobStore
from api.main import app
from api.previews import PreviewStore


class FakeRedis:
    def __init__(self):
        self.store = {}

    def setex(self, key, ttl, value):
        self.store[key] = value

    def get(self, key):
        return self.store.get(key)


@pytest.fixture
def store():
    return JobStore(FakeRedis(), ttl=3600)


@pytest.fixture
def client(store, tmp_path):
    previews = PreviewStore(tmp_path, ttl=3600)
    app.dependency_overrides[get_job_store] = lambda: store
    app.dependency_overrides[get_preview_store] = lambda: previews
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_unknown_job_is_pending(client):
    assert client.get("/status/nope").json() == {"status": "pending", "progress": 0.0}


def test_result_404_until_complete(client, store):
    assert client.get("/result/nope").status_code == 404
    store.set("j1", {"status": "processing", "current": 5, "total": 10})
    assert client.get("/status/j1").json() == {"status": "processing", "progress": 0.5}
    assert client.get("/result/j1").status_code == 404


def test_complete_job_returns_result(client, store):
    store.set("j2", {"status": "complete", "result": {"efficiency": 50.0}})
    assert client.get("/status/j2").json()["status"] == "complete"
    assert client.get("/result/j2").json() == {"efficiency": 50.0}


def test_failed_job_reports_error(client, store):
    store.set("j3", {"status": "failed", "error": "boom"})
    body = client.get("/status/j3").json()
    assert body["status"] == "failed" and body["error"] == "boom"


def test_stream_ends_on_complete(client, store):
    store.set("j4", {"status": "complete", "result": {}})
    lines = [l for l in client.get("/stream/j4").text.splitlines() if l.startswith("data:")]
    assert json.loads(lines[-1][5:]) == {"status": "complete", "progress": 1.0}


def test_submit_unknown_preview_is_404(client):
    assert client.post("/submit", params={"preview_id": "missing"}).status_code == 404


def test_info_rejects_non_video(client):
    res = client.post("/info", files={"video": ("notes.txt", b"hello", "text/plain")})
    assert res.status_code == 415


def test_sample_info_then_frame(client):
    if not get_settings().sample_path.exists():
        pytest.skip("sample clip not available")
    info = client.get("/sample/info").json()
    assert info["total_frames"] > 0 and "preview_id" in info
    res = client.get(f"/frame/{info['preview_id']}", params={"n": 0})
    assert res.status_code == 200 and res.headers["content-type"] == "image/jpeg"
