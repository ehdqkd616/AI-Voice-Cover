"""Voice-model training task: dataset prep -> preprocess -> feature
extraction -> train -> index -> register the model. Runs on worker-separate-
convert (queue `train`) because every heavy step needs the host's single GPU;
a cover requested meanwhile waits its turn on the same solo worker.

Progress lives on the Job row (type="train"): Job.stage follows the steps
above and Job.params carries live training stats (current_epoch, eta_sec,
effective_batch_size, checkpoint_epoch) for the /train UI, which polls it.

A resume ("이어서 학습", params.resume) reuses the experiment dir: it skips
straight to training from the last G/D checkpoint with a raised epoch target,
then updates the already-registered model in place.
"""

import gc
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone

from common.audio_convert import ensure_wav
from common.cache import publish_progress
from common.config import get_settings
from common.db.models import Job, Media, VoiceModel
from common.db.session import session_scope
from common.ids import new_id
from common.redis_client import get_redis
from common.storage import download_file

from ..celery_app import app
from ..convert import engine as convert_engine
from ..job_lifecycle import mark_failed, mark_running, mark_succeeded, scaled_progress
from ..separation import separator
from ..training import pipeline
from ..training.pipeline import TrainingCancelled, TrainingFailed

STAGE_LABEL = {
    "prepare": "학습 데이터 준비",
    "preprocess": "데이터 전처리",
    "extract": "음성 특징 추출",
    "train": "모델 학습",
    "index": "검색 인덱스 생성",
}
MIN_DATASET_SECONDS = 60


def cancel_key(job_id: str) -> str:
    return f"train:cancel:{job_id}"


def _update(job_id: str, stage: str, local_percent: float, **params) -> None:
    percent = round(scaled_progress(stage, min(max(local_percent, 0), 100)), 2)
    with session_scope() as db:
        job = db.get(Job, job_id)
        job.stage = stage
        job.progress = percent
        if params:
            job.params = {**job.params, **params}
    publish_progress(job_id, {"stage": stage, "label": STAGE_LABEL[stage], "percent": percent, **params})


def _release_gpu() -> None:
    """Training runs in subprocesses, so VRAM still held by this worker's
    cached Demucs/RVC models is VRAM training can't use — on a 4GB card that
    is the difference between batch size 4 and an OOM."""
    convert_engine.release_models()
    separator.release_models()
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def _log(exp_name: str, message: str) -> None:
    path = pipeline.exp_path(exp_name) / "prepare.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    with open(path, "a", encoding="utf8") as f:
        f.write(f"[{stamp}] {message}\n")


def _prepare_dataset(job_id: str, exp_name: str, media: list[dict], auto_vocal: bool, should_cancel) -> float:
    """Downloads every training file into <exp>/dataset/ as WAV — first
    isolating the vocal with Demucs when auto_vocal is on, so songs with
    accompaniment can be used as-is (the RVC webui expects clean vocals)."""
    settings = get_settings()
    dataset_dir = pipeline.exp_path(exp_name) / "dataset"
    shutil.rmtree(dataset_dir, ignore_errors=True)
    dataset_dir.mkdir(parents=True)

    work_dir = tempfile.mkdtemp(prefix="trainprep_")
    try:
        for i, item in enumerate(media):
            if should_cancel():
                raise TrainingCancelled()
            _log(exp_name, f"({i + 1}/{len(media)}) {item['title'] or item['id']} 준비 중")
            local = os.path.join(work_dir, f"src_{i}{os.path.splitext(item['storage_key'])[1]}")
            download_file(item["storage_key"], local)
            wav = ensure_wav(local)
            target = dataset_dir / f"{i:03d}.wav"
            if auto_vocal:
                stems = separator.separate(wav, settings.demucs_fast_model, 2)
                model = separator.load_model(settings.demucs_fast_model)
                separator.save_stem(stems["vocals"], str(target), sample_rate=model.samplerate)
                _log(exp_name, "  보컬만 추출 완료 (Demucs)")
            else:
                shutil.copyfile(wav, target)
            _update(job_id, "prepare", 100 * (i + 1) / len(media))
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    seconds = pipeline.dataset_seconds(dataset_dir)
    _log(exp_name, f"학습 데이터 총 {seconds / 60:.1f}분")
    if seconds < MIN_DATASET_SECONDS:
        raise TrainingFailed(
            "TRAIN_DATASET_TOO_SHORT",
            f"학습 데이터가 너무 짧습니다 ({seconds:.0f}초). 최소 1분, 권장 10분 이상의 목소리가 필요합니다.",
        )
    return seconds


def _default_description(epochs: int) -> str:
    return f"직접 학습한 모델 · {epochs} epoch"


def _register_model(job_id: str, params: dict, user_id, sample_rate: str, index_name: str) -> str:
    with session_scope() as db:
        existing = db.get(VoiceModel, params["voice_model_id"]) if params.get("voice_model_id") else None
        if existing is not None:
            # Resumed run: same weight file (overwritten by train.py), so just
            # refresh the index and the auto-generated epoch count.
            existing.index_filename = index_name
            if not existing.description or re.fullmatch(r"직접 학습한 모델 · \d+ epoch", existing.description):
                existing.description = _default_description(int(params["epochs"]))
            return existing.id

        name = params["name"]
        taken = {n for (n,) in db.query(VoiceModel.name).all()}
        suffix = 2
        while name in taken:  # the API checks too; this covers a race between two jobs
            name = f"{params['name']} ({suffix})"
            suffix += 1
        vm = VoiceModel(
            id=new_id("vm"),
            name=name,
            weight_filename=f"{params['exp_name']}.pth",
            index_filename=index_name,
            version="v2",
            sample_rate=pipeline.SR_INT[sample_rate],
            has_f0=True,
            description=params.get("description") or _default_description(int(params["epochs"])),
            pairing_confidence="manual",
            uploaded_by=user_id,
        )
        db.add(vm)
        return vm.id


@app.task(name="tasks.train_voice_model", bind=True, acks_late=False, max_retries=0)
def train_voice_model(self, job_id: str) -> dict:
    # acks_late=False: a multi-hour task must not be re-delivered if the
    # broker's visibility window lapses mid-run (see celery_app.py).
    settings = get_settings()
    with session_scope() as db:
        job = db.get(Job, job_id)
        params = dict(job.params)
        user_id = job.user_id
        media = [
            {"id": m.id, "storage_key": m.storage_key, "title": m.title}
            for m in (db.get(Media, mid) for mid in params["media_ids"])
            if m is not None
        ]

    exp_name = params["exp_name"]
    sample_rate = params["sample_rate"]
    resume = bool(params.get("resume")) and pipeline.has_checkpoint(exp_name)
    redis = get_redis()

    def should_cancel() -> bool:
        return bool(redis.exists(cancel_key(job_id)))

    if should_cancel():  # stopped from the UI before this worker got to it
        mark_failed(job_id, "CANCELLED", "학습을 중지했습니다.")
        redis.delete(cancel_key(job_id))
        return {"cancelled": True}

    mark_running(job_id)
    try:
        pipeline.ensure_runtime_assets(sample_rate)
        _release_gpu()

        if resume:
            # Dataset, slices and features are already in the experiment dir.
            _log(exp_name, f"이어서 학습 — 저장된 체크포인트(epoch {params.get('checkpoint_epoch') or '?'})부터 {params['epochs']} epoch까지")
        else:
            if not media:
                raise TrainingFailed("TRAIN_DATASET_TOO_SHORT", "학습에 쓸 음원을 찾을 수 없습니다.")
            _update(job_id, "prepare", 0)
            seconds = _prepare_dataset(job_id, exp_name, media, params.get("auto_vocal", True), should_cancel)
            _release_gpu()  # Demucs, used just above, is the biggest VRAM holder
            _update(job_id, "prepare", 100, dataset_seconds=round(seconds, 1))

            _update(job_id, "preprocess", 0)
            slices = pipeline.preprocess(exp_name, pipeline.exp_path(exp_name) / "dataset", sample_rate, should_cancel)
            _update(job_id, "preprocess", 100, slices=slices)

            _update(job_id, "extract", 0)
            pipeline.extract_features(exp_name, should_cancel, lambda pct: _update(job_id, "extract", pct))

        pipeline.write_filelist_and_config(exp_name, sample_rate)
        epochs = int(params["epochs"])
        start_epoch = int(params.get("checkpoint_epoch") or 0) if resume else 0
        save_every = pipeline.save_interval(epochs)
        _update(
            job_id, "train", 100 * start_epoch / epochs,
            current_epoch=start_epoch, eta_sec=None, effective_batch_size=params["batch_size"],
        )
        last = {"epoch": start_epoch}

        def on_epoch(epoch: int, sec_per_epoch: float | None, bs: int) -> None:
            if epoch <= last["epoch"]:  # a resume first redoes the checkpoint epoch
                return
            last["epoch"] = epoch
            eta = round(sec_per_epoch * (epochs - epoch)) if sec_per_epoch else None
            extra = {"checkpoint_epoch": epoch} if epoch % save_every == 0 or epoch >= epochs else {}
            _update(
                job_id, "train", 100 * epoch / epochs,
                current_epoch=epoch, eta_sec=eta, sec_per_epoch=sec_per_epoch, effective_batch_size=bs, **extra,
            )

        bs = pipeline.train(exp_name, sample_rate, epochs, int(params["batch_size"]), should_cancel, on_epoch)
        _update(job_id, "train", 100, current_epoch=epochs, checkpoint_epoch=epochs, eta_sec=0, effective_batch_size=bs)

        _update(job_id, "index", 0)
        # The index only depends on the extracted features, which a resume
        # doesn't touch — reuse the one built last time when it's there.
        built = pipeline.existing_index(exp_name) if resume else None
        index_path = built or pipeline.build_index(exp_name, should_cancel)
        os.makedirs(settings.rvc_index_root, exist_ok=True)
        shutil.copyfile(index_path, os.path.join(settings.rvc_index_root, index_path.name))

        with session_scope() as db:  # re-read: the model may have been deleted meanwhile
            params["voice_model_id"] = (db.get(Job, job_id).params or {}).get("voice_model_id")
        voice_model_id = _register_model(job_id, params, user_id, sample_rate, index_path.name)
        _update(job_id, "index", 100, voice_model_id=voice_model_id)
        mark_succeeded(job_id, [])
        return {"voice_model_id": voice_model_id}

    except TrainingCancelled:
        mark_failed(job_id, "CANCELLED", "학습을 중지했습니다.")
        return {"cancelled": True}
    except TrainingFailed as exc:
        mark_failed(job_id, exc.code, exc.message)
        return {"error": exc.code}
    except Exception as exc:
        mark_failed(job_id, "TRAIN_FAILED", f"학습 중 오류가 발생했습니다: {exc}")
        raise
    finally:
        redis.delete(cancel_key(job_id))
        _release_gpu()
