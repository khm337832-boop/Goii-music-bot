"""YouTube search + MP3 download helpers built on yt-dlp.

Blocking yt-dlp work always runs in a worker thread so the Telegram bot's
event loop stays responsive.
"""
from __future__ import annotations

import asyncio
import glob
import logging
import os
from dataclasses import dataclass

import yt_dlp

from config import Settings

LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class Track:
    id: str
    title: str
    channel: str = ""
    duration: int = 0
    url: str = ""

    @property
    def pretty_duration(self) -> str:
        if self.duration <= 0:
            return ""
        minutes, seconds = divmod(self.duration, 60)
        return f"{minutes}:{seconds:02d}"


def _search_sync(query: str, limit: int) -> list[Track]:
    options = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
        "noplaylist": True,
        "playlistend": limit,
        "socket_timeout": 15,
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False) or {}

    tracks: list[Track] = []
    for entry in info.get("entries") or []:
        if not entry or not entry.get("id"):
            continue
        video_id = str(entry["id"])
        tracks.append(
            Track(
                id=video_id,
                title=str(entry.get("title") or "Unknown title").strip(),
                channel=str(entry.get("channel") or entry.get("uploader") or "").strip(),
                duration=int(entry.get("duration") or 0),
                url=f"https://www.youtube.com/watch?v={video_id}",
            )
        )
    return tracks


async def search_tracks(query: str, limit: int = 5) -> list[Track]:
    """Search YouTube and return a small list of playable tracks."""
    return await asyncio.to_thread(_search_sync, query, max(1, min(limit, 8)))


def _download_sync(video_id: str, settings: Settings) -> tuple[str, dict]:
    os.makedirs(settings.download_dir, exist_ok=True)
    template = os.path.join(settings.download_dir, f"{video_id}.%(ext)s")
    options = {
        "format": "bestaudio/best",
        "outtmpl": template,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": settings.audio_quality,
        }],
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "max_filesize": settings.max_file_mb * 1024 * 1024,
        "socket_timeout": 20,
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(
            f"https://www.youtube.com/watch?v={video_id}", download=True
        ) or {}

    files = glob.glob(os.path.join(settings.download_dir, f"{video_id}.*"))
    mp3 = next((path for path in files if path.lower().endswith(".mp3")), None)
    if not mp3:
        cleanup_download(video_id, settings)
        raise RuntimeError("FFmpeg နဲ့ MP3 မပြောင်းနိုင်ပါဘူး")

    meta = {
        "title": str(info.get("title") or "Unknown title"),
        "performer": str(
            info.get("artist") or info.get("creator") or info.get("channel")
            or info.get("uploader") or "Unknown artist"
        ),
        "duration": int(info.get("duration") or 0),
    }
    return mp3, meta


async def download_track(video_id: str, settings: Settings) -> tuple[str, dict]:
    """Download + convert one video to MP3. Returns (file_path, metadata)."""
    return await asyncio.to_thread(_download_sync, video_id, settings)


def cleanup_download(video_id: str, settings: Settings) -> None:
    """Remove every temporary file belonging to a video (also on failure)."""
    # Only allow the simple IDs yt-dlp gives us — no path traversal.
    if not video_id or not all(c.isalnum() or c in "-_" for c in video_id):
        return
    for path in glob.glob(os.path.join(settings.download_dir, f"{video_id}.*")):
        try:
            os.remove(path)
        except OSError as exc:
            LOG.debug("Could not remove %s: %s", path, exc)
