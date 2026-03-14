import cv2
import numpy as np
import mediapipe as mp
from typing import Tuple, Optional
from dataclasses import dataclass


@dataclass
class AnalysisResult:
    good_frames: int
    bad_frames: int
    efficiency: float
    processed_video_path: Optional[str] = None


class PoseAnalyzer:
    
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
        self._com_alpha = 0.2  # EMA factor: lower = smoother, more lag
        self.reset()

    def reset(self) -> None:
        """Reset per-video state. Call before processing each new video."""
        self._com_x: Optional[float] = None
        self._com_y: Optional[float] = None
        
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
    
    def _draw_semi_transparent_rect(
        self,
        image: np.ndarray,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        color: Tuple[int, int, int],
        alpha: float
    ) -> None:

        overlay = image.copy()
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, cv2.FILLED)
        cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0, image)
    
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
    
    def _draw_center_of_mass(
        self,
        img: np.ndarray,
        landmarks,
        h: int,
        w: int
    ) -> None:
        """
        Weights for center of mass calculation based on body segments:
        head 8%, torso 50%, each arm 5%, each leg 16%.
        Each segment centroid is the mean of its visible landmarks.
        """
        LP = self.mp_pose.PoseLandmark

        segments = {
            'head':      (0.08, [LP.NOSE, LP.LEFT_EAR, LP.RIGHT_EAR]),
            'torso':     (0.50, [LP.LEFT_SHOULDER, LP.RIGHT_SHOULDER, LP.LEFT_HIP, LP.RIGHT_HIP]),
            'left_leg':  (0.16, [LP.LEFT_HIP,  LP.LEFT_KNEE,  LP.LEFT_ANKLE]),
            'right_leg': (0.16, [LP.RIGHT_HIP, LP.RIGHT_KNEE, LP.RIGHT_ANKLE]),
            'left_arm':  (0.05, [LP.LEFT_SHOULDER,  LP.LEFT_ELBOW,  LP.LEFT_WRIST]),
            'right_arm': (0.05, [LP.RIGHT_SHOULDER, LP.RIGHT_ELBOW, LP.RIGHT_WRIST]),
        }

        raw_x, raw_y, total_weight = 0.0, 0.0, 0.0
        for weight, lm_ids in segments.values():
            pts = [
                (landmarks[lm.value].x * w, landmarks[lm.value].y * h)
                for lm in lm_ids
                if landmarks[lm.value].visibility > 0.5
            ]
            if not pts:
                continue
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            raw_x += weight * cx
            raw_y += weight * cy
            total_weight += weight

        if total_weight == 0:
            return
        raw_x /= total_weight
        raw_y /= total_weight

        if self._com_x is None:
            self._com_x, self._com_y = raw_x, raw_y
        else:
            self._com_x = self._com_alpha * raw_x + (1 - self._com_alpha) * self._com_x
            self._com_y = self._com_alpha * raw_y + (1 - self._com_alpha) * self._com_y

        mid_x, mid_y = int(self._com_x), int(self._com_y)

        cv2.circle(img, (mid_x, mid_y), 7, self.BLUE, -1, cv2.LINE_AA)
        cv2.circle(img, (mid_x, mid_y), 9, (255, 255, 255), 1, cv2.LINE_AA)

        cv2.putText(
            img, "CoM", (mid_x + 12, mid_y + 5),
            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA
        )

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
        
        h, w = img.shape[:2]
        landmarks = results.pose_landmarks.landmark
        
        r_shoulder, r_elbow, r_wrist = self._get_arm_landmarks(landmarks, h, w, 'right')
        l_shoulder, l_elbow, l_wrist = self._get_arm_landmarks(landmarks, h, w, 'left')
        
        r_bicep_angle = self._calculate_angle(
            r_shoulder[0] - r_elbow[0], r_shoulder[1] - r_elbow[1],
            r_wrist[0] - r_elbow[0], r_wrist[1] - r_elbow[1]
        )
        l_bicep_angle = self._calculate_angle(
            l_shoulder[0] - l_elbow[0], l_shoulder[1] - l_elbow[1],
            l_wrist[0] - l_elbow[0], l_wrist[1] - l_elbow[1]
        )
        
        is_good_frame = self._draw_landmarks_and_classify(
            img, results, r_bicep_angle, l_bicep_angle
        )

        self._draw_center_of_mass(img, landmarks, h, w)

        return img, is_good_frame, (r_bicep_angle, l_bicep_angle)
    
    def add_stats_overlay(
        self,
        img: np.ndarray,
        good_frames: int,
        bad_frames: int
    ) -> np.ndarray:
        
        total_frames = good_frames + bad_frames
        efficiency = (good_frames / total_frames * 100.0) if total_frames > 0 else 0.0

        h, w = img.shape[:2]
        font = cv2.FONT_HERSHEY_SIMPLEX

        # Panel dimensions (top-left corner)
        pad = 12
        panel_w = 260
        panel_h = 110
        panel_x, panel_y = 16, 16

        # Semi-transparent dark panel
        self._draw_semi_transparent_rect(
            img, panel_x, panel_y, panel_x + panel_w, panel_y + panel_h,
            (20, 20, 20), alpha=0.6
        )

        # Thin border around panel
        cv2.rectangle(img, (panel_x, panel_y), (panel_x + panel_w, panel_y + panel_h),
                      (80, 80, 80), 1)

        # --- Title ---
        cv2.putText(img, "CruxCam", (panel_x + pad, panel_y + 28),
                    font, 0.65, (200, 200, 200), 1, cv2.LINE_AA)

        # --- Efficiency score, color-coded ---
        if efficiency >= 70:
            score_color = self.GREEN
        elif efficiency >= 50:
            score_color = self.YELLOW
        else:
            score_color = self.RED

        cv2.putText(img, f"{efficiency:.1f}%", (panel_x + pad, panel_y + 60),
                    font, 1.1, score_color, 2, cv2.LINE_AA)

        # --- Efficiency bar ---
        bar_x = panel_x + pad
        bar_y = panel_y + 70
        bar_w = panel_w - 2 * pad
        bar_h = 8
        bar_fill = int(bar_w * efficiency / 100)

        cv2.rectangle(img, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h),
                      (60, 60, 60), cv2.FILLED)
        if bar_fill > 0:
            cv2.rectangle(img, (bar_x, bar_y), (bar_x + bar_fill, bar_y + bar_h),
                          score_color, cv2.FILLED)

        # --- Good / Bad frame counts ---
        cv2.putText(img, f"Good  {good_frames}", (panel_x + pad, panel_y + 98),
                    font, 0.45, self.GREEN, 1, cv2.LINE_AA)
        cv2.putText(img, f"Bad  {bad_frames}", (panel_x + pad + 110, panel_y + 98),
                    font, 0.45, self.RED, 1, cv2.LINE_AA)

        return img
