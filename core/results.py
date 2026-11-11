"""Result containers produced by the pipeline. Serialized to JSON in api/jobs.py."""
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

Vec3 = Tuple[float, float, float]


@dataclass
class FrameResult:
    """Per-inference-frame output. Serialized positionally — see PoseEntry in frontend/src/types.ts."""
    frame_num: int
    world_lms: np.ndarray                      # (33, 3) metres, hip-centred (MediaPipe world landmarks)
    is_good: bool
    com: Optional[Vec3]                        # smoothed centre of mass, metres, hip-relative
    r_angle: float                             # right elbow angle, degrees (2D pixel space)
    l_angle: float                             # left elbow angle, degrees (2D pixel space)
    hip_plane_dist: Optional[float] = None     # hip-to-contact-plane distance / torso length
    plane_centroid: Optional[Vec3] = None      # smoothed contact-point centroid
    plane_normal: Optional[Vec3] = None        # smoothed unit normal, pointing away from the wall


@dataclass
class AnalysisResult:
    good_frames: int
    bad_frames: int
    efficiency: float
    fps: int = 30
    processed_video_path: Optional[str] = None
    pose_data_3d: Optional[List[FrameResult]] = None
    camera: Optional[dict] = None              # CameraMotion.summary(), when camera motion was estimated
