"""Orchestration for the four-stage cover pipeline: ingest -> separate ->
convert -> mix. Each stage is its own Celery task on its own queue; stages
are chained via job_lifecycle.advance_stage() (params merge + re-enqueue)
rather than a Celery chain/chord, so Job.stage/progress/error in Postgres
stays the single source of truth the API's SSE stream reads from.

The upload path (media uploaded directly via the API's /upload endpoint)
skips straight to the "separate" stage — cover_separate reads
params["media_id"] regardless of whether it was set by the API at job
creation or by cover_ingest_youtube's advance_stage call, so it works either way.
"""

import glob
import os
import shutil
import tempfile
from types import SimpleNamespace

import soundfile as sf
from yt_dlp import DownloadError, YoutubeDL

from common.audio_convert import encode, ensure_wav
from common.cache import L2_TTL, L4_TTL, cache_get, cache_set, content_hash, convert_key, l2_key
from common.config import get_settings
from common.db.models import Job, Media, VoiceModel
from common.db.session import session_scope
from common.ffprobe import probe
from common.storage import download_file, upload_file
from common.ytdlp import CLIENT_FALLBACK_CHAIN, classify_youtube_error, is_permanent_error

from ..celery_app import app
from ..convert.engine import convert_vocal
from ..download.ytdlp_config import audio_opts
from ..job_lifecycle import (
    BACKOFF_SEC,
    advance_stage,
    mark_failed,
    mark_progress,
    mark_running,
    mark_succeeded,
    register_media,
    scaled_progress,
)
from ..mix.mixer import mix as mix_audio
from ..separation.separator import load_model, save_stem, separate

MIME_TYPES = {"mp3": "audio/mpeg", "wav": "audio/wav", "m4a": "audio/mp4"}


@app.task(name="tasks.cover_ingest_youtube", bind=True, max_retries=3)
def cover_ingest_youtube(self, job_id: str) -> dict:
    with session_scope() as db:
        job = db.get(Job, job_id)
        params = dict(job.params)
        user_id = job.user_id

    mark_running(job_id)
    mark_progress(job_id, scaled_progress("ingest", 1), "downloading")  # immediate feedback
    url = params["youtube_url"]

    out_dir = tempfile.mkdtemp(prefix="ingest_")
    try:
        info = None
        last_error: Exception | None = None
        for client in CLIENT_FALLBACK_CHAIN:
            opts = audio_opts(job_id, "mp3-320", out_dir, client)
            try:
                with YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                break
            except DownloadError as exc:  # try next client in the chain
                last_error = exc
                if is_permanent_error(str(exc)):
                    # DRM/unavailable/private is a property of the video, not the
                    # client — every other client would fail the same way.
                    break
                continue
        if info is None:
            raise last_error or RuntimeError("yt-dlp extraction failed for all clients")

        candidates = [
            f for f in glob.glob(f"{out_dir}/*") if not f.endswith((".jpg", ".webp", ".png", ".part"))
        ]
        if not candidates:
            raise RuntimeError("no output file produced")
        local_path = max(candidates, key=os.path.getsize)
        ext = local_path.rsplit(".", 1)[-1].lower()

        meta = probe(local_path)
        file_hash = content_hash(local_path)
        size_bytes = os.path.getsize(local_path)
        mime_type = MIME_TYPES.get(ext, "application/octet-stream")
        video_id = info.get("id")

        storage_key = f"youtube/{video_id}/mp3-320.{ext}"
        upload_file(local_path, storage_key, mime_type)

        media_id = register_media(
            kind="source",
            source_type="youtube",
            parent_id=None,
            content_hash=file_hash,
            storage_key=storage_key,
            mime_type=mime_type,
            size_bytes=size_bytes,
            duration_sec=meta["duration_sec"],
            sample_rate=meta["sample_rate"],
            channels=meta["channels"],
            yt_video_id=video_id,
            title=info.get("title"),
            artist=info.get("channel") or info.get("uploader"),
            lineage={"op": "youtube_extract", "kind": "audio", "format_id": "mp3-320"},
            user_id=user_id,
        )

        mark_progress(job_id, scaled_progress("ingest", 100), "downloading")
        advance_stage(job_id, "separate", {"media_id": media_id}, "tasks.cover_separate", "separate")
        return {"media_id": media_id}

    except Exception as exc:
        code = classify_youtube_error(str(exc))
        retryable = mark_failed(job_id, code, str(exc))
        if retryable:
            attempt = self.request.retries
            raise self.retry(exc=exc, countdown=BACKOFF_SEC[min(attempt, len(BACKOFF_SEC) - 1)])
        raise
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


@app.task(name="tasks.cover_separate", bind=True, max_retries=1)
def cover_separate(self, job_id: str) -> dict:
    settings = get_settings()

    with session_scope() as db:
        job = db.get(Job, job_id)
        params = dict(job.params)
        user_id = job.user_id
        media = db.get(Media, params["media_id"])
        source_hash = media.content_hash
        storage_key = media.storage_key
        source_title = media.title
        source_artist = media.artist

    stems = 2
    quality = params.get("quality", "fast")
    model_name = settings.demucs_hq_model if quality == "high" else settings.demucs_fast_model

    mark_running(job_id)

    cache_key = l2_key(source_hash, model_name, stems)
    cached = cache_get(cache_key)
    if cached and cached.get("vocals_media_id") and cached.get("instrumental_media_id"):
        mark_progress(job_id, scaled_progress("separate", 100), "separating")
        advance_stage(
            job_id,
            "convert",
            {
                "vocals_media_id": cached["vocals_media_id"],
                "instrumental_media_id": cached["instrumental_media_id"],
            },
            "tasks.cover_convert",
            "convert",
        )
        return cached

    work_dir = tempfile.mkdtemp(prefix="sep_")
    try:
        local_src = os.path.join(work_dir, "source")
        download_file(storage_key, local_src)

        mark_progress(job_id, scaled_progress("separate", 5), "separating")
        model = load_model(model_name)  # cached — separate() below loads the same instance
        result = separate(local_src, model_name, stems)
        mark_progress(job_id, scaled_progress("separate", 80), "separating")

        output_ids: dict[str, str] = {}
        for stem_name, tensor in result.items():
            local_out = os.path.join(work_dir, f"{stem_name}.wav")
            save_stem(tensor, local_out, sample_rate=model.samplerate)

            stem_key = f"separated/{source_hash}/{model_name}/{stem_name}.wav"
            upload_file(local_out, stem_key, "audio/wav")

            media_id = register_media(
                kind="stem",
                source_type="derived",
                parent_id=params["media_id"],
                content_hash=f"{source_hash}:{model_name}:{stem_name}",
                storage_key=stem_key,
                mime_type="audio/wav",
                size_bytes=os.path.getsize(local_out),
                title=source_title,
                artist=source_artist,
                lineage={"op": "separate", "model": model_name, "stem": stem_name, "stems": stems},
                user_id=user_id,
            )
            output_ids[stem_name] = media_id

        cache_payload = {
            "vocals_media_id": output_ids.get("vocals"),
            "instrumental_media_id": output_ids.get("instrumental"),
        }
        cache_set(cache_key, cache_payload, L2_TTL)

        mark_progress(job_id, scaled_progress("separate", 100), "separating")
        advance_stage(job_id, "convert", cache_payload, "tasks.cover_convert", "convert")
        return cache_payload

    except Exception as exc:
        code = "GPU_OOM" if "out of memory" in str(exc).lower() else "EXTRACTION_FAILED"
        mark_failed(job_id, code, str(exc))
        raise
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


@app.task(name="tasks.cover_convert", bind=True, max_retries=1)
def cover_convert(self, job_id: str) -> dict:
    settings = get_settings()

    with session_scope() as db:
        job = db.get(Job, job_id)
        params = dict(job.params)
        user_id = job.user_id
        vocals_media = db.get(Media, params["vocals_media_id"])
        vocals_hash = vocals_media.content_hash
        vocals_storage_key = vocals_media.storage_key
        vocals_title = vocals_media.title
        vocals_artist = vocals_media.artist
        voice_model_row = db.get(VoiceModel, params["voice_model_id"])
        # session_scope() commits on exit, which expires every attribute on
        # objects it tracked — accessing voice_model_row.* after the `with`
        # block raises DetachedInstanceError. Copy what's needed into a plain
        # object now, while the session is still open (same reason
        # vocals_hash/vocals_storage_key/etc. above are copied to locals
        # instead of reading vocals_media.* later).
        voice_model = (
            SimpleNamespace(
                id=voice_model_row.id,
                name=voice_model_row.name,
                weight_filename=voice_model_row.weight_filename,
                index_filename=voice_model_row.index_filename,
                speaker_id=voice_model_row.speaker_id,
                is_active=voice_model_row.is_active,
            )
            if voice_model_row is not None
            else None
        )

    # Shouldn't happen — the API validates voice_model_id before creating the
    # job — but defend anyway rather than let a stale/deleted model 500 deep
    # inside the RVC engine with a confusing torch.load(FileNotFoundError).
    if voice_model is None or not voice_model.is_active:
        message = f"Voice model {params.get('voice_model_id')!r} not found or inactive"
        mark_failed(job_id, "VOICE_MODEL_NOT_FOUND", message)
        raise RuntimeError(message)

    f0_up_key = int(params.get("f0_up_key", 0))
    f0_method = params.get("f0_method") or settings.rvc_default_f0_method
    index_rate = float(params.get("index_rate", settings.rvc_default_index_rate))
    protect = float(params.get("protect", settings.rvc_default_protect))
    rms_mix_rate = float(params.get("rms_mix_rate", settings.rvc_default_rms_mix_rate))
    voice_model_name = params.get("voice_model_name") or voice_model.name

    mark_running(job_id)

    cache_key = convert_key(vocals_hash, voice_model.id, f0_up_key, f0_method, index_rate, protect)
    cached = cache_get(cache_key)
    if cached and cached.get("media_id"):
        mark_progress(job_id, scaled_progress("convert", 100), "converting")
        advance_stage(
            job_id, "mix", {"converted_vocals_media_id": cached["media_id"]}, "tasks.cover_mix", "dsp"
        )
        return cached

    work_dir = tempfile.mkdtemp(prefix="conv_")
    try:
        local_src = os.path.join(work_dir, "vocals_src")
        download_file(vocals_storage_key, local_src)
        wav_src = ensure_wav(local_src)

        mark_progress(job_id, scaled_progress("convert", 10), "converting")
        sr, audio = convert_vocal(voice_model, wav_src, f0_up_key, f0_method, index_rate, protect, rms_mix_rate)
        mark_progress(job_id, scaled_progress("convert", 80), "converting")

        out_path = os.path.join(work_dir, "converted.wav")
        sf.write(out_path, audio, sr)

        meta = probe(out_path)
        out_hash = content_hash(out_path)
        storage_key = f"processed/{out_hash}.wav"
        upload_file(out_path, storage_key, "audio/wav")

        media_id = register_media(
            kind="processed",
            source_type="derived",
            parent_id=params["vocals_media_id"],
            content_hash=out_hash,
            storage_key=storage_key,
            mime_type="audio/wav",
            size_bytes=os.path.getsize(out_path),
            duration_sec=meta["duration_sec"],
            sample_rate=meta["sample_rate"],
            channels=meta["channels"],
            title=vocals_title,
            artist=vocals_artist,
            lineage={
                "op": "rvc_convert",
                "voice_model_id": voice_model.id,
                "voice_model_name": voice_model_name,
                "f0_up_key": f0_up_key,
                "f0_method": f0_method,
                "index_rate": index_rate,
                "protect": protect,
            },
            user_id=user_id,
        )
        cache_set(cache_key, {"media_id": media_id}, L4_TTL)

        mark_progress(job_id, scaled_progress("convert", 100), "converting")
        advance_stage(job_id, "mix", {"converted_vocals_media_id": media_id}, "tasks.cover_mix", "dsp")
        return {"media_id": media_id}

    except Exception as exc:
        code = "GPU_OOM" if "out of memory" in str(exc).lower() else "EXTRACTION_FAILED"
        mark_failed(job_id, code, str(exc))
        raise
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


@app.task(name="tasks.cover_mix", bind=True, max_retries=1)
def cover_mix(self, job_id: str) -> dict:
    settings = get_settings()

    with session_scope() as db:
        job = db.get(Job, job_id)
        params = dict(job.params)
        user_id = job.user_id
        converted_media = db.get(Media, params["converted_vocals_media_id"])
        instrumental_media = db.get(Media, params["instrumental_media_id"])
        converted_storage_key = converted_media.storage_key
        instrumental_storage_key = instrumental_media.storage_key
        title = converted_media.title
        artist = converted_media.artist

    output_format = params.get("output_format") or settings.mix_default_output_format
    vocal_gain_db = float(params.get("vocal_gain_db", settings.mix_default_vocal_gain_db))
    instrumental_pitch = int(params.get("instrumental_pitch", 0))
    voice_model_id = params.get("voice_model_id")
    voice_model_name = params.get("voice_model_name")

    mark_running(job_id)
    work_dir = tempfile.mkdtemp(prefix="mix_")
    try:
        local_vocal = os.path.join(work_dir, "vocal_src")
        local_inst = os.path.join(work_dir, "inst_src")
        download_file(converted_storage_key, local_vocal)
        download_file(instrumental_storage_key, local_inst)
        vocal_wav = ensure_wav(local_vocal)
        inst_wav = ensure_wav(local_inst)

        mark_progress(job_id, scaled_progress("mix", 30), "mixing")
        mixed_wav = mix_audio(vocal_wav, inst_wav, vocal_gain_db, instrumental_pitch, work_dir)
        mark_progress(job_id, scaled_progress("mix", 70), "mixing")

        ext = "wav" if output_format == "wav" else "mp3"
        final_path = os.path.join(work_dir, f"final.{ext}")
        encode(mixed_wav, final_path, output_format)

        meta = probe(final_path)
        out_hash = content_hash(final_path)
        mime = "audio/wav" if ext == "wav" else "audio/mpeg"
        storage_key = f"processed/{out_hash}.{ext}"
        upload_file(final_path, storage_key, mime)

        media_id = register_media(
            kind="processed",
            source_type="derived",
            parent_id=params["converted_vocals_media_id"],
            content_hash=out_hash,
            storage_key=storage_key,
            mime_type=mime,
            size_bytes=os.path.getsize(final_path),
            duration_sec=meta["duration_sec"],
            sample_rate=meta["sample_rate"],
            channels=meta["channels"],
            title=title,
            artist=artist,
            lineage={
                "op": "cover_mix",
                "voice_model_id": voice_model_id,
                "voice_model_name": voice_model_name,
                "output_format": output_format,
                "vocal_gain_db": vocal_gain_db,
                "instrumental_pitch": instrumental_pitch,
            },
            user_id=user_id,
        )
        # The only stage of the four that terminates the chain — the API
        # teammate's job-status/SSE consumers expect the job to end here.
        mark_succeeded(job_id, [media_id])
        return {"media_id": media_id}

    except Exception as exc:
        mark_failed(job_id, "EXTRACTION_FAILED", str(exc))
        raise
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
