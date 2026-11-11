"""Uploaded-but-not-yet-submitted videos: temp files, 1080p inference copies, thumbnails, cleanup."""
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

import cv2


class VideoReadError(Exception):
    """The file could not be opened or decoded as a video."""


def read_video_info(path: Path) -> dict:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise VideoReadError("Could not read video file")
    fps          = cap.get(cv2.CAP_PROP_FPS)   # keep fractional: phone video is often 29.97 / 59.94
    width        = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height       = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return {
        "fps": fps,
        "width": width,
        "height": height,
        "total_frames": total_frames,
        "duration": total_frames / max(fps, 1),
    }


class PreviewStore:
    """In-process registry of preview files, keyed by preview_id."""

    _PATTERNS = ("cruxcam_upload_*", "cruxcam_output_*", "cruxcam_preview_*", "cruxcam_scaled_*")

    def __init__(self, tmp: Path, ttl: int):
        self._tmp = tmp
        self._ttl = ttl
        self._previews: Dict[str, Path] = {}
        self._scaled:   Dict[str, Path] = {}   # preview_id -> 1080p-scaled copy for inference

    def new_temp(self, prefix: str, suffix: str) -> Path:
        fd, tmp = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=self._tmp)
        os.close(fd)
        return Path(tmp)

    def create(self, suffix: str, write: Callable[[Path], None]) -> dict:
        """Register a new preview whose contents `write` puts at the given path.

        Returns the video info plus preview_id. Raises VideoReadError for unreadable video.
        """
        preview_id = str(uuid.uuid4())
        path = self.new_temp("cruxcam_preview_", suffix)
        self._previews[preview_id] = path
        try:
            write(path)
            info = read_video_info(path)
            self._scale_for_inference(path, preview_id)
        except Exception:
            path.unlink(missing_ok=True)
            self._previews.pop(preview_id, None)
            raise
        return {**info, "preview_id": preview_id}

    def get(self, preview_id: str) -> Optional[Path]:
        path = self._previews.get(preview_id)
        return path if path and path.exists() else None

    def take(self, preview_id: str) -> Tuple[Optional[Path], Optional[Path]]:
        """Remove a preview from the registry, returning (preview_path, scaled_path)."""
        return self._previews.pop(preview_id, None), self._scaled.pop(preview_id, None)

    def frame_jpeg(self, preview_id: str, n: int) -> Optional[bytes]:
        """JPEG of frame n, or None if the preview doesn't exist. Raises VideoReadError if unreadable."""
        path = self.get(preview_id)
        if path is None:
            return None
        cap = cv2.VideoCapture(str(path))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.set(cv2.CAP_PROP_POS_FRAMES, min(n, total - 1))
        ok, frame = cap.read()
        cap.release()
        if not ok:
            raise VideoReadError("Could not read frame")
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        return buf.tobytes()

    def cleanup(self) -> None:
        """Delete temp files older than the TTL and forget previews whose files are gone."""
        cutoff = time.time() - self._ttl
        for pattern in self._PATTERNS:
            for path in self._tmp.glob(pattern):
                try:
                    if path.is_file() and path.stat().st_mtime < cutoff:
                        path.unlink(missing_ok=True)
                except OSError:
                    pass
        for registry in (self._previews, self._scaled):
            for pid in [k for k, v in registry.items() if not v.exists()]:
                registry.pop(pid, None)

    def _scale_for_inference(self, path: Path, preview_id: str) -> None:
        """If path is taller than 1080p, create a scaled copy and register it under preview_id."""
        cap = cv2.VideoCapture(str(path))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        if height <= 1080:
            return
        ffmpeg_bin = shutil.which('ffmpeg') or 'ffmpeg'
        tmp_path = self.new_temp("cruxcam_scaled_", ".mp4")
        try:
            subprocess.run(
                [ffmpeg_bin, '-y', '-i', str(path), '-vf', 'scale=-2:1080',
                 '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '18', str(tmp_path)],
                check=True, capture_output=True,
            )
            self._scaled[preview_id] = tmp_path
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise
