import json

import numpy as np

from api.jobs import serialize_result
from core.results import AnalysisResult, FrameResult


def _frame(frame, with_plane=True):
    return FrameResult(
        frame_num=frame,
        world_lms=np.full((33, 3), 0.5, dtype=np.float32),
        is_good=True,
        com=(0.1, 0.2, 0.3),
        r_angle=120.0,
        l_angle=95.0,
        hip_plane_dist=0.8 if with_plane else None,
        plane_centroid=(0.0, 0.1, 0.2) if with_plane else None,
        plane_normal=(0.0, 0.0, 1.0) if with_plane else None,
    )


def test_serialize_is_json_and_positional():
    result = AnalysisResult(
        good_frames=2, bad_frames=1, efficiency=66.7, fps=30,
        processed_video_path="/tmp/x.mp4",
        pose_data_3d=[_frame(0), _frame(2, with_plane=False)],
    )
    out = json.loads(json.dumps(serialize_result(result)))

    assert out["good_frames"] == 2 and out["fps"] == 30
    assert "processed_video_path" not in out   # server path never goes to the client
    first, second = out["pose_data_3d"]
    assert len(first) == 9
    assert first[0] == 0
    assert len(first[1]) == 33 and len(first[1][0]) == 3
    assert first[2] is True
    assert first[4:7] == [120.0, 95.0, 0.8]
    assert first[8] == [0.0, 0.0, 1.0]
    assert second[6:9] == [None, None, None]


def test_serialize_rounds_floats():
    frame = _frame(0)
    frame.world_lms[0] = [0.123456789, -1.987654321, 2.5]
    frame.r_angle = 123.456789
    result = AnalysisResult(good_frames=1, bad_frames=0, efficiency=100.0, pose_data_3d=[frame])
    entry = serialize_result(result)["pose_data_3d"][0]
    assert entry[1][0] == [0.1235, -1.9877, 2.5]
    assert entry[4] == 123.4568


def test_serialize_without_pose_data():
    result = AnalysisResult(good_frames=0, bad_frames=0, efficiency=0.0, pose_data_3d=None)
    assert serialize_result(result)["pose_data_3d"] is None
