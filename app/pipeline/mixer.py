import argparse

import librosa
import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from pedalboard import Limiter, Pedalboard

TARGET_SR = 48000


def peak_normalize(audio: np.ndarray, target_dbfs: float) -> np.ndarray:
    peak = np.max(np.abs(audio))
    if peak == 0:
        return audio
    gain = 10 ** (target_dbfs / 20) / peak
    return audio * gain


def match_channels(vocal: np.ndarray, karaoke: np.ndarray):
    if vocal.ndim == 1 and karaoke.ndim == 2:
        vocal = np.column_stack([vocal, vocal])
    elif karaoke.ndim == 1 and vocal.ndim == 2:
        karaoke = np.column_stack([karaoke, karaoke])
    return vocal, karaoke


def mix(vocals_path: str, karaoke_path: str, output_path: str,
        vocal_target: float, karaoke_target: float,
        loudness_target: float, true_peak: float):
    vocal, sr_v = sf.read(vocals_path)
    karaoke, sr_k = sf.read(karaoke_path)

    if sr_v != TARGET_SR:
        vocal = librosa.resample(vocal.T, orig_sr=sr_v, target_sr=TARGET_SR).T
    if sr_k != TARGET_SR:
        karaoke = librosa.resample(karaoke.T, orig_sr=sr_k, target_sr=TARGET_SR).T
    sr = TARGET_SR

    vocal, karaoke = match_channels(vocal, karaoke)

    vocal = peak_normalize(vocal, vocal_target)
    karaoke = peak_normalize(karaoke, karaoke_target)

    min_len = min(len(vocal), len(karaoke))
    vocal = vocal[:min_len]
    karaoke = karaoke[:min_len]

    mixed = vocal + karaoke
    mixed = np.clip(mixed, -1.0, 1.0)

    meter = pyln.Meter(sr)
    loudness = meter.integrated_loudness(mixed)
    mixed = pyln.normalize.loudness(mixed, loudness, loudness_target)

    if mixed.ndim == 2:
        mixed_fmt = mixed.T.copy()
    else:
        mixed_fmt = mixed[np.newaxis, :].copy()

    limiter = Limiter(threshold_db=true_peak, release_ms=100)
    limited = limiter(mixed_fmt, sample_rate=sr)

    if mixed.ndim == 2:
        limited = limited.T
    else:
        limited = limited[0]

    sf.write(output_path, limited, sr, subtype="PCM_24")
    print(f"Mixed audio saved to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Mix processed vocals with karaoke track and normalize loudness"
    )
    parser.add_argument("vocals", help="Path to processed vocals file")
    parser.add_argument("karaoke", help="Path to karaoke / instrumental file")
    parser.add_argument("-o", "--output", default="mixed.wav",
                        help="Output path (default: mixed.wav)")

    parser.add_argument("--vocal-target", type=float, default=-9.0,
                        help="Target peak for vocals in dBFS (default: -9)")
    parser.add_argument("--karaoke-target", type=float, default=-13.0,
                        help="Target peak for karaoke in dBFS (default: -13)")
    parser.add_argument("--loudness-target", type=float, default=-14.0,
                        help="Target integrated loudness in LUFS (default: -14)")
    parser.add_argument("--true-peak", type=float, default=-1.0,
                        help="True peak ceiling in dB (default: -1.0)")

    args = parser.parse_args()
    mix(args.vocals, args.karaoke, args.output,
        args.vocal_target, args.karaoke_target,
        args.loudness_target, args.true_peak)
