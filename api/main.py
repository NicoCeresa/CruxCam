import os
import time
import uuid
import shutil
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Optional
import cv2
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from celery.result import AsyncResult
from .celery_app import celery_app
from .tasks import process_video_task

app = FastAPI(title="CruxCam API")

_ALLOWED_ORIGINS = os.environ.get("CRUXCAM_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── Config ─────────────────────────────────────────────────────────────────────
_PROJECT_ROOT   = Path(__file__).parent.parent
TMP             = Path(tempfile.gettempdir())
FILE_TTL        = int(os.environ.get("CRUXCAM_FILE_TTL", 3600))
MAX_UPLOAD_MB   = int(os.environ.get("CRUXCAM_MAX_UPLOAD_MB", 500))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
RATE_LIMIT      = int(os.environ.get("CRUXCAM_RATE_LIMIT", 10))  # uploads per IP per minute
SAMPLE_PATH     = _PROJECT_ROOT / os.environ.get("CRUXCAM_SAMPLE_PATH", "inputs/tomoa_outside.mp4")

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}

# ── State ──────────────────────────────────────────────────────────────────────
# preview_id → temp file path (only needed until processing starts)
_preview_paths: dict[str, Path] = {}
# ip → list of upload timestamps for sliding-window rate limiting
_upload_times: dict[str, list[float]] = defaultdict(list)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _cleanup_old_files() -> None:
    cutoff = time.time() - FILE_TTL
    for pattern in ("cruxcam_upload_*", "cruxcam_output_*", "cruxcam_preview_*", "cruxcam_skeleton_*"):
        for path in TMP.glob(pattern):
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
    for pid in [k for k, v in _preview_paths.items() if not v.exists()]:
        _preview_paths.pop(pid, None)
    # Purge stale rate-limit windows to keep the dict from growing unboundedly
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
    output_path = Path(output_tmp)

    if preview_id:
        p = _preview_paths.pop(preview_id, None)
        if p:
            p.unlink(missing_ok=True)

    process_video_task.apply_async(
        args=[str(input_path), str(output_path), angle_threshold, start_frame, end_frame, frame_skip],
        task_id=job_id,
    )
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


@app.post("/upload", status_code=202)
async def upload_video(
    request: Request,
    video: UploadFile = File(...),
    angle_threshold: int = Query(default=90, ge=30, le=120),
    start_frame: int = Query(default=0, ge=0),
    end_frame: Optional[int] = Query(default=None, ge=1),
    preview_id: Optional[str] = Query(default=None),
    frame_skip: int = Query(default=2, ge=1, le=10),
):
    _check_upload_size(request)
    _check_rate_limit(request)
    _validate_video(video.filename or "", video.content_type)
    _cleanup_old_files()

    job_id = str(uuid.uuid4())
    suffix = Path(video.filename).suffix.lower() if video.filename else ".mp4"

    fd, input_tmp = tempfile.mkstemp(suffix=suffix, prefix="cruxcam_upload_", dir=TMP)
    os.close(fd)
    input_path = Path(input_tmp)

    fd, output_tmp = tempfile.mkstemp(suffix=".mp4", prefix="cruxcam_output_", dir=TMP)
    os.close(fd)
    output_path = Path(output_tmp)

    with open(input_path, "wb") as f:
        shutil.copyfileobj(video.file, f)

    if input_path.stat().st_size == 0:
        input_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    if preview_id:
        p = _preview_paths.pop(preview_id, None)
        if p:
            p.unlink(missing_ok=True)

    process_video_task.apply_async(
        args=[str(input_path), str(output_path), angle_threshold, start_frame, end_frame, frame_skip],
        task_id=job_id,
    )
    return {"job_id": job_id}


# ── Result endpoints ───────────────────────────────────────────────────────────

@app.get("/status/{job_id}")
def get_status(job_id: str):
    task = AsyncResult(job_id, app=celery_app)
    if task.state == "PENDING":
        return {"status": "pending", "progress": 0.0}
    if task.state == "PROGRESS":
        meta = task.info or {}
        total = max(meta.get("total", 1), 1)
        return {"status": "processing", "progress": meta.get("current", 0) / total}
    if task.state == "SUCCESS":
        return {"status": "complete", "progress": 1.0}
    if task.state == "FAILURE":
        err = task.info
        msg = str(err).splitlines()[0] if err else "Processing failed"
        return {"status": "failed", "error": msg, "progress": 0.0}
    return {"status": task.state.lower(), "progress": 0.0}


@app.get("/result/{job_id}")
def get_result(job_id: str):
    task = AsyncResult(job_id, app=celery_app)
    if task.state != "SUCCESS":
        raise HTTPException(status_code=404, detail=f"Job not complete (state: {task.state})")
    return task.result


@app.get("/skeleton_video/{job_id}")
def get_skeleton_video(job_id: str):
    task = AsyncResult(job_id, app=celery_app)
    if task.state != "SUCCESS":
        raise HTTPException(status_code=404, detail="Job not complete")

    result_data = task.result
    if not result_data.get("pose_data_3d"):
        raise HTTPException(status_code=404, detail="No pose data available")

    cache_path = TMP / f"cruxcam_skeleton_{job_id}.mp4"
    if not cache_path.exists():
        from .tasks import deserialize_result
        from core.skeleton_renderer import render_skeleton_video
        result = deserialize_result(result_data)
        render_skeleton_video(result.pose_data_3d, result.fps, str(cache_path))

    return FileResponse(str(cache_path), media_type="video/mp4",
                        filename=f"cruxcam_3d_{job_id}.mp4")


@app.get("/video/{job_id}")
def get_video(job_id: str):
    task = AsyncResult(job_id, app=celery_app)
    if task.state != "SUCCESS":
        raise HTTPException(status_code=404, detail="Job not complete")
    video_path = task.result.get("processed_video_path")
    if not video_path or not Path(video_path).exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    return FileResponse(video_path, media_type="video/mp4")
