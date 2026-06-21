# Phase 3: Capture Stage Fixes

## Fixes Implemented

### 3.1 Sample Rate & Format Consistency ✅
- Recording: fixed at 48kHz, paFloat32 (device_io.py:342-347)
- Instrumental: resampled to 48kHz on load (studio.py:882-884)
- All `sf.read()` calls now use `dtype='float32'` (studio.py:527,640,824,869)
- Internal processing: float32 throughout
- Export: PCM_24 only at final write

### 3.2 Input Gain Check ✅
- User-selectable input gain: 0.5x / 1.0x / 1.5x / 2.0x (studio.py:228-237)
- Applied in real-time during recording (device_io.py:375-379)

### 3.3 Noise Floor Handling ✅
- Noise gate **removed** from recording path (was causing voice cutouts)
- DeepFilterNet AI handles noise reduction in post-processing
- Fan noise, room tone cleaned by spectral gating, not amplitude gating

### 3.4 DC Offset Removal ✅
- Mean subtraction in `clean_vocal()` (device_io.py:156)
- Measured DC offset on output: -0.000085 (target: < 0.001) ✅

### 3.5 Click/Pop Removal at Boundaries ✅
- 20ms fade-in at start (device_io.py:158-161)
- 20ms fade-out at end (device_io.py:162-164)
- Click detection in analyze.py: start=False, end=False ✅

### 3.6 Latency Measurement & Compensation ✅ **NEW**
- `app/pipeline/latency.py` module created
- **Calibration signal**: 100ms chirp (1kHz→8kHz), generated in code
- **Measurement**: Cross-correlation via `scipy.signal.correlate`
- **Caching**: Per device-pair + sample rate + chunk size (`~/.kore_latency_cache.json`)
- **Compensation**: `apply_latency_compensation()` trims/pads vocal
- **Auto-runs** on first use of each device pair (studio.py:880-887)
- **Displayed** in pre-roll screen (studio.py:262)

### 3.7 Acoustic Bleed Mitigation ✅ **NEW**
- **Device heuristic**: `is_headphone_device()` checks name against keywords
- **CLI warning**: Bold red warning when speakers detected (studio.py:267-270)
- **Post-recording detection**: `detect_acoustic_bleed()` correlates vocal vs instrumental
- **Reports** correlation coefficient and high-corr block ratio

## Test Results

| Test | Result |
|------|--------|
| Calibration signal generation | ✅ 4800 samples, peak 0.5 |
| Latency compensation (positive offset) | ✅ 48000 → 47000 samples |
| Latency compensation (negative offset) | ✅ 48000 → 48500 samples |
| Bleed detection (uncorrelated signals) | ✅ No false positive |
| Headphone heuristic | ✅ 4/4 correct |
| Latency cache set/get | ✅ Persistent JSON |

## Files Changed

| File | Change |
|------|--------|
| `app/pipeline/latency.py` | **NEW** — latency measurement, cache, bleed detection |
| `app/cli/studio.py` | Import latency module, calibration in main(), speaker warning |
| `app/pipeline/device_io.py` | Added fade-out, removed noise gate from recording |

## Remaining Work

Latency calibration requires physical hardware to produce real measurements.
The cross-correlation math is verified; the per-device caching is verified.
Real-world testing will confirm the sync drift is eliminated.
