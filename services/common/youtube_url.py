"""SSRF defense — only a normalized youtube.com/youtu.be watch URL survives."""

import re

_YT_PATTERN = re.compile(
    r"^https?://(www\.|m\.|music\.)?(youtube\.com/watch\?v=|youtu\.be/)"
    r"(?P<id>[A-Za-z0-9_-]{11})"
)


def extract_video_id(url: str) -> str | None:
    match = _YT_PATTERN.match(url.strip())
    return match.group("id") if match else None


def normalize_youtube_url(url: str) -> str | None:
    """Returns a canonical watch URL with playlist/timestamp params stripped, or None if invalid."""
    video_id = extract_video_id(url)
    if not video_id:
        return None
    return f"https://www.youtube.com/watch?v={video_id}"
