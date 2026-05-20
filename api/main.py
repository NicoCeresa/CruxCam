import os
import time
import uuid
import shutil
import tempfile
from pathlib import Path
from typing import Optional
import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from celery.result import AsyncResult
from .celery_app import celery_app
from .tasks import process_video_task

app = FastAPI(title="CruxCam API")

TMP      = Path(tempfile.gettempdir())
FILE_TTL = int(os.environ.get("CRUXCAM_FILE_TTL", 3600))

# In-memory map of preview_id → temp file path (only needed until processing starts)
_preview_paths: dict[str, Path] = {}


def _cleanup_old_files() -> None:
    """Delete CruxCam temp files older than FILE_TTL seconds."""
    cutoff = time.time() - FILE_TTL
    for pattern in ("cruxcam_upload_*", "cruxcam_output_*", "cruxcam_preview_*"):
        for path in TMP.glob(pattern):
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
    # Drop stale entries from the preview tracking dict
    for pid in [k for k, v in _preview_paths.items() if not v.exists()]:
        _preview_paths.pop(pid, None)


@app.post("/info")
async def video_info(video: UploadFile = File(...)):
    """Return metadata and save file for frame preview during trim selection."""
    suffix = Path(video.filename).suffix or ".mp4"
    preview_id = str(uuid.uuid4())
    fd, tmp = tempfile.mkstemp(suffix=suffix, prefix="cruxcam_preview_", dir=TMP)
    os.close(fd)
    preview_path = Path(tmp)
    _preview_paths[preview_id] = preview_path

    with open(preview_path, "wb") as f:
        shutil.copyfileobj(video.file, f)

    try:
        cap = cv2.VideoCapture(str(preview_path))
        if not cap.isOpened():
            preview_path.unlink(missing_ok=True)
            _preview_paths.pop(preview_id, None)
            raise HTTPException(status_code=400, detail="Could not read video file")
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
    except HTTPException:
        raise
    except Exception as exc:
        preview_path.unlink(missing_ok=True)
        _preview_paths.pop(preview_id, None)
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "fps": fps,
        "width": width,
        "height": height,
        "total_frames": total_frames,
        "duration": total_frames / max(fps, 1),
        "preview_id": preview_id,
    }


@app.get("/frame/{preview_id}")
def get_preview_frame(preview_id: str, n: int = Query(default=0, ge=0)):
    """Return a single frame from a preview file as JPEG."""
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
    video: UploadFile = File(...),
    angle_threshold: int = Query(default=90, ge=30, le=120),
    start_frame: int = Query(default=0, ge=0),
    end_frame: Optional[int] = Query(default=None, ge=1),
    preview_id: Optional[str] = Query(default=None),
):
    """Accept a video file, save it, and enqueue a processing job."""
    _cleanup_old_files()
    job_id = str(uuid.uuid4())
    suffix = Path(video.filename).suffix or ".mp4"

    fd, input_tmp = tempfile.mkstemp(suffix=suffix, prefix="cruxcam_upload_", dir=TMP)
    os.close(fd)
    input_path = Path(input_tmp)

    fd, output_tmp = tempfile.mkstemp(suffix=".mp4", prefix="cruxcam_output_", dir=TMP)
    os.close(fd)
    output_path = Path(output_tmp)

    with open(input_path, "wb") as f:
        shutil.copyfileobj(video.file, f)

    # Clean up preview now that processing is starting
    if preview_id:
        p = _preview_paths.pop(preview_id, None)
        if p:
            p.unlink(missing_ok=True)

    process_video_task.apply_async(
        args=[str(input_path), str(output_path), angle_threshold,
              start_frame, end_frame],
        task_id=job_id,
    )
    return {"job_id": job_id}


@app.get("/status/{job_id}")
def get_status(job_id: str):
    """Return the current state and progress (0–1) of a job."""
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
        return {"status": "failed", "error": str(task.info), "progress": 0.0}
    return {"status": task.state.lower(), "progress": 0.0}


@app.get("/result/{job_id}")
def get_result(job_id: str):
    """Return the serialized AnalysisResult for a completed job."""
    task = AsyncResult(job_id, app=celery_app)
    if task.state != "SUCCESS":
        raise HTTPException(
            status_code=404,
            detail=f"Job not complete (state: {task.state})",
        )
    return task.result


@app.get("/video/{job_id}")
def get_video(job_id: str):
    """Stream the processed video file for a completed job."""
    task = AsyncResult(job_id, app=celery_app)
    if task.state != "SUCCESS":
        raise HTTPException(status_code=404, detail="Job not complete")

    video_path = task.result.get("processed_video_path")
    if not video_path or not Path(video_path).exists():
        raise HTTPException(status_code=404, detail="Video file not found")

    return FileResponse(video_path, media_type="video/mp4")
