"""yt-dlp option builder for the ingest stage.

Audio-only — this app never extracts video (no `video_opts`/`VIDEO_HEIGHTS`;
the pipeline always separates the best-audio download into stems).
"""

from common.cache import publish_progress
from common.ytdlp import base_opts

AUDIO_CODECS = {
    "mp3-320": ("mp3", "320"),
    "mp3-192": ("mp3", "192"),
    "wav": ("wav", None),
}

# yt-dlp's EmbedThumbnail postprocessor only supports these containers ("Supported
# filetypes for thumbnail embedding are: mp3, mkv/mka, ogg/opus/flac, m4a/mp4/m4v/mov").
# wav isn't one of them — forcing it there raised a postprocessing error that yt-dlp
# then confusingly re-reported as "This video is DRM protected", which looked like a
# YouTube-side block but was entirely our own postprocessor misconfiguration.
THUMBNAIL_EMBEDDABLE_CODECS = {"mp3", "m4a", "flac", "opus", "ogg"}


def make_progress_hook(job_id: str):
    def hook(d: dict) -> None:
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes", 0)
            percent = round(done / total * 100, 1) if total else 0.0
            publish_progress(job_id, {"stage": "downloading", "percent": percent})
        elif d["status"] == "finished":
            publish_progress(job_id, {"stage": "downloading", "percent": 100.0})

    return hook


def audio_opts(job_id: str, format_id: str, out_dir: str, player_client: str | None = None) -> dict:
    codec, quality = AUDIO_CODECS.get(format_id, ("mp3", "320"))
    postprocessor = {"key": "FFmpegExtractAudio", "preferredcodec": codec}
    if quality:
        postprocessor["preferredquality"] = quality

    postprocessors = [postprocessor, {"key": "FFmpegMetadata", "add_metadata": True}]
    embed_thumbnail = codec in THUMBNAIL_EMBEDDABLE_CODECS
    if embed_thumbnail:
        postprocessors.append({"key": "EmbedThumbnail"})

    opts = base_opts(player_client)
    opts.update(
        {
            "format": "bestaudio/best",
            "postprocessors": postprocessors,
            "writethumbnail": embed_thumbnail,
            "outtmpl": f"{out_dir}/%(id)s.%(ext)s",
            "progress_hooks": [make_progress_hook(job_id)],
        }
    )
    return opts
