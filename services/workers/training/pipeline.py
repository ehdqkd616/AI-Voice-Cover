"""Voice-model training — drives the vendored RVC training scripts
(rvc_engine/train/*) as subprocesses, exactly the way RVC-Learning's webui
does, so they run unmodified. What this module adds on top is what the webui
left to the user: stage sequencing, progress/ETA parsing, cancellation, an
automatic batch-size fallback when the 4GB GPU runs out of memory, and
handing the finished .pth/.index to the voice-model registry.

The scripts resolve everything relative to rvc_engine's root
(`./logs/<exp>`, `assets/weights/<name>.pth`, `assets/pretrained_v2/...`);
docker-compose.yml bind-mounts those three paths to ./data/training,
./data/voice-models/weights and ./data/rvc-pretrained respectively.

Nothing heavy is imported at module level — this is imported by every worker
container for Celery task registration (same rule as separation/separator.py).
"""

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from random import shuffle
from typing import Callable

RVC_ROOT = Path(__file__).resolve().parent.parent / "rvc_engine"
LOGS_ROOT = RVC_ROOT / "logs"
WEIGHTS_DIR = RVC_ROOT / "assets" / "weights"
PRETRAINED_DIR = RVC_ROOT / "assets" / "pretrained_v2"

SR_INT = {"40k": 40000, "48k": 48000}
# Matches RVC webui's choice: v2 at 40k reuses the v1/40k.json architecture
# config (there is no v2/40k.json); v2 at 48k has its own.
CONFIG_TEMPLATE = {"40k": "v1/40k.json", "48k": "v2/48k.json"}

# train.py's per-epoch line once i18n'd through en_US.json, e.g.
# "====> Epoch: 12 [2026-10-09 08:00:01] | (0:00:31.234567)"
EPOCH_RE = re.compile(r"====> Epoch: (\d+) \[[^\]]*\] \| \((\d+):(\d+):([\d.]+)\)")

ShouldCancel = Callable[[], bool]


class TrainingCancelled(Exception):
    pass


class TrainingFailed(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def exp_path(exp_name: str) -> Path:
    return LOGS_ROOT / exp_name


def _stems(directory: Path, suffix: str) -> set[str]:
    if not directory.is_dir():
        return set()
    return {p.name.split(".")[0] for p in directory.iterdir() if p.name.endswith(suffix)}


def _tail(path: Path, lines: int = 40) -> str:
    try:
        return "\n".join(path.read_text(encoding="utf8", errors="replace").splitlines()[-lines:])
    except FileNotFoundError:
        return ""


def ensure_runtime_assets(sample_rate: str) -> None:
    """`logs/mute` holds the silent samples train.py mixes into every
    filelist; it lives in the bind-mounted logs dir, so seed it from the copy
    vendored under assets/ on first use."""
    mute = LOGS_ROOT / "mute"
    if not (mute / "3_feature768").is_dir():
        shutil.copytree(RVC_ROOT / "assets" / "mute", mute, dirs_exist_ok=True)
    for kind in ("G", "D"):
        path = PRETRAINED_DIR / f"f0{kind}{sample_rate}.pth"
        if not path.is_file():
            raise TrainingFailed(
                "TRAIN_ASSETS_MISSING",
                f"사전학습 모델 파일이 없습니다: data/rvc-pretrained/{path.name} (README의 '보이스 모델 학습' 참고)",
            )


def _kill(proc: subprocess.Popen) -> None:
    """Scripts spawn their own children (preprocess workers, DataLoader
    workers), so signal the whole process group, not just the parent."""
    for sig, wait in ((signal.SIGTERM, 10), (signal.SIGKILL, 5)):
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout=wait)
            return
        except subprocess.TimeoutExpired:
            continue


def run_script(
    args: list[str],
    out_log: Path,
    should_cancel: ShouldCancel,
    on_tick: Callable[[], None] | None = None,
) -> int:
    """Runs `python <args>` from rvc_engine's root. The scripts write their own
    progress logs; stdout/stderr (where an uncaught traceback — e.g. a CUDA OOM
    — ends up) goes to `out_log`."""
    env = os.environ.copy()
    env["RVC_CUDA_GRAPH"] = "0"  # same as webui does for training subprocesses
    # Training runs on a GPU shared with other projects' workers; cut allocator
    # fragmentation so the little VRAM left over goes further.
    env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
    env["PYTHONPATH"] = f"{RVC_ROOT}{os.pathsep}{env.get('PYTHONPATH', '')}"
    out_log.parent.mkdir(parents=True, exist_ok=True)
    with open(out_log, "ab") as out:
        proc = subprocess.Popen(
            # -P: don't prepend the script's own dir to sys.path. Otherwise
            # `python train/preprocess.py` makes `import train` resolve to the
            # sibling module train/train.py instead of the train/ package
            # (circular-import crash); with -P, PYTHONPATH's rvc_engine root
            # wins and every script's absolute imports resolve as intended.
            [sys.executable, "-P", *args],
            cwd=RVC_ROOT,
            env=env,
            stdout=out,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            while proc.poll() is None:
                if should_cancel():
                    _kill(proc)
                    raise TrainingCancelled()
                if on_tick:
                    on_tick()
                time.sleep(2)
        except BaseException:
            if proc.poll() is None:
                _kill(proc)
            raise
    return proc.returncode


def dataset_seconds(dataset_dir: Path) -> float:
    import soundfile as sf

    total = 0.0
    for p in dataset_dir.glob("*.wav"):
        info = sf.info(str(p))
        total += info.frames / info.samplerate
    return total


def preprocess(exp_name: str, dataset_dir: Path, sample_rate: str, should_cancel: ShouldCancel) -> int:
    exp = exp_path(exp_name)
    n_p = max(1, min(4, os.cpu_count() or 1))
    rc = run_script(
        ["train/preprocess.py", str(dataset_dir), str(SR_INT[sample_rate]), str(n_p), str(exp), "False", "3.7"],
        exp / "preprocess.out.log",
        should_cancel,
    )
    slices = _stems(exp / "0_gt_wavs", ".wav") & _stems(exp / "1_16k_wavs", ".wav")
    if rc != 0 or not slices:
        raise TrainingFailed(
            "TRAIN_PREPROCESS_FAILED",
            "학습 데이터 전처리에 실패했습니다 — 음원에 목소리가 거의 없거나 너무 짧을 수 있습니다.\n"
            + _tail(exp / "preprocess.log", 10),
        )
    return len(slices)


def extract_features(exp_name: str, should_cancel: ShouldCancel, on_progress: Callable[[float], None]) -> None:
    exp = exp_path(exp_name)
    total = max(1, len(_stems(exp / "1_16k_wavs", ".wav")))
    out_log = exp / "extract.out.log"

    rc = run_script(
        ["train/dataset/extract_f0.py", "cuda", "1", "0", "0", str(exp), "False"],
        out_log,
        should_cancel,
        on_tick=lambda: on_progress(50 * len(_stems(exp / "2b-f0nsf", ".npy")) / total),
    )
    if rc != 0:
        raise TrainingFailed("TRAIN_EXTRACT_FAILED", "음정(F0) 추출에 실패했습니다.\n" + _tail(out_log, 15))

    rc = run_script(
        ["train/dataset/extract_hubert_feature.py", "cuda", "1", "0", "0", str(exp), "v2", "False"],
        out_log,
        should_cancel,
        on_tick=lambda: on_progress(50 + 50 * len(_stems(exp / "3_feature768", ".npy")) / total),
    )
    usable = (
        _stems(exp / "1_16k_wavs", ".wav")
        & _stems(exp / "2a_f0", ".npy")
        & _stems(exp / "2b-f0nsf", ".npy")
        & _stems(exp / "3_feature768", ".npy")
    )
    if rc != 0 or not usable:
        raise TrainingFailed("TRAIN_EXTRACT_FAILED", "음성 특징 추출에 실패했습니다.\n" + _tail(out_log, 15))


def write_filelist_and_config(exp_name: str, sample_rate: str) -> int:
    """Same filelist/config webui's run_train_model() writes for a single
    speaker (speaker id 0), including the two `mute` lines it always adds."""
    exp = exp_path(exp_name)
    gt, feat, f0, f0nsf = exp / "0_gt_wavs", exp / "3_feature768", exp / "2a_f0", exp / "2b-f0nsf"
    names = _stems(gt, ".wav") & _stems(feat, ".npy") & _stems(f0, ".npy") & _stems(f0nsf, ".npy")
    lines = [f"{gt}/{n}.wav|{feat}/{n}.npy|{f0}/{n}.wav.npy|{f0nsf}/{n}.wav.npy|0" for n in sorted(names)]
    mute = LOGS_ROOT / "mute"
    for _ in range(2):
        lines.append(
            f"{mute}/0_gt_wavs/mute{sample_rate}.wav|{mute}/3_feature768/mute.npy"
            f"|{mute}/2a_f0/mute.wav.npy|{mute}/2b-f0nsf/mute.wav.npy|0"
        )
    shuffle(lines)
    (exp / "filelist.txt").write_text("\n".join(lines), encoding="utf8")

    config_path = exp / "config.json"
    if not config_path.exists():
        template = json.loads((RVC_ROOT / "configs" / CONFIG_TEMPLATE[sample_rate]).read_text(encoding="utf8"))
        template.pop("speaker_info", None)
        config_path.write_text(json.dumps(template, ensure_ascii=False, indent=4, sort_keys=True) + "\n", encoding="utf8")
    return len(names)


def last_epoch(exp_name: str) -> tuple[int, float | None]:
    """(latest finished epoch, average seconds per epoch over the last few)."""
    matches = EPOCH_RE.findall(_tail(exp_path(exp_name) / "train.log", 400))
    if not matches:
        return 0, None
    recent = [int(h) * 3600 + int(m) * 60 + float(s) for _, h, m, s in matches[-10:]]
    return int(matches[-1][0]), sum(recent) / len(recent)


def train(
    exp_name: str,
    sample_rate: str,
    epochs: int,
    batch_size: int,
    should_cancel: ShouldCancel,
    on_epoch: Callable[[int, float | None, int], None],
) -> int:
    """Runs train.py; on a CUDA OOM, halves the batch size and reruns —
    train.py resumes from the latest G/D checkpoint in the experiment dir, so
    only the epochs since the last save are repeated. Returns the batch size
    that finally worked."""
    exp = exp_path(exp_name)
    weight = WEIGHTS_DIR / f"{exp_name}.pth"
    out_log = exp / "train.out.log"
    # Checkpoint often enough that an OOM retry or a crash loses little work.
    save_every = max(1, min(10, epochs // 10 or 1))
    bs = batch_size

    while True:
        offset = out_log.stat().st_size if out_log.exists() else 0
        rc = run_script(
            [
                "train/train.py",
                "-e", exp_name,
                "-sr", sample_rate,
                "-f0", "1",
                "-bs", str(bs),
                "-g", "0",
                "-te", str(epochs),
                "-se", str(save_every),
                "-pg", f"assets/pretrained_v2/f0G{sample_rate}.pth",
                "-pd", f"assets/pretrained_v2/f0D{sample_rate}.pth",
                "-l", "1",
                "-c", "0",
                "-sw", "0",
                "-v", "v2",
            ],
            out_log,
            should_cancel,
            on_tick=lambda: on_epoch(*last_epoch(exp_name), bs),
        )
        if rc == 0 and weight.is_file():
            return bs

        with open(out_log, "rb") as f:
            f.seek(offset)
            run_output = f.read().decode("utf8", errors="replace")
        if "out of memory" in run_output.lower() and bs > 1:
            bs = max(1, bs // 2)
            with open(out_log, "a", encoding="utf8") as f:
                f.write(f"\n[ai-voice-cover] GPU 메모리 부족 — batch size를 {bs}(으)로 줄여 이어서 학습합니다.\n")
            continue
        if "out of memory" in run_output.lower():
            raise TrainingFailed(
                "TRAIN_OOM",
                "GPU 메모리가 부족합니다 (batch size 1에서도 실패). 다른 GPU 프로그램을 멈춘 뒤 다시 시도해주세요.",
            )
        raise TrainingFailed("TRAIN_FAILED", "모델 학습이 실패했습니다.\n" + "\n".join(run_output.splitlines()[-15:]))


def build_index(exp_name: str, should_cancel: ShouldCancel) -> Path:
    """Builds the FAISS retrieval index. outside_index_root is pointed at the
    experiment dir itself so train_index.py's symlink-into-an-external-dir
    step is a no-op — a symlink to a container-internal path would dangle for
    the api container and the host; the caller copies the index instead."""
    exp = exp_path(exp_name)
    n_cpu = max(1, min(4, os.cpu_count() or 1))
    rc = run_script(
        ["train/train_index.py", exp_name, "v2", str(exp), str(n_cpu), "single"],
        exp / "index.out.log",
        should_cancel,
    )
    added = sorted(exp.glob(f"added_IVF*_Flat_nprobe_*_{exp_name}_v2.index"), key=lambda p: p.stat().st_mtime)
    if rc != 0 or not added:
        raise TrainingFailed("TRAIN_INDEX_FAILED", "검색 인덱스 생성에 실패했습니다.\n" + _tail(exp / "train_index.log", 10))
    return added[-1]

