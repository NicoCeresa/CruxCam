"""Video processing utilities for CruxCam."""
import cv2
import queue
import tempfile
import threading
from pathlib import Path
from typing import Optional, Callable, Generator
import mediapipe as mp
from .pose_analyzer import PoseAnalyzer, AnalysisResult


class VideoProcessor:
    
    def __init__(self, pose_analyzer: Optional[PoseAnalyzer] = None):
        """
        Initialize video processor.
        
        Args:
            pose_analyzer: PoseAnalyzer instance (creates default if None)
        """
        self.pose_analyzer = pose_analyzer or PoseAnalyzer()
        
    def process_video(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        start_frame: int = 0,
        end_frame: Optional[int] = None,
    ) -> AnalysisResult:
        """
        Process video file and analyze climbing efficiency.
        
        Args:
            input_path: Path to input video file
            output_path: Path for output video (optional, creates temp if None)
            progress_callback: Function called with (current_frame, total_frames)
            
        Returns:
            AnalysisResult with statistics and output path
        """
        if not Path(input_path).exists():
            raise FileNotFoundError(f"Input video not found: {input_path}")
        
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video file: {input_path}")
        
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        raw_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        start_frame = max(0, start_frame)
        end_frame = min(end_frame, raw_total) if end_frame is not None else raw_total
        total_frames = end_frame - start_frame
        
        if output_path is None:
            temp_file = tempfile.NamedTemporaryFile(
                delete=False, suffix='.mp4', prefix='cruxcam_'
            )
            output_path = temp_file.name
            temp_file.close()
        
        # Write raw frames with mp4v, then re-encode to H.264 via ffmpeg for browser compatibility
        tmp_output = output_path.replace('.mp4', '_raw.mp4')
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(tmp_output, fourcc, fps, (width, height))
        
        self.pose_analyzer.reset()

        pose = mp.solutions.pose.Pose()

        good_frames = 0
        bad_frames = 0
        frame_count = 0
        pose_data_3d = []

        # Pipeline: reader thread → frame_q → inference (main) → write_q → writer thread
        # Overlaps disk I/O with pose inference so reads and writes don't stall the CPU.
        _DONE = object()
        frame_q = queue.Queue(maxsize=8)
        write_q = queue.Queue(maxsize=8)
        reader_exc: list = [None]
        writer_exc: list = [None]

        def _reader():
            try:
                cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
                for _ in range(total_frames):
                    ok, frame = cap.read()
                    if not ok:
                        break
                    frame_q.put(frame)
            except Exception as exc:
                reader_exc[0] = exc
            finally:
                frame_q.put(_DONE)

        def _writer():
            try:
                while True:
                    item = write_q.get()
                    if item is _DONE:
                        break
                    out.write(item)
            except Exception as exc:
                writer_exc[0] = exc

        reader_thread = threading.Thread(target=_reader, daemon=True)
        writer_thread = threading.Thread(target=_writer, daemon=True)
        reader_thread.start()
        writer_thread.start()

        try:
            while True:
                frame = frame_q.get()
                if frame is _DONE:
                    break
                if reader_exc[0]:
                    raise reader_exc[0]

                processed_frame, is_good, angles, world_lms = self.pose_analyzer.analyze_frame(
                    frame, pose
                )

                if angles is not None:
                    if is_good:
                        good_frames += 1
                    else:
                        bad_frames += 1
                    pose_data_3d.append((
                        frame_count,
                        world_lms,
                        is_good,
                        self.pose_analyzer.com_3d
                    ))

                processed_frame = self.pose_analyzer.add_stats_overlay(
                    processed_frame, good_frames, bad_frames
                )
                write_q.put(processed_frame)

                frame_count += 1
                if progress_callback:
                    progress_callback(frame_count, total_frames)

        finally:
            write_q.put(_DONE)
            pose.close()
            cap.release()

        if reader_exc[0]:
            raise reader_exc[0]

        writer_thread.join()
        out.release()

        if writer_exc[0]:
            raise writer_exc[0]
        
        import subprocess
        subprocess.run(
            ['ffmpeg', '-y', '-i', tmp_output, '-c:v', 'libx264', '-preset', 'fast', '-crf', '23', output_path],
            check=True, capture_output=True,
        )
        Path(tmp_output).unlink(missing_ok=True)

        total = good_frames + bad_frames
        efficiency = (good_frames / total * 100.0) if total > 0 else 0.0

        return AnalysisResult(
            good_frames=good_frames,
            bad_frames=bad_frames,
            efficiency=efficiency,
            processed_video_path=output_path,
            pose_data_3d=pose_data_3d if pose_data_3d else None
        )
    
    def get_video_info(self, video_path: str) -> dict:
        """
        Get metadata about a video file.
        
        Args:
            video_path: Path to video file
            
        Returns:
            Dictionary with video metadata
        """
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
        """
        Extract frames from video for preview.
        
        Args:
            video_path: Path to video file
            max_frames: Maximum number of frames to extract
            
        Yields:
            Tuples of (frame_number, frame_image)
        """
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
