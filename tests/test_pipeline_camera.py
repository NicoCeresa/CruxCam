"""VideoProcessor + CameraMotion end to end on synthetic video.

MediaPipe can't detect the synthetic blob as a person, so a stub analyzer stands in for
PoseAnalyzer (that's what constructor injection into VideoProcessor is for).
"""
import numpy as np
import pytest

from core.camera_motion import CameraMotion
from core.pose_analyzer import PoseAnalyzer
from core.video_processor import FrameAnalyzer, VideoProcessor
from tests import synthetic as syn

N = 40


class StubAnalyzer:
    """Reports every frame as a detected, good pose with a fixed climber bbox."""

    def __init__(self, bbox=(250.0, 150.0, 390.0, 330.0)):
        self.climber_bbox = bbox
        self.plane_data = None
        self.com_3d = None

    def reset(self):
        pass

    def close(self):
        pass

    def analyze_frame(self, img, run_inference=True):
        return True, (170.0, 170.0), np.zeros((33, 3), dtype=np.float32)


def test_analyzers_satisfy_protocol():
    """Keeps the stub in step with what VideoProcessor actually uses."""
    real = PoseAnalyzer()
    try:
        assert isinstance(real, FrameAnalyzer)
    finally:
        real.close()
    assert isinstance(StubAnalyzer(), FrameAnalyzer)


@pytest.mark.parametrize("motion, expected", [
    (syn.static(N), "tripod"),
    (syn.pan(N, dx=3.0), "handheld"),
])
def test_processor_reports_camera(tmp_path, motion, expected):
    clip = syn.make_clip(tmp_path / "clip.mp4", motion)
    proc = VideoProcessor(pose_analyzer=StubAnalyzer(), camera_motion=CameraMotion("auto"))
    result = proc.process_video(str(clip.path), str(tmp_path / "out.mp4"), frame_skip=2)

    assert result.camera["detected"] == expected
    assert result.camera["used"] == expected
    assert len(result.pose_data_3d) == N // 2


def test_processor_without_camera_motion(tmp_path):
    clip = syn.make_clip(tmp_path / "clip.mp4", syn.static(N))
    result = VideoProcessor(pose_analyzer=StubAnalyzer()).process_video(
        str(clip.path), str(tmp_path / "out.mp4"))
    assert result.camera is None
