"""Standalone smoke test for services/workers/convert/engine.py.

Exercises get_vc() + convert_vocal() against a real vendored RVC voice model
and a short synthetic test WAV, without touching Postgres/Redis/MinIO — the
VoiceModel row is constructed in-memory here, never queried from a DB session,
so this can run with none of the docker-compose infra up.

Run with a Python environment that has RVC's inference deps installed
(torch/transformers/faiss/parselmouth/av/ffmpeg-python/soundfile/librosa/...),
from anywhere, e.g.:

    python3 services/workers/convert/_smoke_test.py \
        --weight-root /path/to/rvc/assets/weights --model IU.pth

Not wired into any test runner — this is the manual, one-off verification
tool called for by the AI-Voice-Cover build spec (Part C), safe to delete
once Part C has been verified working end to end.
"""

import argparse
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

# services/ on sys.path so `common` and `workers` import regardless of CWD —
# this file lives at services/workers/convert/_smoke_test.py.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _make_test_wav(path: str, seconds: float = 2.5, sr: int = 44100) -> None:
    """Synthetic short 'vocal-like' signal: a wavering fundamental + harmonics,
    not silence or a pure tone, so RVC's f0 extractor has something to track."""
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    vibrato = 6 * np.sin(2 * np.pi * 5 * t)  # slight pitch wobble, Hz
    f0 = 180 + vibrato
    phase = 2 * np.pi * np.cumsum(f0) / sr
    signal = 0.6 * np.sin(phase) + 0.25 * np.sin(2 * phase) + 0.1 * np.sin(3 * phase)
    envelope = np.clip(np.minimum(t, seconds - t) * 8, 0, 1)  # fade in/out, avoid clicks
    signal *= envelope
    sf.write(path, signal.astype(np.float32), sr)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weight-root", required=True, help="Directory containing .pth voice models")
    parser.add_argument("--index-root", default="", help="Directory containing .index files (optional)")
    parser.add_argument("--model", required=True, help="Weight filename, e.g. IU.pth")
    parser.add_argument("--speaker-id", type=int, default=0)
    parser.add_argument("--f0-method", default="rmvpe", choices=["pm", "rmvpe", "fcpe"])
    parser.add_argument("--index-rate", type=float, default=0.0)
    parser.add_argument("--keep-output", help="Optional path to copy the converted WAV to for manual listening")
    args = parser.parse_args()

    # Must be set before common.config.get_settings() is first called.
    os.environ["RVC_WEIGHT_ROOT"] = args.weight_root
    os.environ["RVC_INDEX_ROOT"] = args.index_root or args.weight_root

    from common.config import get_settings
    from common.db.models import VoiceModel
    from workers.convert.engine import convert_vocal

    settings = get_settings()
    print(f"weight_root={settings.rvc_weight_root} index_root={settings.rvc_index_root}")

    voice_model = VoiceModel(
        id="vm_smoketest",
        name="smoke-test",
        weight_filename=args.model,
        index_filename=None,
        version="v2",
        sample_rate=40000,
        has_f0=True,
        speaker_id=args.speaker_id,
        is_active=True,
    )

    with tempfile.TemporaryDirectory(prefix="rvc_smoke_") as work_dir:
        in_wav = os.path.join(work_dir, "test_input.wav")
        _make_test_wav(in_wav)
        print(f"wrote synthetic test input: {in_wav}")

        sr, audio = convert_vocal(
            voice_model,
            in_wav,
            f0_up_key=0,
            f0_method=args.f0_method,
            index_rate=args.index_rate,
            protect=settings.rvc_default_protect,
            rms_mix_rate=settings.rvc_default_rms_mix_rate,
        )

        out_wav = os.path.join(work_dir, "test_output.wav")
        sf.write(out_wav, audio, sr)
        if args.keep_output:
            sf.write(args.keep_output, audio, sr)
            print(f"copied output to {args.keep_output}")

        peak = float(np.abs(audio).max()) if audio.size else 0.0
        rms = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2))) if audio.size else 0.0
        print(f"output sr={sr} samples={audio.size} dtype={audio.dtype} peak={peak:.1f} rms={rms:.1f}")
        if peak == 0.0:
            print("FAIL: output is silent")
            return 1
        print("OK: non-silent audio produced")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
