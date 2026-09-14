"""Redis-backed caches + the job progress pub/sub channel."""

import hashlib
import json

import numpy as np

from .redis_client import get_redis

L1_TTL = 60 * 60 * 24  # 24h — youtube download cache
L2_TTL = 60 * 60 * 24 * 7  # 7d — separation result cache
L4_TTL = 60 * 60 * 24 * 7  # 7d — rvc conversion result cache


def content_hash(path: str) -> str:
    """Hash of the decoded PCM, normalized to 16kHz mono.

    Same song encoded as 320k MP3 vs WAV hashes identically, so uploads and
    youtube extracts of the same track share the L2/L4 cache regardless of
    source format.
    """
    import librosa

    y, _ = librosa.load(path, sr=16000, mono=True)
    y = np.round(y, 4)
    return hashlib.sha256(y.tobytes()).hexdigest()


def l1_key(video_id: str, fmt: str, quality: str) -> str:
    return f"media:{video_id}:{fmt}:{quality}"


def l2_key(content_hash_: str, model: str, stems: int) -> str:
    return f"sep:{content_hash_}:{model}:{stems}"


def convert_key(content_hash_: str, voice_model_id: str, f0_up_key: int, f0_method: str, index_rate: float, protect: float) -> str:
    return f"rvc:{content_hash_}:{voice_model_id}:{f0_up_key}:{f0_method}:{index_rate}:{protect}"


def cache_get(key: str) -> dict | None:
    raw = get_redis().get(key)
    return json.loads(raw) if raw else None


def cache_set(key: str, value: dict, ttl: int) -> None:
    get_redis().set(key, json.dumps(value), ex=ttl)


def publish_progress(job_id: str, payload: dict) -> None:
    get_redis().publish(f"progress:{job_id}", json.dumps(payload))
