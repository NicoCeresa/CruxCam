"""Non-integer frame rates (29.97 fps phone video) must not be rounded.

Rounding 29.97 to 29 made a trimmed result video start ~2 s after its pose data
(at a 1-minute trim start) and made the frontend's time → frame mapping drift.
"""
import cv2
import numpy as np
import pytest

from api.previews import read_video_info
from core.video_processor import VideoProcessor
from tests import synthetic as syn
from tests.test_pipeline_camera import StubAnalyzer

NTSC = 30000 / 1001   # 29.97...
START, END = 150, 180


@pytest.fixture
def clip_2997(tmp_path):
    # Panning camera, so every frame is distinguishable from its neighbours.
    return syn.make_clip(tmp_path / "ntsc.mp4", syn.pan(200, dx=3.0), fps=NTSC)


def test_video_info_keeps_fractional_fps(clip_2997):
    assert read_video_info(clip_2997.path)["fps"] == pytest.approx(NTSC, abs=1e-3)


def test_trimmed_video_starts_at_requested_frame(clip_2997, tmp_path):
    out = tmp_path / "out.mp4"
    result = VideoProcessor(StubAnalyzer()).process_video(
        str(clip_2997.path), str(out), start_frame=START, end_frame=END)
    assert result.fps == pytest.approx(NTSC, abs=1e-3)

    cap = cv2.VideoCapture(str(out))
    ok, first = cap.read()
    cap.release()
    assert ok

    source = syn.read_frames(clip_2997.path)
    diffs = {i: np.abs(source[i].astype(int) - first.astype(int)).mean() for i in range(START - 15, START + 15)}
    assert min(diffs, key=diffs.get) == START
