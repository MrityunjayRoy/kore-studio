# Phase 2: Baseline Scores

## Test Harness

| Tool | Status | Location |
|------|--------|----------|
| `analyze.py` | ✅ Built | `app/tools/analyze.py` |
| `compare.py` | ✅ Built | `app/tools/compare.py` |
| `test_pipeline.py` | ✅ 18/18 passing | `tests/test_pipeline.py` |

## Baseline File Analysis: kore_studio_output.wav

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Integrated Loudness | -10.5 LUFS | -16 to -14 | ❌ FAIL (too loud) |
| True Peak | -0.3 dBTP | ≤ -1.0 | ❌ FAIL (too hot) |
| Sample Peak | -0.6 dBFS | ≤ -1.0 | ❌ FAIL (too hot) |
| RMS | -14.4 dBFS | N/A | ℹ️ |
| Crest Factor | 13.8 dB | ≥ 6.0 | ✅ PASS |
| DC Offset | -0.000085 | < 0.001 | ✅ PASS |
| Stereo Correlation | 0.317 | > 0.0 | ✅ PASS |
| Clipped Samples | 0 | 0 | ✅ PASS |
| Click Start | False | False | ✅ PASS |
| Click End | False | False | ✅ PASS |

## Priority Fixes Identified

1. **Limiter not catching peaks** — true peak at -0.3 dBTP means limiter threshold needs to be lower or applied earlier
2. **Loudness normalization boosting too much** — -10.5 LUFS is way above -14 target; pyloudnorm is boosting a quiet mix to hit target, pushing peaks above ceiling
3. **Gain staging order wrong** — loudness normalize THEN limit, not limit then normalize

## Test Suite Coverage

| Area | Tests | Status |
|------|-------|--------|
| clean_vocal | 7 | ✅ All pass |
| NoiseGate | 3 | ✅ All pass |
| Effects chain | 3 | ✅ All pass |
| Vocal doubler | 2 | ✅ All pass |
| Mix balance | 1 | ✅ All pass |
| Export format | 2 | ✅ All pass |
