import pytest

from core.pose_analyzer import PoseAnalyzer


@pytest.mark.parametrize("alpha", [0.1, 0.2])
@pytest.mark.parametrize("steps", [1, 2, 5])
def test_ema_weight_matches_repeated_updates(alpha, steps):
    """One update covering `steps` frames == `steps` per-frame updates toward the same value."""
    x, target = 0.0, 1.0
    for _ in range(steps):
        x = alpha * target + (1 - alpha) * x
    a = PoseAnalyzer._ema_weight(alpha, steps)
    assert a * target + (1 - a) * 0.0 == pytest.approx(x)
