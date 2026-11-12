import asyncio
import json
import logging
import shutil
import time
import uuid
from concurrent.futures import Executor
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse

from .config import Settings
from .deps import RateLimiter, get_executor, get_job_store, get_preview_store, get_rate_limiter, get_settings
from .jobs import JobStore, progress_payload, submit_job
from .previews import PreviewStore, VideoReadError, read_video_info

log = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
# Jobs are stored as "pending" before /submit returns, so a job still unknown after this
# long doesn't exist (wrong id, expired, or lost in a restart) and the stream ends.
UNKNOWN_JOB_GRACE_S = 10.0


# ── Request helpers ────────────────────────────────────────────────────────────

def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _validate_video(filename: str, content_type: Optional[str]) -> None:
    ext = Path(filename).suffix.lower() if filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")
    if content_type and not content_type.startswith("video/"):
        raise HTTPException(status_code=415, detail=f"Expected a video file, got '{content_type}'")


def _create_preview(previews: PreviewStore, suffix: str, write) -> dict:
    try:
        return previews.create(suffix, write)
    except VideoReadError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        # Details (paths, ffmpeg output) go to the log, not to the client.
        log.exception("preview creation failed")
        raise HTTPException(status_code=500, detail="Could not process the video")


def _validate_trim(video: Path, start_frame: int, end_frame: Optional[int]) -> None:
    """Reject trim ranges that select no frames, before a job is queued."""
    if end_frame is not None and end_frame <= start_frame:
        raise HTTPException(status_code=400, detail="end_frame must be greater than start_frame")
    try:
        total = read_video_info(video)["total_frames"]
    except VideoReadError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if start_frame >= total:
        raise HTTPException(status_code=400, detail=f"start_frame is past the end of the video ({total} frames)")


def _start_job(
    store: JobStore, executor: Executor, previews: PreviewStore,
    job_id: str, input_path: Path, scaled_path: Optional[Path],
    angle_threshold: int, start_frame: int, end_frame: Optional[int], frame_skip: int,
) -> dict:
    output_path = previews.new_temp("cruxcam_output_", ".mp4")
    submit_job(
        store, executor, job_id, str(input_path), str(output_path),
        angle_threshold, start_frame, end_frame, frame_skip,
        inference_path=str(scaled_path) if scaled_path else None,
    )
    return {"job_id": job_id}


# ── Sample endpoints ───────────────────────────────────────────────────────────

@router.get("/sample/info")
def sample_info(
    settings: Settings = Depends(get_settings),
    previews: PreviewStore = Depends(get_preview_store),
):
    if not settings.sample_path.exists():
        raise HTTPException(status_code=404, detail="Sample video not found")
    return _create_preview(previews, settings.sample_path.suffix,
                           lambda p: shutil.copy2(settings.sample_path, p))


@router.post("/sample/upload", status_code=202)
def sample_upload(
    request: Request,
    angle_threshold: int = Query(default=90, ge=30, le=120),
    start_frame: int = Query(default=0, ge=0),
    end_frame: Optional[int] = Query(default=None, ge=1),
    preview_id: Optional[str] = Query(default=None),
    frame_skip: int = Query(default=2, ge=1, le=10),
    settings: Settings = Depends(get_settings),
    store: JobStore = Depends(get_job_store),
    executor: Executor = Depends(get_executor),
    previews: PreviewStore = Depends(get_preview_store),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    if not settings.sample_path.exists():
        raise HTTPException(status_code=404, detail="Sample video not found")

    limiter.check(_client_ip(request))
    _validate_trim(settings.sample_path, start_frame, end_frame)
    previews.cleanup()
    limiter.prune()
    job_id = str(uuid.uuid4())

    input_path = previews.new_temp("cruxcam_upload_", settings.sample_path.suffix)
    shutil.copy2(settings.sample_path, input_path)

    preview_path, scaled_path = previews.take(preview_id) if preview_id else (None, None)
    if preview_path:
        preview_path.unlink(missing_ok=True)

    return _start_job(store, executor, previews, job_id, input_path, scaled_path,
                      angle_threshold, start_frame, end_frame, frame_skip)


# ── Upload endpoints ───────────────────────────────────────────────────────────

# Plain `def` (not async): the upload copy and ffmpeg rescale block, so FastAPI must run
# this in its threadpool to keep /stream and other requests responsive meanwhile.
# Upload size is enforced by BodySizeLimit middleware before the body is stored.
@router.post("/info")
def video_info(
    video: UploadFile = File(...),
    previews: PreviewStore = Depends(get_preview_store),
):
    _validate_video(video.filename or "", video.content_type)

    suffix = Path(video.filename).suffix.lower() if video.filename else ".mp4"

    def _write(path: Path) -> None:
        with open(path, "wb") as f:
            shutil.copyfileobj(video.file, f)

    return _create_preview(previews, suffix, _write)


@router.get("/frame/{preview_id}")
def get_preview_frame(
    preview_id: str,
    n: int = Query(default=0, ge=0),
    previews: PreviewStore = Depends(get_preview_store),
):
    try:
        jpeg = previews.frame_jpeg(preview_id, n)
    except VideoReadError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    if jpeg is None:
        raise HTTPException(status_code=404, detail="Preview not found")
    return Response(content=jpeg, media_type="image/jpeg")


@router.post("/submit", status_code=202)
def submit_preview(
    request: Request,
    preview_id: str = Query(...),
    angle_threshold: int = Query(default=90, ge=30, le=120),
    start_frame: int = Query(default=0, ge=0),
    end_frame: Optional[int] = Query(default=None, ge=1),
    frame_skip: int = Query(default=2, ge=1, le=10),
    settings: Settings = Depends(get_settings),
    store: JobStore = Depends(get_job_store),
    executor: Executor = Depends(get_executor),
    previews: PreviewStore = Depends(get_preview_store),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    limiter.check(_client_ip(request))
    previews.cleanup()
    limiter.prune()

    preview = previews.get(preview_id)
    if preview is None:
        _, scaled_path = previews.take(preview_id)   # drop any orphaned scaled copy
        if scaled_path:
            scaled_path.unlink(missing_ok=True)
        raise HTTPException(status_code=404, detail="Preview not found — please re-upload the file")
    # Validate before take(), so a bad trim doesn't force a re-upload.
    _validate_trim(preview, start_frame, end_frame)
    preview_path, scaled_path = previews.take(preview_id)

    job_id = str(uuid.uuid4())
    input_path = settings.tmp / f"cruxcam_upload_{job_id}{preview_path.suffix or '.mp4'}"
    preview_path.rename(input_path)

    return _start_job(store, executor, previews, job_id, input_path, scaled_path,
                      angle_threshold, start_frame, end_frame, frame_skip)


# ── Result endpoints ───────────────────────────────────────────────────────────

@router.get("/status/{job_id}")
def get_status(job_id: str, store: JobStore = Depends(get_job_store)):
    return progress_payload(store.get(job_id))


@router.get("/stream/{job_id}")
async def stream_job(job_id: str, store: JobStore = Depends(get_job_store)):
    async def _gen():
        started = time.monotonic()
        while True:
            data = await asyncio.to_thread(store.get, job_id)
            if data is None and time.monotonic() - started > UNKNOWN_JOB_GRACE_S:
                data = {"status": "failed", "error": "Job not found — it may have expired. Please try again."}
            payload = progress_payload(data)
            yield f"data: {json.dumps(payload)}\n\n"
            if payload["status"] in ("complete", "failed"):
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/result/{job_id}")
def get_result(job_id: str, store: JobStore = Depends(get_job_store)):
    data = store.get(job_id)
    if not data or data["status"] != "complete":
        state = data["status"] if data else "unknown"
        raise HTTPException(status_code=404, detail=f"Job not complete (state: {state})")
    return data["result"]


@router.get("/video/{job_id}")
def get_video(job_id: str, store: JobStore = Depends(get_job_store)):
    data = store.get(job_id)
    if not data or data["status"] != "complete":
        raise HTTPException(status_code=404, detail="Job not complete")
    video_path = data.get("video_path")
    if not video_path or not Path(video_path).exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    return FileResponse(video_path, media_type="video/mp4")
