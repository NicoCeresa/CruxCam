"""All CRUXCAM_* settings, read once from the environment."""
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

_PROJECT_ROOT = Path(__file__).parent.parent


@dataclass(frozen=True)
class Settings:
    allowed_origins:      List[str]
    allowed_origin_regex: Optional[str]
    tmp:                  Path
    file_ttl:             int     # seconds before temp files and job state expire
    max_upload_mb:        int
    rate_limit:           int     # uploads per IP per minute
    sample_path:          Path
    redis_url:            str

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


def load_settings() -> Settings:
    return Settings(
        allowed_origins      = os.environ.get("CRUXCAM_ALLOWED_ORIGINS", "http://localhost:5173").split(","),
        allowed_origin_regex = os.environ.get("CRUXCAM_ALLOWED_ORIGIN_REGEX", None),
        tmp                  = Path(tempfile.gettempdir()),
        file_ttl             = int(os.environ.get("CRUXCAM_FILE_TTL", 3600)),
        max_upload_mb        = int(os.environ.get("CRUXCAM_MAX_UPLOAD_MB", 500)),
        rate_limit           = int(os.environ.get("CRUXCAM_RATE_LIMIT", 10)),
        sample_path          = _PROJECT_ROOT / os.environ.get("CRUXCAM_SAMPLE_PATH", "inputs/tomoa_outside.mp4"),
        redis_url            = os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    )
