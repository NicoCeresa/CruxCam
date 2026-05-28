"""Video processing utilities for CruxCam."""
import cv2
import queue
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Optional, Callable, Generator
import mediapipe as mp
from .pose_analyzer import PoseAnalyzer, AnalysisResult


class VideoProcessor:

    def __init__(self, pose_analyzer: Optional[PoseAnalyzer] = None):
        self.pose_analyzer = pose_analyzer or PoseAnalyzer()
        self._pose = mp.solutions.pose.Pose(model_complexity=0)

    def process_video(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        start_frame: int = 0,
        end_frame: Optional[int] = None,
        frame_skip: int = 1,
    ) -> AnalysisResult:
        if not Path(input_path).exists():
            raise FileNotFoundError(f"Input video not found: {input_path}")

        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video file: {input_path}")

        fps        = int(cap.get(cv2.CAP_PROP_FPS))
        raw_total  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        start_frame  = max(0, start_frame)
        end_frame    = min(end_frame, raw_total) if end_frame is not None else raw_total
        total_frames = end_frame - start_frame

        if output_path is None:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4', prefix='cruxcam_')
            output_path = tmp.name
            tmp.close()

        self.pose_analyzer.reset()

        good_frames = 0
        bad_frames  = 0
        frame_count = 0
        pose_data_3d = []

        # Reader thread overlaps disk I/O with inference.
        # No writer thread — output is produced by ffmpeg after inference completes.
        _DONE = object()
        frame_q    = queue.Queue(maxsize=4)
        reader_exc: list = [None]
        actual_frames_read: list = [0]

        def _reader():
            try:
                cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
                for _ in range(total_frames):
                    ok, frame = cap.read()
                    if not ok:
                        break
                    frame_q.put(frame)
                    actual_frames_read[0] += 1
            except Exception as exc:
                reader_exc[0] = exc
            finally:
                frame_q.put(_DONE)

        reader_thread = threading.Thread(target=_reader, daemon=True)
        reader_thread.start()

        try:
            while True:
                frame = frame_q.get()
                if frame is _DONE:
                    break
                if reader_exc[0]:
                    raise reader_exc[0]

                is_inference_frame = frame_count % frame_skip == 0
                _, is_good, angles, world_lms = self.pose_analyzer.analyze_frame(
                    frame, self._pose if is_inference_frame else None, draw=False
                )

                if angles is not None:
                    if is_good:
                        good_frames += 1
                    else:
                        bad_frames += 1
                    if is_inference_frame and world_lms is not None:
                        plane = self.pose_analyzer.plane_data
                        pose_data_3d.append((
                            frame_count,
                            world_lms,
                            is_good,
                            self.pose_analyzer.com_3d,
                            angles[0],          # r_angle
                            angles[1],          # l_angle
                            plane[0] if plane else None,  # hip_plane_dist
                            plane[1] if plane else None,  # centroid (x,y,z)
                            plane[2] if plane else None,  # normal  (x,y,z)
                        ))

                frame_count += 1
                if progress_callback and frame_count % 10 == 0:
                    real_total = actual_frames_read[0] or total_frames
                    progress_callback(min(frame_count, real_total), real_total)

        finally:
            cap.release()

        if reader_exc[0]:
            raise reader_exc[0]

        reader_thread.join()

        # Trim + re-encode with ffmpeg. Since no annotations are drawn on frames,
        # the output is just a browser-compatible slice of the input.
        ffmpeg = shutil.which('ffmpeg') or 'ffmpeg'
        start_secs   = start_frame / max(fps, 1)
        duration_secs = total_frames / max(fps, 1)
        result = subprocess.run(
            [
                ffmpeg, '-y',
                '-ss', str(start_secs),
                '-i', input_path,
                '-t', str(duration_secs),
                '-c:v', 'copy',
                '-movflags', '+faststart',
                output_path,
            ],
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg failed (exit {result.returncode}): "
                f"{result.stderr.decode(errors='replace').strip()}"
            )

        total      = good_frames + bad_frames
        efficiency = (good_frames / total * 100.0) if total > 0 else 0.0

        return AnalysisResult(
            good_frames=good_frames,
            bad_frames=bad_frames,
            efficiency=efficiency,
            fps=fps,
            processed_video_path=output_path,
            pose_data_3d=pose_data_3d if pose_data_3d else None
        )

    def get_video_info(self, video_path: str) -> dict:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video file: {video_path}")
        info = {
            'fps': int(cap.get(cv2.CAP_PROP_FPS)),
            'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            'total_frames': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            'duration': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) / int(cap.get(cv2.CAP_PROP_FPS))
        }
        cap.release()
        return info

    def extract_frames(
        self,
        video_path: str,
        max_frames: int = 10
    ) -> Generator[tuple, None, None]:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video file: {video_path}")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        step = max(1, total_frames // max_frames)
        frame_num = 0
        extracted = 0

        try:
            while cap.isOpened() and extracted < max_frames:
                success, frame = cap.read()
                if not success:
                    break
                if frame_num % step == 0:
                    yield (frame_num, frame)
                    extracted += 1
                frame_num += 1
        finally:
            cap.release()
