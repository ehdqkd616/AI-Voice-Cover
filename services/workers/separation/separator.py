"""Vocal/instrumental separation.

`DEMUCS_DEVICE` is configurable via .env — set it to "cpu" to run without a
GPU (see .env.example's note on the host's current driver mismatch).

torch/torchaudio/demucs are imported lazily inside each function, not at
module level. `workers/tasks/__init__.py` imports every task module — including
this one, transitively, via tasks/cover.py — in every worker process so
Celery can register all tasks. The download/dsp/beat containers only install
the lightweight base requirements (no torch), so a module-level `import torch`
here would crash their startup even though they never execute this code
(they never consume from the `separate` queue).
"""

from common.config import get_settings

_MODEL_CACHE: dict[str, object] = {}


def _device() -> str:
    return get_settings().demucs_device


def load_model(name: str):
    """Loaded once per worker process lifetime (kept resident in memory)."""
    from demucs.pretrained import get_model

    if name not in _MODEL_CACHE:
        model = get_model(name)
        model.to(_device()).eval()
        _MODEL_CACHE[name] = model
    return _MODEL_CACHE[name]


def separate(audio_path: str, model_name: str, stems: int) -> dict:
    import torch
    import torchaudio
    from demucs.apply import apply_model

    model = load_model(model_name)

    with torch.no_grad():
        wav, sr = torchaudio.load(audio_path)
        if sr != model.samplerate:
            wav = torchaudio.functional.resample(wav, sr, model.samplerate)
        if wav.shape[0] == 1:  # mono → stereo
            wav = wav.repeat(2, 1)

        ref = wav.mean(0)
        mean, std = ref.mean(), ref.std()
        wav = (wav - mean) / (std + 1e-8)

        sources = apply_model(
            model,
            wav[None],
            device=_device(),
            shifts=1,
            split=True,
            overlap=0.25,
            segment=7,  # VRAM/RAM lever — lower if the process gets OOM-killed
            progress=False,
        )[0]

        sources = sources * std + mean
        result = dict(zip(model.sources, sources))

    if stems == 2:
        # Instrumental = full mix minus vocals. Residual sum has fewer artifacts
        # than mixing the other three stems back together.
        instrumental = sum(v for k, v in result.items() if k != "vocals")
        return {"vocals": result["vocals"], "instrumental": instrumental}

    return result


def save_stem(tensor, path: str, sample_rate: int) -> None:
    import torchaudio

    torchaudio.save(path, tensor.cpu(), sample_rate)
