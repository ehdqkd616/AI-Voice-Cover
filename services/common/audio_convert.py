"""ffmpeg-based format conversion."""

import subprocess
from pathlib import Path

LIBSNDFILE_EXTS = {"wav", "aiff", "aif", "flac"}

ENCODE_OPTS = {
    "mp3-320": (["-codec:a", "libmp3lame", "-b:a", "320k"], "mp3"),
    "mp3-192": (["-codec:a", "libmp3lame", "-b:a", "192k"], "mp3"),
    "wav": ([], "wav"),
}


def ensure_wav(src: str) -> str:
    """Returns a path guaranteed to be WAV — converts via ffmpeg if `src` isn't already."""
    ext = Path(src).suffix.lstrip(".").lower()
    if ext in LIBSNDFILE_EXTS:
        return src
    dst = str(Path(src).with_suffix(".wav"))
    subprocess.run(
        ["ffmpeg", "-y", "-i", src, dst],
        check=True, capture_output=True, shell=False,
    )
    return dst


def encode(src_wav: str, dst: str, output_format: str) -> str:
    args, _ = ENCODE_OPTS.get(output_format, ENCODE_OPTS["mp3-320"])
    subprocess.run(
        ["ffmpeg", "-y", "-i", src_wav, *args, dst],
        check=True, capture_output=True, shell=False,
    )
    return dst
