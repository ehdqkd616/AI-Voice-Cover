"""ffprobe-based media inspection (upload validation, download post-processing)."""

import json
import subprocess


class ProbeError(Exception):
    pass


def probe(path: str) -> dict:
    """Runs ffprobe and returns {duration_sec, sample_rate, channels, codec}.

    Deliberately invoked with a list (never shell=True) — never build this
    command from string concatenation.
    """
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                path,
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ProbeError(str(exc)) from exc

    data = json.loads(proc.stdout)
    fmt = data.get("format", {})
    audio_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), {})

    return {
        "duration_sec": float(fmt.get("duration", 0.0)),
        "sample_rate": int(audio_stream["sample_rate"]) if audio_stream.get("sample_rate") else None,
        "channels": audio_stream.get("channels"),
        "codec": audio_stream.get("codec_name"),
        "has_audio": bool(audio_stream),
    }
