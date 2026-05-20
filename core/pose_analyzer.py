import cv2
import numpy as np
import mediapipe as mp
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class AnalysisResult:
    good_frames: int
    bad_frames: int
    efficiency: float
    processed_video_path: Optional[str] = None
    # Each entry: (frame_num, world_lms_33x3, is_good, com_xyz)
    # world_lms_33x3 is None when MediaPipe world landmarks unavailable
    pose_data_3d: Optional[List] = None


class PoseAnalyzer:

    BLUE = (255, 127, 0)
    RED = (50, 50, 255)
    GREEN = (127, 255, 0)
    YELLOW = (0, 255, 255)
    BLACK = (0, 0, 0)

    def __init__(self, angle_threshold: int = 90):
        self.angle_threshold = angle_threshold
        self.mp_pose = mp.solutions.pose
        self.mp_draw = mp.solutions.drawing_utils
        self._com_alpha = 0.2
        self.reset()

    def reset(self) -> None:
        """Reset per-video state. Call before processing each new video."""
        self._com_x: Optional[float] = None
        self._com_y: Optional[float] = None
        self._com_z: Optional[float] = None

    @property
    def com_3d(self) -> Optional[Tuple[float, float, float]]:
        """World-space CoM (meters, hip-relative)."""
        if self._com_x is None:
            return None
        return (float(self._com_x), float(self._com_y), float(self._com_z))

    def _get_arm_landmarks_3d(
        self,
        world_landmarks,
        side: str = 'right'
    ) -> Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]:
        """Extract arm landmarks in metric world space (meters, hip-relative)."""
        prefix = 'RIGHT' if side.lower() == 'right' else 'LEFT'
        def lm(name):
            pt = world_landmarks[getattr(self.mp_pose.PoseLandmark, name).value]
            return (pt.x, pt.y, pt.z)
        return (
            lm(f'{prefix}_SHOULDER'),
            lm(f'{prefix}_ELBOW'),
            lm(f'{prefix}_WRIST'),
        )

    def _calculate_angle(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """Calculate the inner angle between two vectors (N-dimensional)."""
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        cos_theta = np.clip(np.dot(v1, v2) / (norm1 * norm2), -1.0, 1.0)
        return float(np.degrees(np.arccos(cos_theta)))

    def _draw_semi_transparent_rect(
        self,
        image: np.ndarray,
        x1: int, y1: int, x2: int, y2: int,
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

    def _com_world_to_pixel(
        self,
        com_world: Tuple[float, float],
        landmarks_2d,
        world_landmarks,
        h: int,
        w: int
    ) -> Tuple[int, int]:
        """Convert world-space CoM (x, y in meters) to pixel coords using torso scale."""
        LP = self.mp_pose.PoseLandmark

        def px(lm): return np.array([landmarks_2d[lm.value].x * w, landmarks_2d[lm.value].y * h])
        def wd(lm): return np.array([world_landmarks[lm.value].x, world_landmarks[lm.value].y])

        hip_mid_px = (px(LP.LEFT_HIP) + px(LP.RIGHT_HIP)) / 2
        hip_mid_w  = (wd(LP.LEFT_HIP) + wd(LP.RIGHT_HIP)) / 2
        sho_mid_px = (px(LP.LEFT_SHOULDER) + px(LP.RIGHT_SHOULDER)) / 2
        sho_mid_w  = (wd(LP.LEFT_SHOULDER) + wd(LP.RIGHT_SHOULDER)) / 2

        torso_px = np.linalg.norm(sho_mid_px - hip_mid_px)
        torso_w  = np.linalg.norm(sho_mid_w - hip_mid_w)

        if torso_w < 1e-6:
            return int(hip_mid_px[0]), int(hip_mid_px[1])

        scale = torso_px / torso_w
        com_px_x = int(hip_mid_px[0] + (com_world[0] - hip_mid_w[0]) * scale)
        com_px_y = int(hip_mid_px[1] + (com_world[1] - hip_mid_w[1]) * scale)
        return com_px_x, com_px_y

    def _draw_center_of_mass(
        self,
        img: np.ndarray,
        landmarks,
        h: int,
        w: int,
        world_landmarks
    ) -> None:
        """Weighted body segment CoM computed in world space (meters) then projected to pixel."""
        LP = self.mp_pose.PoseLandmark
        segments = {
            'head':      (0.08, [LP.NOSE, LP.LEFT_EAR, LP.RIGHT_EAR]),
            'torso':     (0.50, [LP.LEFT_SHOULDER, LP.RIGHT_SHOULDER, LP.LEFT_HIP, LP.RIGHT_HIP]),
            'left_leg':  (0.16, [LP.LEFT_HIP,  LP.LEFT_KNEE,  LP.LEFT_ANKLE]),
            'right_leg': (0.16, [LP.RIGHT_HIP, LP.RIGHT_KNEE, LP.RIGHT_ANKLE]),
            'left_arm':  (0.05, [LP.LEFT_SHOULDER,  LP.LEFT_ELBOW,  LP.LEFT_WRIST]),
            'right_arm': (0.05, [LP.RIGHT_SHOULDER, LP.RIGHT_ELBOW, LP.RIGHT_WRIST]),
        }

        raw_x, raw_y, raw_z, total_weight = 0.0, 0.0, 0.0, 0.0
        for weight, lm_ids in segments.values():
            pts = [
                (world_landmarks[lm.value].x,
                 world_landmarks[lm.value].y,
                 world_landmarks[lm.value].z)
                for lm in lm_ids
                if landmarks[lm.value].visibility > 0.5
            ]
            if not pts:
                continue
            raw_x += weight * sum(p[0] for p in pts) / len(pts)
            raw_y += weight * sum(p[1] for p in pts) / len(pts)
            raw_z += weight * sum(p[2] for p in pts) / len(pts)
            total_weight += weight

        if total_weight == 0:
            return
        raw_x /= total_weight
        raw_y /= total_weight
        raw_z /= total_weight

        if self._com_x is None:
            self._com_x, self._com_y, self._com_z = raw_x, raw_y, raw_z
        else:
            self._com_x = self._com_alpha * raw_x + (1 - self._com_alpha) * self._com_x
            self._com_y = self._com_alpha * raw_y + (1 - self._com_alpha) * self._com_y
            self._com_z = self._com_alpha * raw_z + (1 - self._com_alpha) * self._com_z

        mid_x, mid_y = self._com_world_to_pixel(
            (self._com_x, self._com_y), landmarks, world_landmarks, h, w
        )

        cv2.circle(img, (mid_x, mid_y), 7, self.BLUE, -1, cv2.LINE_AA)
        cv2.circle(img, (mid_x, mid_y), 9, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(
            img, f"CoM  z={self._com_z:.2f}m", (mid_x + 12, mid_y + 5),
            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA
        )

    def analyze_frame(
        self,
        img: np.ndarray,
        pose
    ) -> Tuple[np.ndarray, bool, Optional[Tuple[float, float]], Optional[np.ndarray]]:
        """
        Analyze a single frame for climbing efficiency.

        Returns:
            (processed_image, is_good_frame, (r_angle, l_angle), world_lms_33x3)
            angles and world_lms_33x3 are None when MediaPipe landmarks are unavailable.
        """
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = pose.process(img_rgb)

        if not results.pose_landmarks or not results.pose_world_landmarks:
            return img, True, None, None

        h, w = img.shape[:2]
        landmarks = results.pose_landmarks.landmark
        world_lms = results.pose_world_landmarks.landmark

        r_s, r_e, r_w = self._get_arm_landmarks_3d(world_lms, 'right')
        l_s, l_e, l_w = self._get_arm_landmarks_3d(world_lms, 'left')
        r_bicep_angle = self._calculate_angle(
            np.array(r_s) - np.array(r_e),
            np.array(r_w) - np.array(r_e)
        )
        l_bicep_angle = self._calculate_angle(
            np.array(l_s) - np.array(l_e),
            np.array(l_w) - np.array(l_e)
        )

        is_good_frame = self._draw_landmarks_and_classify(img, results, r_bicep_angle, l_bicep_angle)
        self._draw_center_of_mass(img, landmarks, h, w, world_lms)

        world_lms_array = np.array([[lm.x, lm.y, lm.z] for lm in world_lms], dtype=np.float32)

        return img, is_good_frame, (r_bicep_angle, l_bicep_angle), world_lms_array

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

        pad = 12
        panel_w = 260
        panel_h = 110
        panel_x, panel_y = 16, 16

        self._draw_semi_transparent_rect(
            img, panel_x, panel_y, panel_x + panel_w, panel_y + panel_h,
            (20, 20, 20), alpha=0.6
        )
        cv2.rectangle(img, (panel_x, panel_y), (panel_x + panel_w, panel_y + panel_h),
                      (80, 80, 80), 1)

        cv2.putText(img, "CruxCam", (panel_x + pad, panel_y + 28),
                    font, 0.65, (200, 200, 200), 1, cv2.LINE_AA)

        if efficiency >= 70:
            score_color = self.GREEN
        elif efficiency >= 50:
            score_color = self.YELLOW
        else:
            score_color = self.RED

        cv2.putText(img, f"{efficiency:.1f}%", (panel_x + pad, panel_y + 60),
                    font, 1.1, score_color, 2, cv2.LINE_AA)

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

        cv2.putText(img, f"Good  {good_frames}", (panel_x + pad, panel_y + 98),
                    font, 0.45, self.GREEN, 1, cv2.LINE_AA)
        cv2.putText(img, f"Bad  {bad_frames}", (panel_x + pad + 110, panel_y + 98),
                    font, 0.45, self.RED, 1, cv2.LINE_AA)

        return img
