"""Pose analysis logic for climbing efficiency detection."""
import cv2
import numpy as np
import mediapipe as mp
from typing import Tuple, Optional
from dataclasses import dataclass


@dataclass
class AnalysisResult:
    """Results from pose analysis."""
    good_frames: int
    bad_frames: int
    efficiency: float
    processed_video_path: Optional[str] = None


class PoseAnalyzer:
    """Analyzes climbing poses and calculates efficiency."""
    
    # Color definitions
    BLUE = (255, 127, 0)
    RED = (50, 50, 255)
    GREEN = (127, 255, 0)
    YELLOW = (0, 255, 255)
    BLACK = (0, 0, 0)
    
    def __init__(self, angle_threshold: int = 90):
        """
        Initialize the pose analyzer.
        
        Args:
            angle_threshold: Angle threshold for determining good/bad frames (degrees)
        """
        self.angle_threshold = angle_threshold
        self.mp_pose = mp.solutions.pose
        self.mp_draw = mp.solutions.drawing_utils
        
    def _get_arm_landmarks(
        self, 
        landmarks, 
        h: int, 
        w: int, 
        side: str = 'right'
    ) -> Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]]:
        """
        Extract arm landmarks for specified side.
        
        Args:
            landmarks: MediaPipe pose landmarks
            h: Image height
            w: Image width
            side: 'right' or 'left'
            
        Returns:
            Tuple of (shoulder, elbow, wrist) coordinates
        """
        prefix = 'RIGHT' if side.lower() == 'right' else 'LEFT'
        
        shoulder = (
            landmarks[getattr(self.mp_pose.PoseLandmark, f'{prefix}_SHOULDER').value].x * w,
            landmarks[getattr(self.mp_pose.PoseLandmark, f'{prefix}_SHOULDER').value].y * h
        )
        elbow = (
            landmarks[getattr(self.mp_pose.PoseLandmark, f'{prefix}_ELBOW').value].x * w,
            landmarks[getattr(self.mp_pose.PoseLandmark, f'{prefix}_ELBOW').value].y * h
        )
        wrist = (
            landmarks[getattr(self.mp_pose.PoseLandmark, f'{prefix}_WRIST').value].x * w,
            landmarks[getattr(self.mp_pose.PoseLandmark, f'{prefix}_WRIST').value].y * h
        )
        
        return shoulder, elbow, wrist
    
    def _calculate_angle(
        self, 
        x1: float, 
        y1: float, 
        x2: float, 
        y2: float
    ) -> float:
        """
        Calculate the inner angle between two vectors.
        
        Args:
            x1, y1: First vector components
            x2, y2: Second vector components
            
        Returns:
            Angle in degrees
        """
        vec1 = np.array([x1, y1])
        vec2 = np.array([x2, y2])
        
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        cos_theta = np.dot(vec1, vec2) / (norm1 * norm2)
        cos_theta = np.clip(cos_theta, -1.0, 1.0)
        
        theta_rads = np.arccos(cos_theta)
        theta_deg = np.degrees(theta_rads)
        
        return theta_deg
    
    def _put_text_with_background(
        self,
        image: np.ndarray,
        text: str,
        position: Tuple[int, int],
        font: int,
        scale: float,
        color: Tuple[int, int, int],
        thickness: int,
        bg_color: Tuple[int, int, int]
    ) -> None:
        """Draw text with a background rectangle."""
        (text_width, text_height), baseline = cv2.getTextSize(
            text, font, scale, thickness
        )
        bottom_left = (position[0], position[1] + baseline)
        top_right = (position[0] + text_width, position[1] - text_height - baseline)
        cv2.rectangle(image, bottom_left, top_right, bg_color, cv2.FILLED)
        cv2.putText(image, text, position, font, scale, color, thickness)
    
    def _draw_landmarks_and_classify(
        self,
        img: np.ndarray,
        results,
        r_bicep_angle: float,
        l_bicep_angle: float
    ) -> bool:
        """
        Draw landmarks on image and classify frame as good/bad.
        
        Returns:
            True if good frame, False if bad frame
        """
        is_good_frame = not (
            r_bicep_angle <= self.angle_threshold and 
            l_bicep_angle <= self.angle_threshold
        )
        
        connection_color = self.GREEN if is_good_frame else self.RED
        
        self.mp_draw.draw_landmarks(
            img,
            results.pose_landmarks,
            self.mp_pose.POSE_CONNECTIONS,
            self.mp_draw.DrawingSpec(color=self.YELLOW, thickness=2, circle_radius=2),
            self.mp_draw.DrawingSpec(color=connection_color, thickness=2, circle_radius=2)
        )
        
        return is_good_frame
    
    def analyze_frame(
        self,
        img: np.ndarray,
        pose
    ) -> Tuple[np.ndarray, bool, Optional[Tuple[float, float]]]:
        """
        Analyze a single frame for climbing efficiency.
        
        Args:
            img: Input frame (BGR format)
            pose: MediaPipe Pose object
            
        Returns:
            Tuple of (processed_image, is_good_frame, (r_angle, l_angle))
        """
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = pose.process(img_rgb)
        
        if not results.pose_landmarks:
            return img, True, None
        
        h, w, c = img.shape
        landmarks = results.pose_landmarks.landmark
        
        # Get arm landmarks
        r_shoulder, r_elbow, r_wrist = self._get_arm_landmarks(landmarks, h, w, 'right')
        l_shoulder, l_elbow, l_wrist = self._get_arm_landmarks(landmarks, h, w, 'left')
        
        # Calculate angles
        r_bicep_angle = self._calculate_angle(
            r_shoulder[0] - r_elbow[0], r_shoulder[1] - r_elbow[1],
            r_wrist[0] - r_elbow[0], r_wrist[1] - r_elbow[1]
        )
        l_bicep_angle = self._calculate_angle(
            l_shoulder[0] - l_elbow[0], l_shoulder[1] - l_elbow[1],
            l_wrist[0] - l_elbow[0], l_wrist[1] - l_elbow[1]
        )
        
        # Draw landmarks and classify
        is_good_frame = self._draw_landmarks_and_classify(
            img, results, r_bicep_angle, l_bicep_angle
        )
        
        return img, is_good_frame, (r_bicep_angle, l_bicep_angle)
    
    def add_stats_overlay(
        self,
        img: np.ndarray,
        good_frames: int,
        bad_frames: int
    ) -> np.ndarray:
        """Add statistics overlay to the frame."""
        total_frames = good_frames + bad_frames
        efficiency = (good_frames / total_frames * 100.0) if total_frames > 0 else 0.0
        
        font = cv2.FONT_HERSHEY_SIMPLEX
        
        self._put_text_with_background(
            img, f"Climbing Efficiency: {efficiency:.2f}%",
            (10, 45), font, 1, self.BLUE, 1, self.BLACK
        )
        self._put_text_with_background(
            img, f"Good: {good_frames}",
            (10, 70), font, 0.5, self.GREEN, 1, self.BLACK
        )
        self._put_text_with_background(
            img, f"Bad: {bad_frames}",
            (10, 100), font, 0.5, self.RED, 1, self.BLACK
        )
        
        return img
