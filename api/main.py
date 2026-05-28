import asyncio
import json
import os
import subprocess
import time
import uuid
import shutil
import tempfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import cv2
import redis as redis_lib
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse

from .tasks import process_video

app = FastAPI(title="CruxCam API")

_ALLOWED_ORIGINS = os.environ.get("CRUXCAM_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── Config ─────────────────────────────────────────────────────────────────────
_PROJECT_ROOT    = Path(__file__).parent.parent
TMP              = Path(tempfile.gettempdir())
FILE_TTL         = int(os.environ.get("CRUXCAM_FILE_TTL", 3600))
MAX_UPLOAD_MB    = int(os.environ.get("CRUXCAM_MAX_UPLOAD_MB", 500))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
RATE_LIMIT       = int(os.environ.get("CRUXCAM_RATE_LIMIT", 10))
SAMPLE_PATH      = _PROJECT_ROOT / os.environ.get("CRUXCAM_SAMPLE_PATH", "inputs/tomoa_outside.mp4")
REDIS_URL        = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}

# ── Services ───────────────────────────────────────────────────────────────────
_redis    = redis_lib.Redis.from_url(REDIS_URL, decode_responses=True)
_executor = ThreadPoolExecutor(max_workers=2)

# ── State ──────────────────────────────────────────────────────────────────────
_preview_paths: dict[str, Path] = {}
_scaled_paths:  dict[str, Path] = {}   # preview_id -> 1080p-scaled copy for inference
_upload_times:  dict[str, list[float]] = defaultdict(list)


# ── Job helpers ────────────────────────────────────────────────────────────────

def _set_job(job_id: str, state: dict) -> None:
    _redis.setex(f"cruxcam:job:{job_id}", FILE_TTL, json.dumps(state))


def _get_job(job_id: str) -> Optional[dict]:
    raw = _redis.get(f"cruxcam:job:{job_id}")
    return json.loads(raw) if raw else None


def _submit_job(job_id: str, input_path: str, output_path: str,
                angle_threshold: int, start_frame: int,
                end_frame: Optional[int], frame_skip: int,
                inference_path: Optional[str] = None) -> None:
    _set_job(job_id, {"status": "pending"})
    _executor.submit(
        process_video,
        job_id, input_path, output_path,
        angle_threshold, start_frame, end_frame, frame_skip,
        _set_job, inference_path,
    )


def _scale_for_inference(path: Path, preview_id: str) -> None:
    """If path is taller than 1080p, create a scaled copy and register it under preview_id."""
    cap = cv2.VideoCapture(str(path))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    if height <= 1080:
        return
    ffmpeg_bin = shutil.which('ffmpeg') or 'ffmpeg'
    fd, tmp = tempfile.mkstemp(suffix='.mp4', prefix='cruxcam_scaled_', dir=TMP)
    os.close(fd)
    tmp_path = Path(tmp)
    try:
        subprocess.run(
            [ffmpeg_bin, '-y', '-i', str(path), '-vf', 'scale=-2:1080',
             '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '18', str(tmp_path)],
            check=True, capture_output=True,
        )
        _scaled_paths[preview_id] = tmp_path
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


# ── File helpers ───────────────────────────────────────────────────────────────

def _cleanup_old_files() -> None:
    cutoff = time.time() - FILE_TTL
    for pattern in ("cruxcam_upload_*", "cruxcam_output_*", "cruxcam_preview_*", "cruxcam_scaled_*"):
        for path in TMP.glob(pattern):
            try:
                if path.is_file() and path.stat().st_mtime < cutoff:
                    path.unlink(missing_ok=True)
            except OSError:
                pass
    for pid in [k for k, v in _preview_paths.items() if not v.exists()]:
        _preview_paths.pop(pid, None)
    for pid in [k for k, v in _scaled_paths.items() if not v.exists()]:
        _scaled_paths.pop(pid, None)
    now = time.time()
    for ip in list(_upload_times):
        _upload_times[ip] = [t for t in _upload_times[ip] if now - t < 60]
        if not _upload_times[ip]:
            del _upload_times[ip]


def _check_rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    _upload_times[ip] = [t for t in _upload_times[ip] if now - t < 60]
    if len(_upload_times[ip]) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Too many requests — try again in a minute")
    _upload_times[ip].append(now)


def _check_upload_size(request: Request) -> None:
    cl = request.headers.get("content-length")
    if cl and int(cl) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File too large (max {MAX_UPLOAD_MB} MB)")


def _validate_video(filename: str, content_type: Optional[str]) -> None:
    ext = Path(filename).suffix.lower() if filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")
    if content_type and not content_type.startswith("video/"):
        raise HTTPException(status_code=415, detail=f"Expected a video file, got '{content_type}'")


def _read_video_info(path: Path) -> dict:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise HTTPException(status_code=400, detail="Could not read video file")
    fps          = int(cap.get(cv2.CAP_PROP_FPS))
    width        = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height       = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return {
        "fps": fps,
        "width": width,
        "height": height,
        "total_frames": total_frames,
        "duration": total_frames / max(fps, 1),
    }


# ── Sample endpoints ───────────────────────────────────────────────────────────

@app.get("/sample/info")
def sample_info():
    if not SAMPLE_PATH.exists():
        raise HTTPException(status_code=404, detail="Sample video not found")

    preview_id = str(uuid.uuid4())
    fd, tmp = tempfile.mkstemp(suffix=SAMPLE_PATH.suffix, prefix="cruxcam_preview_", dir=TMP)
    os.close(fd)
    preview_path = Path(tmp)
    shutil.copy2(SAMPLE_PATH, preview_path)
    _preview_paths[preview_id] = preview_path

    try:
        info = _read_video_info(preview_path)
        _scale_for_inference(preview_path, preview_id)
    except HTTPException:
        preview_path.unlink(missing_ok=True)
        _preview_paths.pop(preview_id, None)
        raise

    return {**info, "preview_id": preview_id}


@app.post("/sample/upload", status_code=202)
def sample_upload(
    request: Request,
    angle_threshold: int = Query(default=90, ge=30, le=120),
    start_frame: int = Query(default=0, ge=0),
    end_frame: Optional[int] = Query(default=None, ge=1),
    preview_id: Optional[str] = Query(default=None),
    frame_skip: int = Query(default=2, ge=1, le=10),
):
    if not SAMPLE_PATH.exists():
        raise HTTPException(status_code=404, detail="Sample video not found")

    _check_rate_limit(request)
    _cleanup_old_files()
    job_id = str(uuid.uuid4())

    fd, input_tmp = tempfile.mkstemp(suffix=SAMPLE_PATH.suffix, prefix="cruxcam_upload_", dir=TMP)
    os.close(fd)
    input_path = Path(input_tmp)
    shutil.copy2(SAMPLE_PATH, input_path)

    fd, output_tmp = tempfile.mkstemp(suffix=".mp4", prefix="cruxcam_output_", dir=TMP)
    os.close(fd)

    scaled_path = _scaled_paths.pop(preview_id, None) if preview_id else None
    if preview_id:
        p = _preview_paths.pop(preview_id, None)
        if p:
            p.unlink(missing_ok=True)

    _submit_job(job_id, str(input_path), output_tmp, angle_threshold, start_frame, end_frame, frame_skip,
                inference_path=str(scaled_path) if scaled_path else None)
    return {"job_id": job_id}


# ── Upload endpoints ───────────────────────────────────────────────────────────

@app.post("/info")
async def video_info(request: Request, video: UploadFile = File(...)):
    _check_upload_size(request)
    _validate_video(video.filename or "", video.content_type)

    suffix = Path(video.filename).suffix.lower() if video.filename else ".mp4"
    preview_id = str(uuid.uuid4())
    fd, tmp = tempfile.mkstemp(suffix=suffix, prefix="cruxcam_preview_", dir=TMP)
    os.close(fd)
    preview_path = Path(tmp)
    _preview_paths[preview_id] = preview_path

    with open(preview_path, "wb") as f:
        shutil.copyfileobj(video.file, f)

    try:
        info = _read_video_info(preview_path)
        _scale_for_inference(preview_path, preview_id)
    except HTTPException:
        preview_path.unlink(missing_ok=True)
        _preview_paths.pop(preview_id, None)
        raise
    except Exception as exc:
        preview_path.unlink(missing_ok=True)
        _preview_paths.pop(preview_id, None)
        raise HTTPException(status_code=500, detail=str(exc))

    return {**info, "preview_id": preview_id}


@app.get("/frame/{preview_id}")
def get_preview_frame(preview_id: str, n: int = Query(default=0, ge=0)):
    preview_path = _preview_paths.get(preview_id)
    if not preview_path or not preview_path.exists():
        raise HTTPException(status_code=404, detail="Preview not found")

    cap = cv2.VideoCapture(str(preview_path))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.set(cv2.CAP_PROP_POS_FRAMES, min(n, total - 1))
    ok, frame = cap.read()
    cap.release()

    if not ok:
        raise HTTPException(status_code=500, detail="Could not read frame")

    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
    return Response(content=buf.tobytes(), media_type="image/jpeg")


@app.post("/submit", status_code=202)
def submit_preview(
    request: Request,
    preview_id: str = Query(...),
    angle_threshold: int = Query(default=90, ge=30, le=120),
    start_frame: int = Query(default=0, ge=0),
    end_frame: Optional[int] = Query(default=None, ge=1),
    frame_skip: int = Query(default=2, ge=1, le=10),
):
    _check_rate_limit(request)
    _cleanup_old_files()

    preview_path = _preview_paths.pop(preview_id, None)
    if not preview_path or not preview_path.exists():
        raise HTTPException(status_code=404, detail="Preview not found — please re-upload the file")

    job_id = str(uuid.uuid4())
    suffix = preview_path.suffix or ".mp4"
    input_path = TMP / f"cruxcam_upload_{job_id}{suffix}"
    preview_path.rename(input_path)

    fd, output_tmp = tempfile.mkstemp(suffix=".mp4", prefix="cruxcam_output_", dir=TMP)
    os.close(fd)

    scaled_path = _scaled_paths.pop(preview_id, None)
    _submit_job(job_id, str(input_path), output_tmp, angle_threshold, start_frame, end_frame, frame_skip,
                inference_path=str(scaled_path) if scaled_path else None)
    return {"job_id": job_id}


# ── Result endpoints ───────────────────────────────────────────────────────────

@app.get("/status/{job_id}")
def get_status(job_id: str):
    data = _get_job(job_id)
    if data is None:
        return {"status": "pending", "progress": 0.0}
    status = data["status"]
    if status == "processing":
        total = max(data.get("total", 1), 1)
        return {"status": "processing", "progress": data.get("current", 0) / total}
    if status == "complete":
        return {"status": "complete", "progress": 1.0}
    if status == "failed":
        return {"status": "failed", "error": data.get("error", "Processing failed"), "progress": 0.0}
    return {"status": status, "progress": 0.0}


@app.get("/stream/{job_id}")
async def stream_job(job_id: str):
    async def _gen():
        while True:
            data = await asyncio.to_thread(_get_job, job_id)
            if data is None:
                payload = {"status": "pending", "progress": 0.0}
            elif data["status"] == "processing":
                total = max(data.get("total", 1), 1)
                payload = {"status": "processing", "progress": data.get("current", 0) / total}
            elif data["status"] == "complete":
                yield f"data: {json.dumps({'status': 'complete', 'progress': 1.0})}\n\n"
                return
            elif data["status"] == "failed":
                yield f"data: {json.dumps({'status': 'failed', 'error': data.get('error', ''), 'progress': 0.0})}\n\n"
                return
            else:
                payload = {"status": data["status"], "progress": 0.0}
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/result/{job_id}")
def get_result(job_id: str):
    data = _get_job(job_id)
    if not data or data["status"] != "complete":
        state = data["status"] if data else "unknown"
        raise HTTPException(status_code=404, detail=f"Job not complete (state: {state})")
    return data["result"]


@app.get("/video/{job_id}")
def get_video(job_id: str):
    data = _get_job(job_id)
    if not data or data["status"] != "complete":
        raise HTTPException(status_code=404, detail="Job not complete")
    video_path = data["result"].get("processed_video_path")
    if not video_path or not Path(video_path).exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    return FileResponse(video_path, media_type="video/mp4")
