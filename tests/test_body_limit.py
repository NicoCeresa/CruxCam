"""Upload size limit is enforced before the body is stored."""
from fastapi import FastAPI, File, UploadFile
from fastapi.testclient import TestClient

from api.body_limit import BodySizeLimit
from api.main import app as main_app

LIMIT = 1024 * 1024   # 1 MB


def _client():
    app = FastAPI()
    app.add_middleware(BodySizeLimit, max_bytes=LIMIT)
    stored = []

    @app.post("/upload")
    def upload(video: UploadFile = File(...)):
        stored.append(len(video.file.read()))
        return {"bytes": stored[-1]}

    return TestClient(app), stored


def _chunks(total, size=64 * 1024):
    """Multipart body as a generator → sent chunked, with no Content-Length."""
    boundary = b"b0undary"
    yield b"--" + boundary + b'\r\nContent-Disposition: form-data; name="video"; filename="v.mp4"\r\n'
    yield b"Content-Type: video/mp4\r\n\r\n"
    for i in range(0, total, size):
        yield b"x" * min(size, total - i)
    yield b"\r\n--" + boundary + b"--\r\n"


def _chunked_headers():
    return {"content-type": "multipart/form-data; boundary=b0undary"}


def test_small_upload_passes():
    client, stored = _client()
    res = client.post("/upload", files={"video": ("v.mp4", b"x" * 1000, "video/mp4")})
    assert res.status_code == 200 and stored == [1000]


def test_declared_oversize_rejected_without_reaching_endpoint():
    client, stored = _client()
    res = client.post("/upload", files={"video": ("v.mp4", b"x" * (2 * LIMIT), "video/mp4")})
    assert res.status_code == 413 and "too large" in res.json()["detail"]
    assert stored == []


def test_undeclared_oversize_rejected_while_streaming():
    client, stored = _client()
    res = client.post("/upload", content=_chunks(2 * LIMIT), headers=_chunked_headers())
    assert res.status_code == 413
    assert stored == []


def test_undeclared_small_upload_passes():
    client, stored = _client()
    res = client.post("/upload", content=_chunks(10_000), headers=_chunked_headers())
    assert res.status_code == 200 and stored == [10_000]


def test_main_app_installs_limit_inside_cors():
    # Last-added middleware is outermost; CORS must wrap the limit so 413s carry CORS headers.
    names = [m.cls.__name__ for m in main_app.user_middleware]
    assert names.index("CORSMiddleware") < names.index("BodySizeLimit")
