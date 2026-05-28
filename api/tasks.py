import logging
from pathlib import Path
from typing import Callable, Optional

from core.pose_analyzer import AnalysisResult, PoseAnalyzer
from core.video_processor import VideoProcessor

log = logging.getLogger(__name__)


def serialize_result(result: AnalysisResult) -> dict:
    pose_data = None
    if result.pose_data_3d:
        pose_data = [
            [
                entry[0],
                entry[1].tolist() if entry[1] is not None else None,
                entry[2],
                list(entry[3]) if entry[3] is not None else None,
                entry[4] if len(entry) > 4 else None,
                entry[5] if len(entry) > 5 else None,
                entry[6] if len(entry) > 6 else None,
                list(entry[7]) if len(entry) > 7 and entry[7] is not None else None,
                list(entry[8]) if len(entry) > 8 and entry[8] is not None else None,
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


def process_video(
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
        set_state(job_id, {"status": "failed", "error": f"Input file missing: {input_path}"})
        return

    # Create a fresh processor per job — model is loaded here and released in finally.
    processor = VideoProcessor(PoseAnalyzer(angle_threshold=angle_threshold))

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
        set_state(job_id, {"status": "complete", "result": serialized})
    except Exception as exc:
        input_file.unlink(missing_ok=True)
        log.exception("job failed  id=%s", job_id)
        set_state(job_id, {"status": "failed", "error": str(exc).splitlines()[0]})
    finally:
        # Explicitly close MediaPipe to release native memory immediately.
        try:
            processor._pose.close()
        except Exception:
            pass
        if inference_path:
            Path(inference_path).unlink(missing_ok=True)
