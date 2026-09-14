"""Thin integration wrapper around the vendored RVC inference engine
(services/workers/rvc_engine/, see that directory's LICENSE).

torch/faiss/transformers-backed imports (`configs.config`, `infer.vc.modules`,
...) are deferred inside functions, never at module level — same lazy-import
discipline as separation/separator.py. `workers/tasks/__init__.py` imports
every task module (including this one, transitively, via tasks/cover.py) in
every worker process so Celery can register all tasks; the download/dsp/beat
containers never install torch/transformers/faiss, so a module-level import
here would crash their startup even though they never touch the convert queue.

Two CWD/path gotchas from the vendored code (see rvc_engine's internal
imports — `infer/vc/utils.py`'s `get_index_path_from_model` and
`i18n/i18n.py`'s `I18nAuto` both resolve `./i18n/locale/{lang}.json` and
similar paths relative to the process's CURRENT WORKING DIRECTORY, not
`__file__`):

  1. Primary fix: services/workers/Dockerfile.gpu sets `WORKDIR` to this
     vendored `rvc_engine/` directory right before its CMD, so the worker
     container's CWD is correct for the whole process lifetime.
  2. Belt-and-suspenders here: `_ensure_engine_importable()` also inserts
     `rvc_engine` onto `sys.path` (needed either way — `rvc_engine` is a
     PYTHONPATH root, not an installed package, and the Dockerfile's
     `ENV PYTHONPATH` covers the container case but not a bare `python -m`
     smoke-test run from the repo root) and `os.chdir()`s into it if the
     i18n locale file isn't already resolvable from the current CWD. This
     makes the module self-sufficient when run standalone (e.g. the smoke
     test below) without redundantly chdir-ing in the normal Docker path
     (WORKDIR already put us there, so the check is a no-op).
"""

import os
import sys
from pathlib import Path

import numpy as np

from common.config import get_settings
from common.db.models import VoiceModel

_VC_CACHE: dict[str, object] = {}  # keyed by VoiceModel.id — reused across requests in this worker process
_config_singleton = None
_engine_ready = False


def _rvc_root() -> str:
    # services/workers/convert/engine.py -> services/workers/rvc_engine
    return str(Path(__file__).resolve().parent.parent / "rvc_engine")


def _ensure_engine_importable() -> None:
    """Make `infer`/`configs`/`i18n`/`tools` importable and CWD-correct.

    Idempotent — safe to call from every entry point below before the first
    `infer.*`/`configs.*` import in this process.
    """
    global _engine_ready
    if _engine_ready:
        return
    root = _rvc_root()
    if root not in sys.path:
        sys.path.insert(0, root)
    # Only chdir if the vendored i18n locale isn't already reachable relative
    # to the current CWD (i.e. the Dockerfile's WORKDIR didn't already put us
    # there) — avoids a redundant/surprising chdir in the normal container path.
    if not os.path.isfile(os.path.join(os.getcwd(), "i18n", "locale", "en_US.json")):
        os.chdir(root)
    _engine_ready = True


def _create_config():
    """RVC's Config parses sys.argv via argparse — swap it out before instantiating,
    exactly like infer/cli.py::create_config() does, or Celery's own argv breaks it."""
    global _config_singleton
    if _config_singleton is None:
        _ensure_engine_importable()
        from configs.config import Config

        saved, sys.argv = sys.argv, sys.argv[:1]
        try:
            _config_singleton = Config()
        finally:
            sys.argv = saved
    return _config_singleton


def get_vc(voice_model: VoiceModel):
    if voice_model.id not in _VC_CACHE:
        settings = get_settings()
        _ensure_engine_importable()
        # Must be set before infer.vc.utils (imported transitively by
        # infer.vc.modules) is first imported in this process — get_index_path_from_model
        # reads outside_index_root/index_root via os.getenv() at call time, but
        # they still need to be in the environment before that first call.
        os.environ["weight_root"] = settings.rvc_weight_root
        os.environ["index_root"] = settings.rvc_index_root
        os.environ["outside_index_root"] = settings.rvc_index_root
        # rmvpe_root is read lazily inside Pipeline.get_f0() on first pitch
        # extraction, not at import time, but set it here anyway for clarity.
        os.environ["rmvpe_root"] = os.path.join(_rvc_root(), "assets", "rmvpe")

        from infer.vc.modules import VC

        vc = VC(_create_config())
        vc.get_vc(voice_model.weight_filename)
        _VC_CACHE[voice_model.id] = vc
    return _VC_CACHE[voice_model.id]


def convert_vocal(
    voice_model: VoiceModel,
    input_wav_path: str,
    f0_up_key: int,
    f0_method: str,
    index_rate: float,
    protect: float,
    rms_mix_rate: float,
) -> tuple[int, "np.ndarray"]:
    vc = get_vc(voice_model)
    settings = get_settings()
    index_path = (
        os.path.join(settings.rvc_index_root, voice_model.index_filename)
        if voice_model.index_filename
        else ""
    )
    status, (sr, audio) = vc.vc_single(
        voice_model.speaker_id,
        input_wav_path,
        f0_up_key,
        f0_method,
        index_path,
        index_rate,
        0,  # resample_sr — 0 means "don't resample", keep the model's target sample rate
        rms_mix_rate,
        protect,
    )
    if sr is None or audio is None:
        raise RuntimeError(f"RVC conversion failed: {status}")
    return sr, audio
