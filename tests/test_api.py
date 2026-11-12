"""API behaviour with Redis replaced by an in-memory fake, via dependency overrides."""
import json
import shutil

import pytest
from fastapi.testclient import TestClient

import api.routes as routes
from api.deps import RateLimiter, get_executor, get_job_store, get_preview_store, get_rate_limiter, get_settings
from api.jobs import JobStore
from api.main import app
from api.previews import PreviewStore
from tests import synthetic as syn


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


class FakeExecutor:
    """Records submitted jobs instead of running them."""

    def __init__(self):
        self.submitted = []

    def submit(self, fn, *args):
        self.submitted.append(args)


@pytest.fixture
def previews(tmp_path):
    return PreviewStore(tmp_path, ttl=3600)


@pytest.fixture
def executor():
    return FakeExecutor()


@pytest.fixture
def client(store, previews, executor):
    limiter = RateLimiter(limit=1000)
    app.dependency_overrides[get_job_store] = lambda: store
    app.dependency_overrides[get_preview_store] = lambda: previews
    app.dependency_overrides[get_executor] = lambda: executor
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
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


# ── Correctness / hardening ───────────────────────────────────────────────────

def test_result_hides_server_path_but_video_is_served(client, store, tmp_path):
    video = tmp_path / "result.mp4"
    video.write_bytes(b"fake mp4")
    store.set("j5", {"status": "complete", "result": {"efficiency": 1.0}, "video_path": str(video)})
    assert client.get("/result/j5").json() == {"efficiency": 1.0}
    assert client.get("/video/j5").content == b"fake mp4"


def test_stream_ends_for_unknown_job(client, monkeypatch):
    monkeypatch.setattr(routes, "UNKNOWN_JOB_GRACE_S", 0.0)
    lines = [l for l in client.get("/stream/never-existed").text.splitlines() if l.startswith("data:")]
    assert json.loads(lines[-1][5:])["status"] == "failed"


def test_unexpected_preview_error_is_generic(client, previews, monkeypatch):
    def boom(suffix, write):
        raise RuntimeError("ffmpeg failed: /tmp/cruxcam_preview_secret.mp4")
    monkeypatch.setattr(previews, "create", boom)
    res = client.post("/info", files={"video": ("clip.mp4", b"x", "video/mp4")})
    assert res.status_code == 500
    assert "/tmp" not in res.text and res.json()["detail"] == "Could not process the video"


@pytest.fixture
def preview_id(previews, tmp_path):
    clip = syn.make_clip(tmp_path / "clip.mp4", syn.static(30))
    return previews.create(".mp4", lambda p: shutil.copy(clip.path, p))["preview_id"]


@pytest.mark.parametrize("start, end", [(20, 20), (20, 5), (30, None), (500, 600)])
def test_submit_rejects_empty_trim_without_losing_preview(client, previews, executor, preview_id, start, end):
    params = {"preview_id": preview_id, "start_frame": start}
    if end is not None:
        params["end_frame"] = end
    assert client.post("/submit", params=params).status_code == 400
    assert previews.get(preview_id) is not None   # user can fix the trim and resubmit
    assert executor.submitted == []


def test_submit_valid_trim_queues_job(client, executor, preview_id):
    res = client.post("/submit", params={"preview_id": preview_id, "start_frame": 5, "end_frame": 25})
    assert res.status_code == 202 and len(executor.submitted) == 1


def test_sample_upload_rejects_start_past_end(client, executor):
    if not get_settings().sample_path.exists():
        pytest.skip("sample clip not available")
    assert client.post("/sample/upload", params={"start_frame": 10**6}).status_code == 400
    assert executor.submitted == []


def test_info_and_sample_info_are_rate_limited(store, previews):
    limiter = RateLimiter(limit=2)
    app.dependency_overrides[get_job_store] = lambda: store
    app.dependency_overrides[get_preview_store] = lambda: previews
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    try:
        client = TestClient(app)
        upload = {"video": ("notes.txt", b"hello", "text/plain")}
        assert client.post("/info", files=upload).status_code == 415   # counted, then rejected
        assert client.post("/info", files=upload).status_code == 415
        assert client.post("/info", files=upload).status_code == 429
        assert client.get("/sample/info").status_code == 429           # same per-IP budget
    finally:
        app.dependency_overrides.clear()
