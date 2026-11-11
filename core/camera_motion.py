"""Camera-motion estimation from wall features: pyramidal Lucas-Kanade + RANSAC homography.

"Wall coordinates" are the full-resolution pixel coordinates of the first tracked frame.
For each tracked frame we estimate H_wall_to_frame (3x3). On a tripod this stays ≈ identity.

Tracking is keyframe-based: features chosen on a keyframe are tracked directly from the
keyframe into each new frame (with the previous frame's positions as the initial guess),
so error doesn't accumulate frame-to-frame. A new keyframe starts when too few features
survive, chained so wall coordinates stay consistent.
"""
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

BBox = Tuple[float, float, float, float]   # (x0, y0, x1, y1), full-res pixels


class CameraMotion:

    MODES = ("auto", "tripod", "handheld")

    _WORK_WIDTH        = 480     # px; tracking runs on a downscaled grayscale copy
    _MAX_FEATURES      = 400
    _MIN_TRACKED       = 80      # start a new keyframe when fewer inliers survive
    _MIN_INLIERS       = 25      # fewer → this frame pair is invalid
    _FB_MAX_ERR        = 1.0     # forward-backward error limit, px at work scale
    _RANSAC_PX         = 2.0     # reprojection threshold, px at work scale
    _MASK_PAD          = 0.2     # pad the climber bbox by 20% of its size on each side
    _TRIPOD_MAX_MOTION = 0.001   # p90 corner motion per frame, as a fraction of the image diagonal
    _TRIPOD_MAX_DRIFT  = 0.01    # max total displacement from the first frame, fraction of the diagonal
    _MIN_VALID_RATIO   = 0.5     # below this, the clip is "uncertain"
    _LK_PARAMS = dict(
        winSize=(21, 21),
        maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
    )

    def __init__(self, mode: str = "auto"):
        if mode not in self.MODES:
            raise ValueError(f"camera mode must be one of {self.MODES}, got {mode!r}")
        self.mode = mode
        self.reset()

    def reset(self) -> None:
        """Reset per-video state. Call before processing each new video."""
        self._scale: Optional[float] = None           # work / full resolution
        self._size: Optional[Tuple[int, int]] = None  # (w, h) full resolution
        self._kf_gray: Optional[np.ndarray] = None
        self._kf_pts: Optional[np.ndarray] = None     # (N, 1, 2) work-scale feature positions in the keyframe
        self._prev_pts: Optional[np.ndarray] = None   # the same features' positions in the previous frame
        self._H_wall_to_kf = np.eye(3)
        self._H_wall_to_prev = np.eye(3)
        self._prev_frame_num: Optional[int] = None
        self._H: Dict[int, np.ndarray] = {}           # frame_num -> H_wall_to_frame (full res)
        self._motion: List[float] = []                # corner motion per frame, px (valid pairs only)
        self._max_drift = 0.0                         # max corner displacement from the first frame, px
        self._pairs = 0
        self._valid_pairs = 0

    # ── Per-frame ──────────────────────────────────────────────────────────────

    def update(self, frame: np.ndarray, frame_num: int, climber_bbox: Optional[BBox] = None) -> None:
        """Estimate H_wall_to_frame for this frame. Frames must arrive in increasing frame_num."""
        if self.mode == "tripod":
            return

        if self._scale is None:
            h, w = frame.shape[:2]
            self._size = (w, h)
            self._scale = min(1.0, self._WORK_WIDTH / w)
        gray = cv2.cvtColor(
            cv2.resize(frame, None, fx=self._scale, fy=self._scale, interpolation=cv2.INTER_AREA),
            cv2.COLOR_BGR2GRAY,
        )

        if self._kf_gray is None:
            self._set_keyframe(gray, climber_bbox, np.eye(3))
            self._record(frame_num, np.eye(3))
            return

        self._pairs += 1
        gap = max(frame_num - self._prev_frame_num, 1)
        tracked = self._track(gray)

        if tracked is None:
            # Lost track: assume no motion for this frame and restart from here.
            H = self._H_wall_to_prev
            self._set_keyframe(gray, climber_bbox, H)
        else:
            H_kf_to_cur, n_inliers = tracked
            H = H_kf_to_cur @ self._H_wall_to_kf
            self._valid_pairs += 1
            self._motion.append(self._corner_motion(H @ np.linalg.inv(self._H_wall_to_prev)) / gap)
            self._max_drift = max(self._max_drift, self._corner_motion(H))
            if n_inliers < self._MIN_TRACKED:
                self._set_keyframe(gray, climber_bbox, H)

        self._record(frame_num, H)

    def wall_to_frame(self, frame_num: int) -> Optional[np.ndarray]:
        """H_wall_to_frame for a tracked frame (identity when the clip is treated as tripod)."""
        if self.summary()["used"] == "tripod":
            return np.eye(3)
        return self._H.get(frame_num)

    # ── Clip-level ─────────────────────────────────────────────────────────────

    def summary(self) -> dict:
        """{requested, detected, used, p90_motion_px, max_drift_px, valid_pair_ratio} for the clip so far.

        Tripod needs both low per-frame jitter and low total drift, so a slow steady pan
        (small per-frame motion, large accumulated motion) is still detected as handheld.
        """
        if self.mode == "tripod":
            return {"requested": "tripod", "detected": None, "used": "tripod",
                    "p90_motion_px": None, "max_drift_px": None, "valid_pair_ratio": None}

        ratio = self._valid_pairs / self._pairs if self._pairs else 0.0
        p90 = float(np.percentile(self._motion, 90)) if self._motion else None
        if ratio < self._MIN_VALID_RATIO or p90 is None:
            detected = "uncertain"
        else:
            diag = float(np.hypot(*self._size))
            still = p90 < self._TRIPOD_MAX_MOTION * diag and self._max_drift < self._TRIPOD_MAX_DRIFT * diag
            detected = "tripod" if still else "handheld"

        if self.mode == "auto":
            used = "handheld" if detected == "handheld" else "tripod"
        else:
            used = self.mode
        return {"requested": self.mode, "detected": detected, "used": used,
                "p90_motion_px": p90, "max_drift_px": self._max_drift, "valid_pair_ratio": ratio}

    # ── Internals ──────────────────────────────────────────────────────────────

    def _record(self, frame_num: int, H: np.ndarray) -> None:
        self._H[frame_num] = H
        self._H_wall_to_prev = H
        self._prev_frame_num = frame_num

    def _set_keyframe(self, gray: np.ndarray, climber_bbox: Optional[BBox], H_wall_to_frame: np.ndarray) -> None:
        mask = np.full(gray.shape, 255, dtype=np.uint8)
        if climber_bbox is not None:
            x0, y0, x1, y1 = (v * self._scale for v in climber_bbox)
            px, py = (x1 - x0) * self._MASK_PAD, (y1 - y0) * self._MASK_PAD
            mask[max(int(y0 - py), 0):max(int(y1 + py), 0), max(int(x0 - px), 0):max(int(x1 + px), 0)] = 0
        pts = cv2.goodFeaturesToTrack(gray, self._MAX_FEATURES, qualityLevel=0.01, minDistance=8, mask=mask)
        self._kf_gray = gray
        self._kf_pts = pts if pts is not None else np.empty((0, 1, 2), dtype=np.float32)
        self._prev_pts = self._kf_pts.copy()
        self._H_wall_to_kf = H_wall_to_frame

    def _track(self, gray: np.ndarray) -> Optional[Tuple[np.ndarray, int]]:
        """Track keyframe features into `gray`. Returns (H_kf_to_frame full-res, n_inliers) or None."""
        if len(self._kf_pts) < self._MIN_INLIERS:
            return None
        flags = cv2.OPTFLOW_USE_INITIAL_FLOW
        cur, st_fwd, _ = cv2.calcOpticalFlowPyrLK(
            self._kf_gray, gray, self._kf_pts, self._prev_pts.copy(), flags=flags, **self._LK_PARAMS)
        back, st_bwd, _ = cv2.calcOpticalFlowPyrLK(
            gray, self._kf_gray, cur, self._kf_pts.copy(), flags=flags, **self._LK_PARAMS)
        fb_err = np.linalg.norm((self._kf_pts - back).reshape(-1, 2), axis=1)
        ok = (st_fwd.ravel() == 1) & (st_bwd.ravel() == 1) & (fb_err < self._FB_MAX_ERR)
        if ok.sum() < self._MIN_INLIERS:
            return None

        src = self._kf_pts[ok].reshape(-1, 2) / self._scale
        dst = cur[ok].reshape(-1, 2) / self._scale
        H, inlier_mask = cv2.findHomography(src, dst, cv2.RANSAC, self._RANSAC_PX / self._scale)
        if H is None:
            return None
        inliers = inlier_mask.ravel().astype(bool)
        if inliers.sum() < self._MIN_INLIERS:
            return None

        # Keep only RANSAC inliers: features on the climber or badly tracked ones drop out.
        keep = np.flatnonzero(ok)[inliers]
        self._kf_pts = self._kf_pts[keep]
        self._prev_pts = cur[keep]
        return H, int(inliers.sum())

    def _corner_motion(self, M: np.ndarray) -> float:
        """Mean displacement (px) of the image corners under M."""
        w, h = self._size
        corners = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float64).reshape(-1, 1, 2)
        moved = cv2.perspectiveTransform(corners, M)
        return float(np.linalg.norm((moved - corners).reshape(-1, 2), axis=1).mean())
