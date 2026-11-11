"""Pins the current pipeline output on a real clip so refactors can't silently change results.

Regenerate after an intentional change with:  pytest --update-golden
"""
import json
from pathlib import Path

import numpy as np
import pytest

from api.jobs import serialize_result
from core.pose_analyzer import PoseAnalyzer
from core.video_processor import VideoProcessor

GOLDEN = Path(__file__).parent / "golden" / "tomoa_outside_820_910.json"
FLOAT_TOL = 1e-3


def _summarize(result) -> dict:
    """Compact, comparable view of a result (world landmarks reduced to a per-frame sum)."""
    data = serialize_result(result)
    entries = []
    for e in data["pose_data_3d"] or []:
        entries.append({
            "frame":    e[0],
            "lms_sum":  float(np.sum(e[1])) if e[1] is not None else None,
            "is_good":  e[2],
            "com":      e[3],
            "r_angle":  e[4],
            "l_angle":  e[5],
            "hip_dist": e[6],
            "centroid": e[7],
            "normal":   e[8],
        })
    return {
        "good_frames": data["good_frames"],
        "bad_frames":  data["bad_frames"],
        "efficiency":  data["efficiency"],
        "fps":         data["fps"],
        "entries":     entries,
    }


def _assert_close(actual, expected, path="root"):
    if isinstance(expected, dict):
        assert actual.keys() == expected.keys(), path
        for k in expected:
            _assert_close(actual[k], expected[k], f"{path}.{k}")
    elif isinstance(expected, list):
        assert len(actual) == len(expected), path
        for i, (a, b) in enumerate(zip(actual, expected)):
            _assert_close(a, b, f"{path}[{i}]")
    elif isinstance(expected, float):
        assert actual == pytest.approx(expected, abs=FLOAT_TOL), path
    else:
        assert actual == expected, path


def test_pipeline_matches_golden(sample_clip, tmp_path, update_golden):
    processor = VideoProcessor(PoseAnalyzer(angle_threshold=90))
    try:
        result = processor.process_video(
            str(sample_clip), str(tmp_path / "out.mp4"),
            start_frame=820, end_frame=910, frame_skip=2,
        )
    finally:
        processor.close()
    summary = json.loads(json.dumps(_summarize(result)))   # tuples → lists, as the API sends them

    if update_golden or not GOLDEN.exists():
        GOLDEN.parent.mkdir(exist_ok=True)
        GOLDEN.write_text(json.dumps(summary, indent=1))
        pytest.skip(f"golden written to {GOLDEN}")

    _assert_close(summary, json.loads(GOLDEN.read_text()))
