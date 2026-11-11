"""Synthetic climbing-wall videos with known camera motion, for testing camera-motion code.

A textured "wall" image (larger than the frame) is warped into each frame by a known
homography H_t (wall coords → frame pixels). An optional textured blob stands in for the
climber; it is drawn in wall coordinates, so its wall-relative path is known exactly.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

FRAME_W, FRAME_H = 640, 480
WALL_W,  WALL_H  = FRAME_W * 2, FRAME_H * 2
BLOB_RADIUS = 40


@dataclass
class SyntheticClip:
    path: Path
    fps: int
    H: List[np.ndarray]                                   # per frame, wall → frame pixels
    blob_path: Optional[List[Tuple[float, float]]] = None  # per frame, wall coords


def make_wall(seed: int = 0) -> np.ndarray:
    """Grey noise base with random coloured ellipses as holds — plenty of corners for LK."""
    rng = np.random.default_rng(seed)
    wall = rng.integers(90, 140, size=(WALL_H, WALL_W, 1), dtype=np.uint8).repeat(3, axis=2)
    wall = cv2.GaussianBlur(wall, (5, 5), 0)
    for _ in range(WALL_W * WALL_H // 4000):
        center = (int(rng.integers(0, WALL_W)), int(rng.integers(0, WALL_H)))
        axes   = (int(rng.integers(6, 22)), int(rng.integers(6, 22)))
        color  = tuple(int(c) for c in rng.integers(0, 256, 3))
        cv2.ellipse(wall, center, axes, float(rng.uniform(0, 180)), 0, 360, color, -1, cv2.LINE_AA)
    return wall


# ── Camera motions: each returns per-frame transforms M_t in frame-pixel space ───

def static(n: int) -> List[np.ndarray]:
    return [np.eye(3) for _ in range(n)]


def pan(n: int, dx: float, dy: float = 0.0) -> List[np.ndarray]:
    """Camera pans by (dx, dy) px/frame, so wall content moves by (-dx, -dy)."""
    return [_translation(-dx * t, -dy * t) for t in range(n)]


def shake(n: int, amp: float = 4.0, seed: int = 0) -> List[np.ndarray]:
    """Smoothed random translation plus small rotation — a handheld wobble."""
    rng = np.random.default_rng(seed)
    kernel = np.ones(5) / 5
    tx  = np.convolve(rng.normal(0, amp, n), kernel, mode="same")
    ty  = np.convolve(rng.normal(0, amp, n), kernel, mode="same")
    rot = np.convolve(rng.normal(0, 0.5, n), kernel, mode="same")   # degrees
    cx, cy = FRAME_W / 2, FRAME_H / 2
    return [
        _translation(tx[t], ty[t]) @ np.vstack([cv2.getRotationMatrix2D((cx, cy), rot[t], 1.0), [0, 0, 1]])
        for t in range(n)
    ]


def zoom(n: int, rate: float = 0.003) -> List[np.ndarray]:
    """Zoom in about the frame centre by `rate` per frame."""
    cx, cy = FRAME_W / 2, FRAME_H / 2
    return [np.vstack([cv2.getRotationMatrix2D((cx, cy), 0, 1 + rate * t), [0, 0, 1]]) for t in range(n)]


def _translation(tx: float, ty: float) -> np.ndarray:
    return np.array([[1, 0, tx], [0, 1, ty], [0, 0, 1]], dtype=np.float64)


# ── Clip writer ────────────────────────────────────────────────────────────────

def make_clip(
    path: Path,
    motion: List[np.ndarray],
    blob_path: Optional[List[Tuple[float, float]]] = None,
    seed: int = 0,
    fps: int = 30,
) -> SyntheticClip:
    """Render and write an mp4. `blob_path`, if given, needs one wall-coord point per frame."""
    wall = make_wall(seed)
    blob = _make_blob_texture(seed + 1)
    # Centre the frame on the wall, then apply the camera motion in frame space.
    base = _translation(-(WALL_W - FRAME_W) / 2, -(WALL_H - FRAME_H) / 2)
    H = [m @ base for m in motion]

    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (FRAME_W, FRAME_H))
    try:
        for t, h in enumerate(H):
            canvas = wall
            if blob_path is not None:
                canvas = wall.copy()
                _paste_blob(canvas, blob, blob_path[t])
            writer.write(cv2.warpPerspective(canvas, h, (FRAME_W, FRAME_H), flags=cv2.INTER_LINEAR))
    finally:
        writer.release()
    return SyntheticClip(path=path, fps=fps, H=H, blob_path=blob_path)


def _make_blob_texture(seed: int) -> np.ndarray:
    """Textured disc (BGRA) so the 'climber' has trackable features that move with it."""
    rng = np.random.default_rng(seed)
    size = BLOB_RADIUS * 2
    tex = np.zeros((size, size, 4), dtype=np.uint8)
    tex[..., :3] = rng.integers(0, 256, size=(size, size, 3), dtype=np.uint8)
    tex[..., :3] = cv2.GaussianBlur(tex[..., :3], (3, 3), 0)
    tex[..., 2] = np.maximum(tex[..., 2], 160)   # reddish, distinct from the wall
    mask = np.zeros((size, size), dtype=np.uint8)   # separate array: cv2 can't draw into a channel slice
    cv2.circle(mask, (BLOB_RADIUS, BLOB_RADIUS), BLOB_RADIUS, 255, -1)
    tex[..., 3] = mask
    return tex


def _paste_blob(canvas: np.ndarray, blob: np.ndarray, center: Tuple[float, float]) -> None:
    x0, y0 = int(round(center[0])) - BLOB_RADIUS, int(round(center[1])) - BLOB_RADIUS
    region = canvas[y0:y0 + blob.shape[0], x0:x0 + blob.shape[1]]
    alpha  = blob[: region.shape[0], : region.shape[1], 3:4] / 255.0
    region[:] = (alpha * blob[: region.shape[0], : region.shape[1], :3] + (1 - alpha) * region).astype(np.uint8)


def read_frames(path: Path) -> List[np.ndarray]:
    cap = cv2.VideoCapture(str(path))
    frames = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(frame)
    cap.release()
    return frames
