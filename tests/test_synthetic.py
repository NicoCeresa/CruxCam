"""Sanity checks that the synthetic generator produces the motion it claims to."""
import cv2
import numpy as np

from tests import synthetic as syn

N = 30


def _gray(frame):
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)


def test_frame_count_and_size(tmp_path):
    clip = syn.make_clip(tmp_path / "static.mp4", syn.static(N))
    frames = syn.read_frames(clip.path)
    assert len(frames) == N
    assert frames[0].shape == (syn.FRAME_H, syn.FRAME_W, 3)


def test_static_clip_is_still(tmp_path):
    frames = syn.read_frames(syn.make_clip(tmp_path / "static.mp4", syn.static(N)).path)
    diffs = [np.abs(_gray(a) - _gray(b)).mean() for a, b in zip(frames, frames[1:])]
    assert max(diffs) < 2.0   # compression noise only


def test_pan_shift_matches_ground_truth(tmp_path):
    frames = syn.read_frames(syn.make_clip(tmp_path / "pan.mp4", syn.pan(N, dx=3.0)).path)
    for a, b in zip(frames[:10], frames[1:11]):
        (sx, sy), _ = cv2.phaseCorrelate(_gray(a), _gray(b))
        assert abs(sx - (-3.0)) < 0.3   # camera pans right → content moves left
        assert abs(sy) < 0.3


def test_blob_follows_wall_path(tmp_path):
    cx, cy = syn.WALL_W / 2, syn.WALL_H / 2
    blob_path = [(cx + 4 * t, cy) for t in range(N)]
    clip = syn.make_clip(tmp_path / "blob.mp4", syn.static(N), blob_path=blob_path)
    plain = syn.read_frames(syn.make_clip(tmp_path / "plain.mp4", syn.static(N)).path)
    frames = syn.read_frames(clip.path)

    for t in (0, N - 1):
        # Project the blob's wall position into the frame and check pixels differ there.
        x, y, w = clip.H[t] @ np.array([*blob_path[t], 1.0])
        px, py = int(x / w), int(y / w)
        patch = (slice(py - 10, py + 10), slice(px - 10, px + 10))
        assert np.abs(_gray(frames[t])[patch] - _gray(plain[t])[patch]).mean() > 20
