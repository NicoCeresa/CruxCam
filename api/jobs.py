"""Job state (in memory), submission, background execution and result serialization."""
import json
import logging
import threading
import time
from concurrent.futures import Executor
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

import numpy as np

from core.camera_motion import CameraMotion
from core.pose_analyzer import PoseAnalyzer
from core.results import AnalysisResult
from core.video_processor import VideoProcessor

log = logging.getLogger(__name__)


class JobStore:
    """Job state in memory, expiring `ttl` seconds after its last update.

    Jobs run in this process's executor, so a restart loses them anyway; an external
    store would add a service without adding durability. Assumes a single instance.
    """

    def __init__(self, ttl: int, clock: Callable[[], float] = time.monotonic):
        self._ttl = ttl
        self._clock = clock
        self._jobs: Dict[str, Tuple[float, str]] = {}
        self._lock = threading.Lock()

    def set(self, job_id: str, state: dict) -> None:
        now = self._clock()
        with self._lock:
            self._jobs = {k: v for k, v in self._jobs.items() if v[0] > now}
            self._jobs[job_id] = (now + self._ttl, json.dumps(state))

    def get(self, job_id: str) -> Optional[dict]:
        with self._lock:
            entry = self._jobs.get(job_id)
        if entry is None or entry[0] <= self._clock():
            return None
        return json.loads(entry[1])


def progress_payload(data: Optional[dict]) -> dict:
    """Client-facing status for a job's stored state. Shared by /status and /stream."""
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


def submit_job(
    store: JobStore,
    executor: Executor,
    job_id: str,
    input_path: str,
    output_path: str,
    angle_threshold: int,
    start_frame: int,
    end_frame: Optional[int],
    frame_skip: int,
    inference_path: Optional[str] = None,
) -> None:
    store.set(job_id, {"status": "pending"})
    executor.submit(
        run_job,
        job_id, input_path, output_path,
        angle_threshold, start_frame, end_frame, frame_skip,
        store.set, inference_path,
    )


_DECIMALS = 4   # 0.1 mm for world coords — far below MediaPipe's noise


def _round(v: Optional[float]) -> Optional[float]:
    return None if v is None else round(float(v), _DECIMALS)


def _round_vec(v) -> Optional[list]:
    return None if v is None else [round(float(x), _DECIMALS) for x in v]


def serialize_result(result: AnalysisResult) -> dict:
    # pose_data_3d is sent positionally to keep the payload small — see PoseEntry in types.ts.
    pose_data = None
    if result.pose_data_3d:
        pose_data = [
            [
                f.frame_num,
                np.round(f.world_lms.astype(np.float64), _DECIMALS).tolist(),
                f.is_good,
                _round_vec(f.com),
                _round(f.r_angle),
                _round(f.l_angle),
                _round(f.hip_plane_dist),
                _round_vec(f.plane_centroid),
                _round_vec(f.plane_normal),
            ]
            for f in result.pose_data_3d
        ]
    return {
        "good_frames": result.good_frames,
        "bad_frames": result.bad_frames,
        "efficiency": result.efficiency,
        "fps": result.fps,
        "pose_data_3d": pose_data,
    }


def build_processor(angle_threshold: int, camera_mode: Optional[str] = None) -> VideoProcessor:
    """Assemble the pipeline for one job. camera_mode None → camera motion is not estimated."""
    camera_motion = CameraMotion(camera_mode) if camera_mode else None
    return VideoProcessor(PoseAnalyzer(angle_threshold=angle_threshold), camera_motion=camera_motion)


def run_job(
    job_id: str,
    input_path: str,
    output_path: str,
    angle_threshold: int,
    start_frame: int,
    end_frame: Optional[int],
    frame_skip: int,
    set_state: Callable[[str, dict], None],
    inference_path: Optional[str] = None,
) -> None:
    log.info("job start  id=%s  input=%s  exists=%s", job_id, input_path, Path(input_path).exists())
    input_file = Path(input_path)

    if not input_file.exists():
        set_state(job_id, {"status": "failed", "error": "Input file missing — please re-upload the video"})
        return

    # Create a fresh processor per job — model is loaded here and released in finally.
    processor = build_processor(angle_threshold)

    def _progress(current: int, total: int) -> None:
        set_state(job_id, {"status": "processing", "current": current, "total": total})

    try:
        result = processor.process_video(
            input_path, output_path,
            progress_callback=_progress,
            start_frame=start_frame,
            end_frame=end_frame,
            frame_skip=frame_skip,
            inference_path=inference_path,
        )
        serialized = serialize_result(result)
        input_file.unlink(missing_ok=True)
        # video_path stays server-side: /video reads it, /result never returns it.
        set_state(job_id, {"status": "complete", "result": serialized,
                           "video_path": result.processed_video_path})
    except Exception:
        input_file.unlink(missing_ok=True)
        # Details (paths, ffmpeg output) go to the log, not to the client.
        log.exception("job failed  id=%s", job_id)
        set_state(job_id, {"status": "failed", "error": "Processing failed — the video could not be analyzed"})
    finally:
        # Explicitly close MediaPipe to release native memory immediately.
        try:
            processor.close()
        except Exception:
            pass
        if inference_path:
            Path(inference_path).unlink(missing_ok=True)
