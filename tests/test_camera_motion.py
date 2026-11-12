"""CameraMotion against synthetic clips with known camera motion."""
import cv2
import numpy as np
import pytest

from core.camera_motion import CameraMotion
from tests import synthetic as syn

N = 60
CORNERS = np.array(
    [[0, 0], [syn.FRAME_W, 0], [syn.FRAME_W, syn.FRAME_H], [0, syn.FRAME_H]], dtype=np.float64
).reshape(-1, 1, 2)


def _run(frames, mode="auto", step=1, bboxes=None):
    cm = CameraMotion(mode)
    for t in range(0, len(frames), step):
        cm.update(frames[t], t, bboxes[t] if bboxes else None)
    return cm


def _corner_error(cm, clip, t):
    """Mean px error of frame-0 corners mapped into frame t: estimated vs ground truth."""
    true = clip.H[t] @ np.linalg.inv(clip.H[0])
    est = cm.wall_to_frame(t)
    a = cv2.perspectiveTransform(CORNERS, true)
    b = cv2.perspectiveTransform(CORNERS, est)
    return float(np.linalg.norm((a - b).reshape(-1, 2), axis=1).mean())


def _clip(tmp_path, name, motion, **kw):
    clip = syn.make_clip(tmp_path / f"{name}.mp4", motion, **kw)
    return clip, syn.read_frames(clip.path)


def test_static_is_tripod(tmp_path):
    _, frames = _clip(tmp_path, "static", syn.static(N))
    s = _run(frames).summary()
    assert s["detected"] == "tripod" and s["used"] == "tripod"
    assert s["p90_motion_px"] < 0.5
    assert s["valid_pair_ratio"] == 1.0


def test_static_with_moving_climber_is_tripod(tmp_path):
    """The blob has texture and moves; RANSAC must treat it as an outlier even unmasked."""
    cx, cy = syn.WALL_W / 2, syn.WALL_H / 2
    path = [(cx - 100 + 4 * t, cy + 50 - 2 * t) for t in range(N)]
    _, frames = _clip(tmp_path, "blob", syn.static(N), blob_path=path)
    assert _run(frames).summary()["detected"] == "tripod"


@pytest.mark.parametrize("name, motion", [
    ("pan",   syn.pan(N, dx=3.0, dy=1.0)),
    ("shake", syn.shake(N, amp=4.0)),
    ("zoom",  syn.zoom(N, rate=0.003)),
])
def test_moving_camera_is_handheld_and_recovered(tmp_path, name, motion):
    clip, frames = _clip(tmp_path, name, motion)
    cm = _run(frames)
    s = cm.summary()
    assert s["detected"] == "handheld" and s["used"] == "handheld"
    assert max(_corner_error(cm, clip, t) for t in range(N)) < 1.5


def test_slow_drift_is_handheld(tmp_path):
    """0.3 px/frame is under the per-frame threshold, but 36 px of total drift is not a tripod."""
    _, frames = _clip(tmp_path, "slow_pan", syn.pan(120, dx=0.3))
    s = _run(frames).summary()
    assert s["p90_motion_px"] < 0.8
    assert s["detected"] == "handheld"


def test_frame_skip_still_recovers(tmp_path):
    clip, frames = _clip(tmp_path, "pan_skip", syn.pan(N, dx=3.0))
    cm = _run(frames, step=2)
    assert cm.summary()["detected"] == "handheld"
    assert max(_corner_error(cm, clip, t) for t in range(0, N, 2)) < 1.5


def test_long_pan_drift_is_bounded(tmp_path):
    """300 frames, 300 px of pan: keyframes refresh and drift stays under 2% of the path."""
    n = 300
    clip, frames = _clip(tmp_path, "long_pan", syn.pan(n, dx=1.0))
    cm = _run(frames)
    assert _corner_error(cm, clip, n - 1) < 0.02 * 300


def test_forced_tripod_skips_tracking(tmp_path):
    _, frames = _clip(tmp_path, "pan_forced", syn.pan(N, dx=3.0))
    cm = _run(frames, mode="tripod")
    s = cm.summary()
    assert s["used"] == "tripod" and s["detected"] is None
    assert np.array_equal(cm.wall_to_frame(10), np.eye(3))


def test_textureless_is_uncertain():
    frames = [np.full((syn.FRAME_H, syn.FRAME_W, 3), 120, dtype=np.uint8) for _ in range(N)]
    s = _run(frames).summary()
    assert s["detected"] == "uncertain" and s["used"] == "tripod"


def test_invalid_mode_rejected():
    with pytest.raises(ValueError):
        CameraMotion("drone")


def test_summary_is_cached_until_next_update(tmp_path):
    # Still for 10 frames, then the camera pans: the answer must change once updated.
    _, frames = _clip(tmp_path, "cache", syn.static(10) + syn.pan(15, dx=3.0))
    cm = _run(frames[:10])
    first = cm.summary()
    assert first["detected"] == "tripod"
    first["used"] = "tampered"                       # callers get a copy
    assert cm.summary()["used"] == "tripod"
    for t in range(10, len(frames)):
        cm.update(frames[t], t)
    assert cm.summary()["detected"] == "handheld"    # recomputed after update
