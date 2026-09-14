"""Final mix stage: converted vocal + original instrumental -> one WAV.

Deliberately modest — no AI mastering, no DTW/cross-correlation resync. RVC's
pipeline can shift the vocal's sample count slightly relative to the source
(frame-boundary rounding in Pipeline.pipeline's windowed synthesis), so the
two stems are only aligned by zero-padding the shorter one out to the longer
one's length. This is a known, documented limitation: a vocal take that
drifts out of phase with its instrumental over a long track would need a
proper resync (DTW or cross-correlation windowing) to fix — not attempted
here, kept simple per spec.

IMPORTANT: the converted vocal comes back at the RVC model's own target
sample rate (`tgt_sr` — 40000/48000/32000 depending on the model), which is
frequently NOT the instrumental's sample rate (44100, Demucs' native output
rate). Summing raw samples across two different rates without resampling
first plays them back on two different time axes — the exact "vocal drifts
out of sync with the instrumental" symptom this used to produce, worse the
longer the track runs. Every array here is resampled to a single common
rate (the instrumental's) before alignment/summing.
"""

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from math import gcd
from scipy.signal import resample_poly


def _resample(x: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Polyphase resample along the time axis (axis 0); no-op if rates already match."""
    if orig_sr == target_sr:
        return x
    g = gcd(orig_sr, target_sr)
    up, down = target_sr // g, orig_sr // g
    return resample_poly(x, up, down, axis=0).astype(np.float32)


def _pitch_shift(x: np.ndarray, sr: int, semitones: int) -> np.ndarray:
    """Tempo-preserving pitch shift for the instrumental track — independent
    of the vocal's own pitch, which RVC already handles internally via
    f0_up_key. Uses librosa (already a dependency; no new apt package like
    Rubber Band needed) — per-channel since librosa's phase-vocoder shifter
    expects a 1D signal."""
    if not semitones:
        return x
    import librosa

    channels = [
        librosa.effects.pitch_shift(np.ascontiguousarray(x[:, ch]), sr=sr, n_steps=semitones)
        for ch in range(x.shape[1])
    ]
    # Framing can round each channel's output length by a sample or two —
    # trim to the shortest so channels stay aligned with each other.
    min_len = min(len(c) for c in channels)
    return np.stack([c[:min_len] for c in channels], axis=1).astype(np.float32)


def _pad_to_match(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Zero-pad the shorter of the two (in samples) to the longer one's length."""
    max_len = max(a.shape[0], b.shape[0])
    if a.shape[0] < max_len:
        a = np.pad(a, ((0, max_len - a.shape[0]), (0, 0)))
    if b.shape[0] < max_len:
        b = np.pad(b, ((0, max_len - b.shape[0]), (0, 0)))
    return a, b


def _lufs_match_gain(vocal: np.ndarray, sr: int, reference: np.ndarray, ref_sr: int) -> float:
    """Linear gain to bring `vocal`'s integrated LUFS to match `reference`'s.

    A voice-model timbre swap can noticeably change perceived loudness even
    at the same peak/RMS level (different harmonic content), so this is
    measured with ITU-R BS.1770 integrated loudness (pyloudnorm), not a
    simple peak or RMS match.
    """
    meter_vocal = pyln.Meter(sr)
    meter_ref = pyln.Meter(ref_sr)
    # mono-sum for loudness measurement — pyloudnorm expects [samples] or [samples, channels]
    vocal_lufs = meter_vocal.integrated_loudness(vocal)
    ref_lufs = meter_ref.integrated_loudness(reference)
    if not np.isfinite(vocal_lufs) or not np.isfinite(ref_lufs):
        # e.g. near-silent input measures as -inf LUFS — no sane gain to compute, leave as-is.
        return 1.0
    return float(10 ** ((ref_lufs - vocal_lufs) / 20))


def mix(
    vocal_wav_path: str,
    instrumental_wav_path: str,
    vocal_gain_db: float,
    instrumental_pitch: int,
    work_dir: str,
) -> str:
    """Loudness-matches the converted vocal against the original vocal-stem
    reference isn't available here (only vocal + instrumental) — instead
    matches the converted vocal's LUFS to the instrumental's, which keeps the
    two stems in a sane relative balance regardless of the voice model's
    native loudness, then applies the caller's vocal_gain_db on top.

    `instrumental_pitch` transposes the MR track itself (semitones, tempo
    preserved) — separate from the vocal's own pitch, which is already baked
    into the converted vocal by RVC's f0_up_key upstream.

    Returns the path to the mixed WAV (before final format encoding — the
    calling task owns encode()+upload+register_media, matching how
    Music-Tools' task functions, not their DSP helpers, own the upload step).
    """
    vocal, vocal_sr = sf.read(vocal_wav_path, always_2d=True)
    instrumental, inst_sr = sf.read(instrumental_wav_path, always_2d=True)
    vocal = vocal.astype(np.float32)
    instrumental = instrumental.astype(np.float32)

    # Bring both onto the same time axis (the instrumental's rate) before any
    # length/alignment math — see module docstring for why this is required,
    # not optional, whenever the RVC model's tgt_sr != Demucs' output rate.
    vocal = _resample(vocal, vocal_sr, inst_sr)
    vocal_sr = inst_sr

    instrumental = _pitch_shift(instrumental, inst_sr, instrumental_pitch)

    gain = _lufs_match_gain(vocal, vocal_sr, instrumental, inst_sr)
    gain *= 10 ** (vocal_gain_db / 20)
    vocal = vocal * gain

    vocal, instrumental = _pad_to_match(vocal, instrumental)

    mixed = vocal + instrumental
    peak = np.abs(mixed).max()
    if peak > 1.0:
        mixed = mixed / peak  # simple clip-safety normalization, same pattern as Music-Tools' mix_stems

    out_path = f"{work_dir}/mixed.wav"
    sf.write(out_path, mixed, inst_sr)
    return out_path
