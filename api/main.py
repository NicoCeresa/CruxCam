import os
import uuid
import shutil
import tempfile
from pathlib import Path
import cv2
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from celery.result import AsyncResult
from .celery_app import celery_app
from .tasks import process_video_task

app = FastAPI(title="CruxCam API")

UPLOAD_DIR = Path(os.environ.get("CRUXCAM_UPLOAD_DIR", "uploads"))
OUTPUT_DIR = Path(os.environ.get("CRUXCAM_OUTPUT_DIR", "outputs"))
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


@app.post("/info")
async def video_info(video: UploadFile = File(...)):
    """Return metadata (fps, resolution, duration) for an uploaded video."""
    suffix = Path(video.filename).suffix or ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(video.file, tmp)
        tmp_path = tmp.name

    try:
        cap = cv2.VideoCapture(tmp_path)
        if not cap.isOpened():
            raise HTTPException(status_code=400, detail="Could not read video file")
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return {
        "fps": fps,
        "width": width,
        "height": height,
        "total_frames": total_frames,
        "duration": total_frames / max(fps, 1),
    }


@app.post("/upload", status_code=202)
async def upload_video(
    video: UploadFile = File(...),
    angle_threshold: int = Query(default=90, ge=30, le=120),
    use_3d: bool = Query(default=True),
):
    """Accept a video file, save it, and enqueue a processing job."""
    job_id = str(uuid.uuid4())
    suffix = Path(video.filename).suffix or ".mp4"
    input_path = UPLOAD_DIR / f"{job_id}{suffix}"
    output_path = OUTPUT_DIR / f"analyzed_{job_id}.mp4"

    with open(input_path, "wb") as f:
        shutil.copyfileobj(video.file, f)

    process_video_task.apply_async(
        args=[str(input_path), str(output_path), angle_threshold, use_3d],
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
