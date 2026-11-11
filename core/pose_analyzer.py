import cv2
import numpy as np
import mediapipe as mp
from typing import Tuple, Optional


class PoseAnalyzer:
    """Runs MediaPipe Pose and derives per-frame climbing measurements.

    Owns the MediaPipe model — call close() when done.
    """

    def __init__(self, angle_threshold: int = 90):
        self.angle_threshold = angle_threshold
        self.mp_pose = mp.solutions.pose
        self._pose = self.mp_pose.Pose(model_complexity=0)
        self._com_alpha = 0.2
        self.reset()

    def reset(self) -> None:
        """Reset per-video state. Call before processing each new video."""
        self._com_x: Optional[float] = None
        self._com_y: Optional[float] = None
        self._com_z: Optional[float] = None
        self._last_results = None
        self._contact_pts: Optional[np.ndarray] = None   # (4, 3) smoothed
        self._plane_normal: Optional[np.ndarray] = None  # (3,) smoothed unit vector
        self._plane_centroid: Optional[np.ndarray] = None
        self._hip_plane_dist: Optional[float] = None

    def close(self) -> None:
        """Release MediaPipe's native resources."""
        self._pose.close()

    # Indices: L wrist=15, R wrist=16, L ankle=27, R ankle=28
    _CONTACT_IDX  = [15, 16, 27, 28]
    _CONTACT_ALPHA = 0.1   # EMA weight for contact points (long memory → smooth)
    _NORMAL_ALPHA  = 0.2   # EMA weight for plane normal   (slightly faster)

    def _update_contact_plane(self, world_lms) -> None:
        raw_pts = np.array(
            [[world_lms[i].x, world_lms[i].y, world_lms[i].z] for i in self._CONTACT_IDX],
            dtype=np.float32,
        )
        if self._contact_pts is None:
            self._contact_pts = raw_pts
        else:
            self._contact_pts = (
                self._CONTACT_ALPHA * raw_pts +
                (1 - self._CONTACT_ALPHA) * self._contact_pts
            )

        centroid = self._contact_pts.mean(axis=0)
        _, _, Vt = np.linalg.svd(self._contact_pts - centroid, full_matrices=False)
        raw_normal = Vt[-1]

        # Ensure normal consistently points toward the hip (away from the wall)
        hip_mid = np.array([
            (world_lms[23].x + world_lms[24].x) / 2,
            (world_lms[23].y + world_lms[24].y) / 2,
            (world_lms[23].z + world_lms[24].z) / 2,
        ], dtype=np.float32)
        if np.dot(raw_normal, hip_mid - centroid) < 0:
            raw_normal = -raw_normal

        if self._plane_normal is None:
            self._plane_normal = raw_normal
        else:
            self._plane_normal = (
                self._NORMAL_ALPHA * raw_normal +
                (1 - self._NORMAL_ALPHA) * self._plane_normal
            )
            self._plane_normal /= np.linalg.norm(self._plane_normal)

        self._plane_centroid = centroid

        dist = float(abs(np.dot(hip_mid - centroid, self._plane_normal)))
        sho_mid = np.array([
            (world_lms[11].x + world_lms[12].x) / 2,
            (world_lms[11].y + world_lms[12].y) / 2,
            (world_lms[11].z + world_lms[12].z) / 2,
        ], dtype=np.float32)
        torso_len = float(np.linalg.norm(sho_mid - hip_mid))
        self._hip_plane_dist = dist / torso_len if torso_len > 1e-6 else 0.0

    @property
    def plane_data(self) -> Optional[Tuple]:
        """(hip_plane_dist, centroid_xyz, normal_xyz) or None if not yet computed."""
        if self._hip_plane_dist is None or self._plane_centroid is None or self._plane_normal is None:
            return None
        return (
            float(self._hip_plane_dist),
            tuple(float(v) for v in self._plane_centroid),
            tuple(float(v) for v in self._plane_normal),
        )

    @property
    def com_3d(self) -> Optional[Tuple[float, float, float]]:
        """World-space CoM (meters, hip-relative)."""
        if self._com_x is None:
            return None
        return (float(self._com_x), float(self._com_y), float(self._com_z))

    def _calculate_angle(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """Calculate the inner angle between two vectors (N-dimensional)."""
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        cos_theta = np.clip(np.dot(v1, v2) / (norm1 * norm2), -1.0, 1.0)
        return float(np.degrees(np.arccos(cos_theta)))

    def _update_center_of_mass(self, landmarks, world_landmarks) -> None:
        """Weighted body segment CoM computed in world space (meters), EMA-smoothed."""
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

    def analyze_frame(
        self,
        img: np.ndarray,
        run_inference: bool = True,
    ) -> Tuple[bool, Optional[Tuple[float, float]], Optional[np.ndarray]]:
        """
        Analyze a single frame for climbing efficiency.

        When run_inference is False, the previous frame's MediaPipe results are reused.

        Returns:
            (is_good_frame, (r_angle, l_angle), world_lms_33x3)
            angles and world_lms_33x3 are None when MediaPipe landmarks are unavailable.
        """
        if run_inference:
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            self._last_results = self._pose.process(img_rgb)

        results = self._last_results
        if results is None or not results.pose_landmarks or not results.pose_world_landmarks:
            return True, None, None

        h, w = img.shape[:2]
        landmarks = results.pose_landmarks.landmark
        world_lms = results.pose_world_landmarks.landmark

        # Arm angles use 2D pixel-space landmarks — MediaPipe's 3D world estimates
        # are unreliable for non-standard poses and produce incorrect angles.
        LP = self.mp_pose.PoseLandmark
        def lm2d(lp): return np.array([landmarks[lp.value].x * w, landmarks[lp.value].y * h])

        r_s = lm2d(LP.RIGHT_SHOULDER); r_e = lm2d(LP.RIGHT_ELBOW); r_w = lm2d(LP.RIGHT_WRIST)
        l_s = lm2d(LP.LEFT_SHOULDER);  l_e = lm2d(LP.LEFT_ELBOW);  l_w = lm2d(LP.LEFT_WRIST)
        r_bicep_angle = self._calculate_angle(r_s - r_e, r_w - r_e)
        l_bicep_angle = self._calculate_angle(l_s - l_e, l_w - l_e)

        is_good_frame = not (
            r_bicep_angle <= self.angle_threshold and
            l_bicep_angle <= self.angle_threshold
        )
        self._update_center_of_mass(landmarks, world_lms)
        self._update_contact_plane(world_lms)

        world_lms_array = np.array([[lm.x, lm.y, lm.z] for lm in world_lms], dtype=np.float32)

        return is_good_frame, (r_bicep_angle, l_bicep_angle), world_lms_array
