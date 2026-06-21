#!/usr/bin/env python3
"""compare.py — Compare two WAV files against studio-grade metrics.

Usage:
    python -m app.tools.compare baseline.wav processed.wav
"""
import argparse
import sys

from app.tools.analyze import analyze, print_report


def compare(file_a: str, file_b: str):
    a = analyze(file_a)
    b = analyze(file_b)

    print(f"\n{'='*70}")
    print(f"  COMPARISON: {a.file} vs {b.file}")
    print(f"{'='*70}")
    print(f"  {'Metric':<25} {'Baseline':>15} {'Processed':>15} {'Delta':>12}")
    print(f"  {'-'*67}")

    fields = [
        ("Loudness (LUFS)", a.integrated_loudness_lufs, b.integrated_loudness_lufs, True),
        ("True Peak (dBTP)", a.true_peak_dbtp, b.true_peak_dbtp, True),
        ("Sample Peak (dBFS)", a.sample_peak_dbfs, b.sample_peak_dbfs, True),
        ("RMS (dBFS)", a.rms_dbfs, b.rms_dbfs, True),
        ("Crest Factor (dB)", a.crest_factor_db, b.crest_factor_db, True),
        ("DC Offset", a.dc_offset, b.dc_offset, False),
        ("Stereo Correlation", a.stereo_correlation, b.stereo_correlation, False),
        ("Clipped Samples", a.clipped_samples, b.clipped_samples, False),
        ("Spectral Low (dB)", a.spectral_low_db, b.spectral_low_db, True),
        ("Spectral Mid (dB)", a.spectral_mid_db, b.spectral_mid_db, True),
        ("Spectral High (dB)", a.spectral_high_db, b.spectral_high_db, True),
    ]

    for name, va, vb, show_delta in fields:
        if show_delta and isinstance(va, (int, float)):
            delta = vb - va
            d_str = f"{delta:+.1f}"
        else:
            d_str = ""
        print(f"  {name:<25} {str(va):>15} {str(vb):>15} {d_str:>12}")

    print(f"\n  Baseline status:  {'PASS' if a.all_pass else 'FAIL'} ({len(a.failures)} failures)")
    print(f"  Processed status: {'PASS' if b.all_pass else 'FAIL'} ({len(b.failures)} failures)")

    if b.failures:
        print(f"\n  Processed FAILURES:")
        for f in b.failures:
            print(f"    ✗ {f}")

    if a.failures and not b.failures:
        print(f"\n  ✓ All baseline failures resolved!")
    print()


def main():
    parser = argparse.ArgumentParser(description="Compare two WAV files")
    parser.add_argument("baseline", help="Baseline WAV file")
    parser.add_argument("processed", help="Processed WAV file")
    args = parser.parse_args()

    compare(args.baseline, args.processed)


if __name__ == "__main__":
    main()
