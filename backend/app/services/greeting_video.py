"""Greeting video storage: save upload, normalize to MP4 for Telegram."""

from __future__ import annotations

import asyncio
import logging
import shutil
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

MEDIA_VIDEOS = Path(__file__).resolve().parents[2] / "media" / "videos"
MEDIA_VIDEOS.mkdir(parents=True, exist_ok=True)

# Telegram Bot API rejects multipart uploads above 50 MB.
MAX_VIDEO_BYTES = 50 * 1024 * 1024
FFMPEG_TIMEOUT_SEC = 180

VIDEO_EXTENSIONS = {
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
    "video/3gpp": ".3gp",
    "video/x-m4v": ".m4v",
}


def video_url(file_id: str | None) -> str | None:
    if file_id and file_id.startswith("local:"):
        return f"/media/videos/{file_id.removeprefix('local:')}"
    return None


def video_path(file_id: str | None) -> Path | None:
    if file_id and file_id.startswith("local:"):
        path = MEDIA_VIDEOS / file_id.removeprefix("local:")
        return path if path.exists() else None
    return None


def remove_video(file_id: str | None) -> None:
    path = video_path(file_id)
    if path is not None:
        path.unlink(missing_ok=True)


async def _run_ffmpeg(args: list[str]) -> bool:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        *args,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=FFMPEG_TIMEOUT_SEC)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        logger.warning("ffmpeg timed out: %s", args)
        return False
    if proc.returncode != 0:
        logger.warning("ffmpeg failed (%s): %s", proc.returncode, stderr.decode(errors="ignore")[-500:])
        return False
    return True


async def normalize_to_mp4(src: Path) -> Path:
    """Return an MP4 Telegram plays inline; fall back to the original file."""
    if shutil.which("ffmpeg") is None:
        logger.warning("ffmpeg not installed; keeping %s as is", src.name)
        return src

    dest = src.with_name(f"{uuid.uuid4().hex}.mp4")
    remux = ["-i", str(src), "-c", "copy", "-movflags", "+faststart", str(dest)]
    transcode = [
        "-i",
        str(src),
        "-vf",
        "scale='min(1280,iw)':-2",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "26",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(dest),
    ]
    for args in (remux, transcode):
        if await _run_ffmpeg(args) and dest.exists() and dest.stat().st_size > 0:
            if dest.stat().st_size <= MAX_VIDEO_BYTES:
                src.unlink(missing_ok=True)
                return dest
        dest.unlink(missing_ok=True)
    return src
