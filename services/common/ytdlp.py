"""Shared yt-dlp option base + bot-detection fallback chain."""

from .config import get_settings

# ios first: usually doesn't require a PO token. web_safari/android/tv as fallback
# if a client gets blocked.
CLIENT_FALLBACK_CHAIN = ["ios", "web_safari", "android", "tv"]

ROTATING_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
)


def base_opts(player_client: str | None = None) -> dict:
    settings = get_settings()
    opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "extractor_args": {
            "youtube": {"player_client": [player_client] if player_client else CLIENT_FALLBACK_CHAIN}
        },
        "http_headers": {"User-Agent": ROTATING_UA},
        "retries": 3,
        "socket_timeout": 30,
    }
    if settings.proxy_url:
        opts["proxy"] = settings.proxy_url
    if settings.cookie_path:
        opts["cookiefile"] = settings.cookie_path
    return opts


# Content-level failures — retrying (same or different client) can never
# succeed, so the per-client fallback loop and the outer Celery retry should
# both give up immediately instead of burning ~20-40s of backoff first.
PERMANENT_ERROR_PATTERNS = {
    "DRM_PROTECTED": ("drm protected",),
    "VIDEO_UNAVAILABLE": ("video unavailable", "video has been removed", "private video"),
    "AGE_RESTRICTED": ("sign in to confirm your age", "age-restricted", "age restricted"),
    "GEO_BLOCKED": ("not available in your country", "not available on this app"),
    "LIVE_STREAM_UNSUPPORTED": ("this live event",),
}


def classify_youtube_error(message: str) -> str:
    """Maps a yt-dlp error message to an error code.

    Anything not matched here (network blips, bot-detection blocks, format
    hiccups on one client) falls back to EXTRACTION_FAILED, which IS
    retryable — only clearly permanent, content-level failures get a
    non-retryable code.
    """
    lower = message.lower()
    for code, patterns in PERMANENT_ERROR_PATTERNS.items():
        if any(p in lower for p in patterns):
            return code
    return "EXTRACTION_FAILED"


def is_permanent_error(message: str) -> bool:
    return classify_youtube_error(message) != "EXTRACTION_FAILED"


def fetch_info(url: str) -> dict:
    """Metadata-only lookup (download=False), trying each client in the fallback chain."""
    from yt_dlp import DownloadError, YoutubeDL

    last_error: Exception | None = None
    for client in CLIENT_FALLBACK_CHAIN:
        try:
            with YoutubeDL(base_opts(client)) as ydl:
                return ydl.extract_info(url, download=False)
        except DownloadError as exc:  # try next client in the chain
            last_error = exc
            continue
    raise last_error or RuntimeError("yt-dlp extraction failed for all clients")
