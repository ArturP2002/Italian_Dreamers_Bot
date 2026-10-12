"""Greeting video storage: save upload, normalize to MP4 for Telegram."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

MEDIA_VIDEOS = Path(__file__).resolve().parents[2] / "media" / "videos"
MEDIA_VIDEOS.mkdir(parents=True, exist_ok=True)

# Telegram Bot API rejects multipart uploads above 50 MB.
MAX_VIDEO_BYTES = 50 * 1024 * 1024
FFMPEG_TIMEOUT_SEC = 180
FFPROBE_TIMEOUT_SEC = 30

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


@dataclass
class VideoInfo:
    # Display size, i.e. after applying the rotation.
    width: int
    height: int
    duration: int
    # Degrees the player must rotate the stored frames (iPhone portrait videos: 90).
    rotation: int


async def probe_video(path: Path) -> VideoInfo | None:
    if shutil.which("ffprobe") is None:
        return None
    proc = await asyncio.create_subprocess_exec(
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_streams",
        "-show_format",
        "-of",
        "json",
        str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=FFPROBE_TIMEOUT_SEC)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        logger.warning("ffprobe timed out: %s", path.name)
        return None
    try:
        data = json.loads(stdout or b"{}")
        stream = (data.get("streams") or [])[0]
        rotation_raw = (stream.get("tags") or {}).get("rotate") or next(
            (sd["rotation"] for sd in stream.get("side_data_list") or [] if "rotation" in sd),
            0,
        )
        rotation = int(float(rotation_raw)) % 360
        width, height = int(stream["width"]), int(stream["height"])
        if rotation in (90, 270):
            width, height = height, width
        duration = float(stream.get("duration") or (data.get("format") or {}).get("duration") or 0)
    except (IndexError, KeyError, TypeError, ValueError):
        logger.warning("Unreadable ffprobe output for %s", path.name)
        return None
    return VideoInfo(width=width, height=height, duration=round(duration), rotation=rotation)


async def video_metadata(path: Path) -> dict[str, int]:
    """Width/height/duration for Telegram, so clients lay the album tile out correctly."""
    info = await probe_video(path)
    if info is None:
        return {}
    meta = {"width": info.width, "height": info.height}
    if info.duration:
        meta["duration"] = info.duration
    return meta


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
    info = await probe_video(src)
    rotated = bool(info and info.rotation)
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
    # A plain remux keeps the rotation flag, which Telegram mobile ignores in albums;
    # re-encoding bakes the rotation into the frames (ffmpeg autorotates by default).
    attempts = (transcode,) if rotated else (remux, transcode)
    for args in attempts:
        if await _run_ffmpeg(args) and dest.exists() and dest.stat().st_size > 0:
            if dest.stat().st_size <= MAX_VIDEO_BYTES:
                src.unlink(missing_ok=True)
                return dest
        dest.unlink(missing_ok=True)
    return src
