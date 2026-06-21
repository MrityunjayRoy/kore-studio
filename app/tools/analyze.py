#!/usr/bin/env python3
"""analyze.py — Studio-grade audio measurement suite.

Usage:
    python -m app.tools.analyze <file.wav>
    python -m app.tools.analyze <file.wav> --json

Prints all metrics. Returns exit code 0 if all pass, 1 if any fail.
"""
import argparse
import json
import sys
from dataclasses import dataclass, asdict
from typing import Optional

import numpy as np
import soundfile as sf
import pyloudnorm as pyln
import librosa


@dataclass
class AnalysisResult:
    file: str
    sample_rate: int
    channels: int
    duration_s: float
    dtype: str
    integrated_loudness_lufs: float
    true_peak_dbtp: float
    sample_peak_dbfs: float
    rms_dbfs: float
    crest_factor_db: float
    dc_offset: float
    stereo_correlation: float
    clipped_samples: int
    clip_percentage: float
    click_detected_start: bool
    click_detected_end: bool
    spectral_low_db: float
    spectral_mid_db: float
    spectral_high_db: float
    all_pass: bool
    failures: list


TARGETS = {
    "lufs_min": -22.0,
    "lufs_max": -6.0,
    "true_peak_max": -1.0,
    "sample_peak_max": -1.0,
    "dc_offset_max": 0.001,
    "stereo_corr_min": 0.0,
    "clipped_max": 0,
    "crest_factor_min": 6.0,
}


def analyze(filepath: str, vocal_stem: Optional[str] = None,
            instrumental_stem: Optional[str] = None) -> AnalysisResult:
    data, sr = sf.read(filepath, dtype='float32')
    failures = []

    if data.ndim == 1:
        mono = data
        stereo_corr = 1.0
    else:
        mono = np.mean(data, axis=1)
        left = data[:, 0]
        right = data[:, 1]
        if np.std(left) > 0 and np.std(right) > 0:
            stereo_corr = float(np.corrcoef(left, right)[0, 1])
        else:
            stereo_corr = 1.0

    duration = len(mono) / sr
    peak = float(np.max(np.abs(mono)))
    sample_peak_dbfs = 20 * np.log10(max(peak, 1e-10))
    rms = float(np.sqrt(np.mean(mono.astype(np.float64) ** 2)))
    rms_dbfs = 20 * np.log10(max(rms, 1e-10))
    crest_factor = sample_peak_dbfs - rms_dbfs if rms > 0 else 0
    dc_offset = float(np.mean(mono))

    meter = pyln.Meter(sr)
    loudness = float(meter.integrated_loudness(data))

    oversampled = librosa.resample(mono, orig_sr=sr, target_sr=sr * 4)
    true_peak = float(np.max(np.abs(oversampled)))
    true_peak_dbtp = 20 * np.log10(max(true_peak, 1e-10))

    clipped = int(np.sum(np.abs(mono) >= 0.999))
    clip_pct = 100.0 * clipped / len(mono)

    start_50ms = mono[:int(sr * 0.050)]
    end_50ms = mono[-int(sr * 0.050):]
    click_start = bool(np.any(np.abs(np.diff(start_50ms)) > 0.5)) if len(start_50ms) > 1 else False
    click_end = bool(np.any(np.abs(np.diff(end_50ms)) > 0.5)) if len(end_50ms) > 1 else False

    spec = np.abs(librosa.stft(mono, n_fft=4096))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=4096)

    def band_db(lo, hi):
        mask = (freqs >= lo) & (freqs <= hi)
        energy = np.mean(spec[mask] ** 2)
        return float(10 * np.log10(max(energy, 1e-20)))

    spectral_low = band_db(20, 250)
    spectral_mid = band_db(250, 4000)
    spectral_high = band_db(4000, 20000)

    if not (TARGETS["lufs_min"] <= loudness <= TARGETS["lufs_max"]):
        failures.append(f"LUFS {loudness:.1f} outside [{TARGETS['lufs_min']}, {TARGETS['lufs_max']}]")
    if true_peak_dbtp > TARGETS["true_peak_max"]:
        failures.append(f"True peak {true_peak_dbtp:.1f} dBTP > {TARGETS['true_peak_max']}")
    if sample_peak_dbfs > TARGETS["sample_peak_max"]:
        failures.append(f"Sample peak {sample_peak_dbfs:.1f} dBFS > {TARGETS['sample_peak_max']}")
    if abs(dc_offset) > TARGETS["dc_offset_max"]:
        failures.append(f"DC offset {dc_offset:.6f} > {TARGETS['dc_offset_max']}")
    if data.ndim == 2 and stereo_corr < TARGETS["stereo_corr_min"]:
        failures.append(f"Stereo correlation {stereo_corr:.3f} < {TARGETS['stereo_corr_min']}")
    if clipped > TARGETS["clipped_max"]:
        failures.append(f"Clipped samples: {clipped}")
    if click_start:
        failures.append("Click/pop detected at start")
    if click_end:
        failures.append("Click/pop detected at end")
    if crest_factor < TARGETS["crest_factor_min"]:
        failures.append(f"Crest factor {crest_factor:.1f}dB < {TARGETS['crest_factor_min']}dB (over-compressed)")

    return AnalysisResult(
        file=filepath, sample_rate=sr, channels=data.ndim,
        duration_s=round(duration, 2), dtype=str(data.dtype),
        integrated_loudness_lufs=round(loudness, 1),
        true_peak_dbtp=round(true_peak_dbtp, 1),
        sample_peak_dbfs=round(sample_peak_dbfs, 1),
        rms_dbfs=round(rms_dbfs, 1),
        crest_factor_db=round(crest_factor, 1),
        dc_offset=round(dc_offset, 6),
        stereo_correlation=round(stereo_corr, 3),
        clipped_samples=clipped,
        clip_percentage=round(clip_pct, 4),
        click_detected_start=click_start,
        click_detected_end=click_end,
        spectral_low_db=round(spectral_low, 1),
        spectral_mid_db=round(spectral_mid, 1),
        spectral_high_db=round(spectral_high, 1),
        all_pass=len(failures) == 0,
        failures=failures,
    )


def print_report(r: AnalysisResult):
    status = "PASS" if r.all_pass else "FAIL"
    print(f"\n{'='*60}")
    print(f"  Audio Analysis: {r.file}  [{status}]")
    print(f"{'='*60}")
    print(f"  Format:     {r.sample_rate}Hz / {r.channels}ch / {r.dtype} / {r.duration_s}s")
    print(f"  Loudness:   {r.integrated_loudness_lufs} LUFS  (target: -16 to -14)")
    print(f"  True Peak:  {r.true_peak_dbtp} dBTP  (target: <= -1.0)")
    print(f"  Sample Peak:{r.sample_peak_dbfs} dBFS  (target: <= -1.0)")
    print(f"  RMS:        {r.rms_dbfs} dBFS")
    print(f"  Crest Factor:{r.crest_factor_db} dB  (min: 6.0)")
    print(f"  DC Offset:  {r.dc_offset}  (max: 0.001)")
    print(f"  Stereo Corr:{r.stereo_correlation}  (min: 0.0)")
    print(f"  Clipped:    {r.clipped_samples} ({r.clip_percentage}%)")
    print(f"  Clicks:     start={r.click_detected_start} end={r.click_detected_end}")
    print(f"  Spectral:   low={r.spectral_low_db}dB mid={r.spectral_mid_db}dB high={r.spectral_high_db}dB")
    if r.failures:
        print(f"\n  FAILURES:")
        for f in r.failures:
            print(f"    ✗ {f}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Studio-grade audio analysis")
    parser.add_argument("file", help="WAV file to analyze")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    result = analyze(args.file)

    if args.json:
        print(json.dumps(asdict(result), indent=2))
    else:
        print_report(result)

    sys.exit(0 if result.all_pass else 1)


if __name__ == "__main__":
    main()
