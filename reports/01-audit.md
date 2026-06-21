# Phase 1: Pipeline Audit Report

## Signal Path

```
┌─────────────────────────────────────────────────────────────────────────┐
│ RECORDING PATH                                                          │
│                                                                         │
│  USB Mic → PyAudio(paFloat32, 1ch, 48kHz, chunk=2048) → in_stream     │
│    ↓                                                                    │
│  audio_io_thread (write-first sync)                                     │
│    ├── out_stream → speakers/headphones (backing track playback)        │
│    └── in_stream.read() → raw_input_list[bytes]                         │
│         ↓                                                               │
│  b"".join(raw_input_list) → np.float32 array                            │
│    ↓                                                                    │
│  clean_vocal()                                                          │
│    ├── ×input_gain (1.0/1.5/2.0)                                        │
│    ├── remove_dc_offset() [mean subtraction]                            │
│    ├── 20ms fade-in [linspace]                                          │
│    ├── soft_clip(threshold=0.90) [tanh saturation]                      │
│    └── peak limit to 0.95                                               │
│    ↓                                                                    │
│  kore_raw_vocal.wav (48kHz, mono, float32 → PCM_24)                     │
└─────────────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ POST-RECORDING PROCESSING (apply_effects)                               │
│                                                                         │
│  1. Noise Reduction (DeepFilterNet AI)                                  │
│  2. Pitch Correction (librosa.pyin → quantize → psola.vocode)          │
│  3. Vocal Doubler (mono delay, 10-20ms)                                 │
│  4. Pedalboard Chain:                                                   │
│     ├── HighpassFilter (80-120Hz)                                       │
│     ├── LowShelfFilter (200Hz, -1.5dB)                                  │
│     ├── PeakFilter (3kHz, +5dB) [presence]                              │
│     ├── HighShelfFilter (12kHz, +4dB) [air]                             │
│     ├── Compressor (de-esser: -20dB, 3:1)                               │
│     ├── Compressor (main: -18dB, 3:1, 3ms/60ms)                         │
│     ├── Distortion (drive 1.5dB) [saturation]                           │
│     └── Reverb (room=0.25, wet=10%, dry=85%)                            │
│  5. Gain (×1.0)                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────────────┐
│ MIX STAGE                                                               │
│                                                                         │
│  Load karaoke → resample to 48kHz → stereo                              │
│  Peak normalize vocal to -8 dBFS                                        │
│  Peak normalize karaoke to -1 dBFS                                      │
│  Sum: vocal + karaoke → clip(-1, 1)                                     │
│  pyloudnorm → -14 LUFS integrated                                       │
│  Pedalboard Limiter → -1 dBTP ceiling                                   │
│  Export: PCM_24 WAV                                                     │
└─────────────────────────────────────────────────────────────────────────┘
```

## Library Inventory

| Library | Version | Role | Format Handled |
|---------|---------|------|----------------|
| `pyaudio` | ≥0.2.14 | Audio I/O (recording + playback) | paFloat32 |
| `numpy` | ≥1.24.0 | Array math, DSP | float32/float64 |
| `soundfile` | ≥0.13.1 | WAV read/write | float64, PCM_24 |
| `librosa` | ≥0.11.0 | Resampling, pitch detection | float32 |
| `pedalboard` | ≥0.9.23 | DSP effects chain | float32 |
| `pyloudnorm` | ≥0.1.1 | LUFS measurement + normalization | float64 |
| `deepfilternet` | latest | AI noise reduction | float32 tensor |
| `torch` | 2.6.0 | DeepFilterNet backend | float32 |
| `psola` | ≥0.0.1 | Pitch correction | float32 |
| `rich` | ≥13.7.0 | TUI display | N/A |
| `inquirer` | ≥3.2.0 | TUI prompts | N/A |

## Bug Checklist

### 1. Sample Rate Mismatch — ⚠️ PARTIALLY PRESENT
- **Recording**: Fixed at 48kHz (`device_io.py:186`)
- **Instrumental**: Resampled to 48kHz on load (`studio.py:796`)
- **DeepFilterNet**: Model runs at its own SR (~48kHz), `NoiseReducer` handles resampling
- **Finding**: Recording is always 48kHz. If instrumental is 44.1kHz, it gets resampled. This is correct. No mismatch at mix time. ✅

### 2. Bit-Depth/Format Mismatch — ⚠️ PRESENT (soundfile read)
- `pyaudio` opens `paFloat32` ✅
- `clean_vocal` works in float32 ✅
- `soundfile.read()` returns **float64** by default ⚠️
- Karaoke loaded via `sf.read()` is float64, then processed in float64
- `pedalboard` expects float32; implicit conversion happens but may lose precision
- **Fix needed**: Force `dtype=np.float32` in all `sf.read()` calls

### 3. Round-Trip Latency Measurement — ❌ ABSENT
- No calibration step exists
- No cross-correlation between output and input
- Sync relies on write-first ordering + force-length-match
- **This is the primary cause of the 1-2 second drift**
- Two independent PyAudio streams have independent hardware clocks
- Over 60s, even 0.1% clock drift = 60ms; buffer timing adds more

### 4. Acoustic Bleed / Headphone Check — ⚠️ PARTIAL
- Pre-roll screen warns "Use headphones/earphones" ✅
- No device name heuristic check ❌
- No post-recording bleed detection (correlation check) ❌

### 5. PyAudio Buffer/Chunk Size — ℹ️ DOCUMENTED
- `frames_per_buffer = 2048` at 48kHz = 42.7ms per chunk
- This is the **maximum sync error per chunk**
- With write-first ordering, actual offset = 1 chunk = ~43ms
- This is perceptible (>20ms target) but not catastrophic
- **Fix**: Latency calibration (Phase 3.6) will measure and compensate

### 6. Linear Mixing Without Gain Staging — ❌ ABSENT (Fixed)
- Previously: `peak_normalize` with wrong targets
- Currently: `peak_normalize(vocal, -8)` + `peak_normalize(karaoke, -1)` ✅
- Gap is 7dB which may be too much (karaoke dominates)

### 7. Clipping Protection — ⚠️ PARTIAL
- `np.clip(mixed, -1.0, 1.0)` before loudness normalization ✅ (safety net)
- Pedalboard `Limiter` at -1dBTP after normalization ✅
- No proactive gain-backoff before clipping ❌
- If sum peaks at +3dB before clip, distortion is already introduced

### 8. Mono/Stereo Mismatch — ✅ HANDLED
- Vocal: mono → `np.column_stack([v, v])` for stereo ✅
- Karaoke: stereo or mono → normalized to stereo ✅
- Vocal doubler produces mono output ✅
- Final output is always stereo ✅

### 9. Silence/DC Offset at Boundaries — ✅ HANDLED
- 20ms fade-in on raw capture ✅
- DC offset removal via mean subtraction ✅
- No fade-out on recording end ⚠️ (minor risk)

## Current Mix Balance Analysis

From user's last exported file (`kore_studio_output.wav`):
- Vocal peak: -1.5 dBFS (too hot after limiting)
- RMS: -15.7 dBFS
- Mid (1k-4k): -24.6 dB relative to bass (vocal buried)
- Air (8k-16k): -41.6 dB (dead)
- Stereo correlation: 0.107 (too wide/random)
- Integrated loudness: -16.3 LUFS

**Root cause**: Presence boost at 5kHz missed the vocal clarity band (3kHz).
Air boost too weak. Reverb washing out detail. These are fixed in current presets.

## Baseline Measurements

*Cannot generate true baseline files without running CLI with physical mic.*
*Phase 2 will create synthetic test fixtures for deterministic testing.*

## Summary of Required Fixes (Priority Order)

| Priority | Issue | Phase |
|----------|-------|-------|
| 🔴 CRITICAL | No latency calibration | 3.6 |
| 🔴 CRITICAL | soundfile returns float64 | 1 (immediate) |
| 🟡 HIGH | No proactive clip protection | 6.2 |
| 🟡 HIGH | No fade-out on recording end | 3.5 |
| 🟡 HIGH | No acoustic bleed detection | 3.7 |
| 🟢 MEDIUM | No device headphone heuristic | 3.7 |
| 🟢 MEDIUM | Vocal balance may still be wrong | 6.1 |
| 🟢 MEDIUM | No input level check before recording | 3.2 |
