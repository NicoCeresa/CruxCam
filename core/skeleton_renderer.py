import subprocess
from pathlib import Path
from typing import List

import cv2
import numpy as np

CONNECTIONS = [
    (11, 12),
    (11, 13), (13, 15),
    (12, 14), (14, 16),
    (11, 23), (12, 24),
    (23, 24),
    (23, 25), (25, 27), (27, 29), (29, 31),
    (24, 26), (26, 28), (28, 30), (30, 32),
    (0, 11), (0, 12),
]

BG    = (43, 26, 13)    # BGR: #0D1A2B
GREEN = (80, 255, 122)  # BGR
RED   = (50, 50, 255)   # BGR
BLUE  = (255, 127, 0)   # BGR: CoM


def render_skeleton_video(pose_data: List, source_fps: int, output_path: str) -> None:
    if not pose_data:
        raise ValueError("No pose data to render")

    stride = pose_data[1][0] - pose_data[0][0] if len(pose_data) > 1 else 1
    out_fps = max(1, source_fps // stride)

    W = H = 720

    all_lms = [np.array(lms) for _, lms, _, _ in pose_data if lms is not None]
    if not all_lms:
        raise ValueError("No landmark data in pose entries")

    pts = np.concatenate(all_lms, axis=0)
    # Match Three.js coordinate flip: x → -x, y → -y
    xs, ys = -pts[:, 0], -pts[:, 1]

    margin = 0.12
    scale = min(
        W * (1 - 2 * margin) / max(xs.max() - xs.min(), 1e-6),
        H * (1 - 2 * margin) / max(ys.max() - ys.min(), 1e-6),
    )
    x_off = W * margin - xs.min() * scale
    y_off = H * margin - ys.min() * scale

    def to_px(x, y):
        return int(-x * scale + x_off), int(-y * scale + y_off)

    tmp_raw = output_path.replace('.mp4', '_skel_raw.mp4')
    out = cv2.VideoWriter(tmp_raw, cv2.VideoWriter_fourcc(*'mp4v'), out_fps, (W, H))

    for _, lms, is_good, com in pose_data:
        frame = np.full((H, W, 3), BG, dtype=np.uint8)

        if lms is not None:
            lms = np.array(lms)
            color = GREEN if is_good else RED

            for a, b in CONNECTIONS:
                if a < len(lms) and b < len(lms):
                    cv2.line(frame, to_px(lms[a][0], lms[a][1]),
                             to_px(lms[b][0], lms[b][1]), color, 2, cv2.LINE_AA)

            for pt in lms:
                cv2.circle(frame, to_px(pt[0], pt[1]), 4, color, -1, cv2.LINE_AA)

            if com is not None:
                cv2.circle(frame, to_px(com[0], com[1]), 12, BLUE, -1, cv2.LINE_AA)

        out.write(frame)

    out.release()

    subprocess.run(
        ['ffmpeg', '-y', '-i', tmp_raw, '-c:v', 'libx264', '-preset', 'fast', '-crf', '23', output_path],
        check=True, capture_output=True,
    )
    Path(tmp_raw).unlink(missing_ok=True)
