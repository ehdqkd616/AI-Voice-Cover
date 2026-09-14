"""UVR-MDX-NET separation via the `audio-separator` package — isolated in its
own worker container/venv (see services/workers/Dockerfile.mdx and
requirements-mdx.txt for why: audio-separator pulls in a much newer torch
than the RVC engine is pinned/verified against, so it can't safely share
worker-separate-convert's environment without risking pip silently upgrading
torch out from under RVC).

CPU-only inference (requirements-mdx.txt installs plain `onnxruntime`, not
`onnxruntime-gpu`) — this container never competes with Demucs/RVC for the
host's single 4GB GPU.

Like separation/separator.py, the heavy import (`audio_separator`) is
deferred inside functions, not at module level — workers/tasks/__init__.py
imports every task module (including this one, transitively, via
tasks/cover.py) in every worker process so Celery can register all task
names, and worker-separate-convert/worker-dsp/worker-download never install
audio-separator.
"""

import os

MODEL_FILENAME = "Kim_Vocal_2.onnx"  # the modern successor to "UVR-MDX-NET Voc FT"

_SEPARATOR_CACHE: dict[str, object] = {}


def _get_separator(output_dir: str):
    from audio_separator.separator import Separator

    if MODEL_FILENAME not in _SEPARATOR_CACHE:
        sep = Separator(output_dir=output_dir, output_format="WAV")
        sep.load_model(model_filename=MODEL_FILENAME)
        _SEPARATOR_CACHE[MODEL_FILENAME] = sep
    else:
        sep = _SEPARATOR_CACHE[MODEL_FILENAME]
        sep.output_dir = output_dir  # each job writes into its own tempdir
    return sep


def separate_mdx(audio_path: str, output_dir: str) -> dict[str, str]:
    """Runs UVR-MDX-NET separation, returns {"vocals": path, "instrumental": path}."""
    sep = _get_separator(output_dir)
    sep.separate(audio_path, custom_output_names={"Vocals": "vocals", "Instrumental": "instrumental"})
    return {
        "vocals": os.path.join(output_dir, "vocals.wav"),
        "instrumental": os.path.join(output_dir, "instrumental.wav"),
    }
