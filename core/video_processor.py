"""Video processing utilities for CruxCam."""
import cv2
import tempfile
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
        progress_callback: Optional[Callable[[int, int], None]] = None
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
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        if output_path is None:
            temp_file = tempfile.NamedTemporaryFile(
                delete=False, suffix='.mp4', prefix='cruxcam_'
            )
            output_path = temp_file.name
            temp_file.close()
        
        fourcc = cv2.VideoWriter_fourcc(*'avc1')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        if not out.isOpened():
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            tmp_output = output_path.replace('.mp4', '_raw.mp4')
            out = cv2.VideoWriter(tmp_output, fourcc, fps, (width, height))
        else:
            tmp_output = None
        
        self.pose_analyzer.reset()

        pose = mp.solutions.pose.Pose()
        
        good_frames = 0
        bad_frames = 0
        frame_count = 0
        
        try:
            while cap.isOpened():
                success, frame = cap.read()
                if not success:
                    break
                
                processed_frame, is_good, angles = self.pose_analyzer.analyze_frame(
                    frame, pose
                )
                
                if angles is not None:  
                    if is_good:
                        good_frames += 1
                    else:
                        bad_frames += 1
                
                processed_frame = self.pose_analyzer.add_stats_overlay(
                    processed_frame, good_frames, bad_frames
                )
                
                out.write(processed_frame)
                
                frame_count += 1
                if progress_callback:
                    progress_callback(frame_count, total_frames)
                    
        finally:
            cap.release()
            out.release()
            pose.close()
        
        if tmp_output is not None:
            import subprocess
            subprocess.run(
                ['ffmpeg', '-y', '-i', tmp_output, '-vcodec', 'libx264', '-acodec', 'aac', output_path],
                check=True, capture_output=True
            )
            Path(tmp_output).unlink(missing_ok=True)

        total = good_frames + bad_frames
        efficiency = (good_frames / total * 100.0) if total > 0 else 0.0

        return AnalysisResult(
            good_frames=good_frames,
            bad_frames=bad_frames,
            efficiency=efficiency,
            processed_video_path=output_path
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
