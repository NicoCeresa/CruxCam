"""Job assembly and execution (run_job) without the API."""
from api.jobs import build_processor, run_job
from core.camera_motion import CameraMotion
from tests import synthetic as syn


def test_build_processor_without_camera_mode():
    proc = build_processor(angle_threshold=80)
    try:
        assert proc.camera_motion is None
        assert proc.pose_analyzer.angle_threshold == 80
    finally:
        proc.close()


def test_build_processor_with_camera_mode():
    proc = build_processor(angle_threshold=90, camera_mode="handheld")
    try:
        assert isinstance(proc.camera_motion, CameraMotion)
        assert proc.camera_motion.mode == "handheld"
    finally:
        proc.close()


def _run(tmp_path, input_path):
    states = []
    run_job("j", str(input_path), str(tmp_path / "out.mp4"), 90, 0, None, 2,
            lambda _id, state: states.append(state))
    return states


def test_run_job_completes_and_cleans_up(tmp_path):
    # No person in a synthetic wall clip: the job should still complete, with no pose data.
    clip = syn.make_clip(tmp_path / "in.mp4", syn.static(20))
    states = _run(tmp_path, clip.path)

    assert states[-1]["status"] == "complete"
    assert states[-1]["result"]["pose_data_3d"] is None
    assert any(s["status"] == "processing" for s in states)
    assert not clip.path.exists()   # input is deleted once processed


def test_run_job_missing_input_fails(tmp_path):
    states = _run(tmp_path, tmp_path / "nope.mp4")
    assert states[-1]["status"] == "failed"
    assert str(tmp_path) not in states[-1]["error"]   # no server paths in client-facing errors


def test_run_job_unreadable_video_fails_generically(tmp_path):
    bad = tmp_path / "corrupt.mp4"
    bad.write_bytes(b"not a video")
    states = _run(tmp_path, bad)
    assert states[-1] == {"status": "failed", "error": "Processing failed — the video could not be analyzed"}
    assert not bad.exists()


def test_run_job_keeps_video_path_server_side(tmp_path):
    clip = syn.make_clip(tmp_path / "in.mp4", syn.static(20))
    final = _run(tmp_path, clip.path)[-1]
    assert final["video_path"] == str(tmp_path / "out.mp4")
    assert "processed_video_path" not in final["result"]
