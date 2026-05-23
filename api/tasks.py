import logging
from pathlib import Path
from typing import Optional

import numpy as np

from .celery_app import celery_app
from core.pose_analyzer import AnalysisResult, PoseAnalyzer
from core.video_processor import VideoProcessor

log = logging.getLogger(__name__)

# Cached per worker process — keeps the MediaPipe Pose model loaded across tasks.
_processor: Optional[VideoProcessor] = None


def serialize_result(result: AnalysisResult) -> dict:
    """Convert AnalysisResult to a JSON-safe dict (numpy arrays → lists)."""
    pose_data = None
    if result.pose_data_3d:
        pose_data = [
            [
                entry[0],                                                   # frame_num
                entry[1].tolist() if entry[1] is not None else None,        # world_lms (33,3)
                entry[2],                                                   # is_good
                list(entry[3]) if entry[3] is not None else None,           # com_xyz
            ]
            for entry in result.pose_data_3d
        ]
    return {
        "good_frames": result.good_frames,
        "bad_frames": result.bad_frames,
        "efficiency": result.efficiency,
        "fps": result.fps,
        "processed_video_path": result.processed_video_path,
        "pose_data_3d": pose_data,
    }


def deserialize_result(data: dict) -> AnalysisResult:
    """Reconstruct an AnalysisResult from a JSON dict."""
    pose_data = None
    if data.get("pose_data_3d"):
        pose_data = [
            (
                entry[0],
                np.array(entry[1], dtype=np.float32) if entry[1] is not None else None,
                entry[2],
                tuple(entry[3]) if entry[3] is not None else None,
            )
            for entry in data["pose_data_3d"]
        ]
    return AnalysisResult(
        good_frames=data["good_frames"],
        bad_frames=data["bad_frames"],
        efficiency=data["efficiency"],
        fps=data.get("fps", 30),
        processed_video_path=data.get("processed_video_path"),
        pose_data_3d=pose_data,
    )


@celery_app.task(bind=True)
def process_video_task(
    self,
    input_path: str,
    output_path: str,
    angle_threshold: int = 90,
    start_frame: int = 0,
    end_frame: Optional[int] = None,
    frame_skip: int = 2,
) -> dict:
    global _processor

    log.info("task start  input=%s  exists=%s", input_path, Path(input_path).exists())

    if _processor is None:
        _processor = VideoProcessor(PoseAnalyzer(angle_threshold=angle_threshold))
    else:
        _processor.pose_analyzer.angle_threshold = angle_threshold

    def _progress(current: int, total: int) -> None:
        self.update_state(
            state="PROGRESS",
            meta={"current": current, "total": total},
        )

    input_file = Path(input_path)
    if not input_file.exists():
        raise FileNotFoundError(f"Input file missing before task start: {input_path}")

    try:
        result = _processor.process_video(
            input_path, output_path,
            progress_callback=_progress,
            start_frame=start_frame,
            end_frame=end_frame,
            frame_skip=frame_skip,
        )
        serialized = serialize_result(result)
        # Delete only after result is serialized — prevents re-queued retries
        # (task_acks_late=True) from failing with a missing file on the second run.
        input_file.unlink(missing_ok=True)
        return serialized
    except Exception:
        input_file.unlink(missing_ok=True)
        raise
