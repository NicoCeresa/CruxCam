from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
SAMPLE_CLIP  = PROJECT_ROOT / "inputs" / "tomoa_outside.mp4"


def pytest_addoption(parser):
    parser.addoption(
        "--update-golden", action="store_true", default=False,
        help="Rewrite golden files in tests/golden/ from the current pipeline output.",
    )


@pytest.fixture
def update_golden(request) -> bool:
    return request.config.getoption("--update-golden")


@pytest.fixture
def sample_clip() -> Path:
    # inputs/ is gitignored, so tests that need real footage skip in CI.
    if not SAMPLE_CLIP.exists():
        pytest.skip(f"sample clip not found: {SAMPLE_CLIP}")
    return SAMPLE_CLIP
