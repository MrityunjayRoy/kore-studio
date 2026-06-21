# KORE Studio — Configuration Reference

## Preset Parameters

Each preset in `app/cli/studio.py` controls the full processing chain. All parameters are tunable within the ranges shown.

### Recording Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `input_gain` | 1.0 | 0.5–2.0 | Mic sensitivity multiplier |
| `monitor_level` | 0.0 | 0.0–1.0 | Live vocal monitoring in headphones |

### Noise Reduction

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `noise_reduction` | True | bool | DeepFilterNet AI noise reduction |

### Pitch Correction

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `pitch_correct` | True | bool | Enable pitch correction |
| `pitch_key` | "C" | C–B | Musical key |
| `pitch_scale` | "chromatic" | chromatic/major/minor/pentatonic_* | Scale |
| `pitch_strength` | 0.5 | 0.0–1.0 | Correction strength |

### EQ

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `highpass_cutoff` | 80.0 | 20–200 Hz | High-pass filter cutoff |
| `low_cut_db` | -1.5 | 0 to -6 dB | Low shelf cut (mud removal) |
| `low_cut_freq` | 200.0 | 150–400 Hz | Low shelf center frequency |
| `presence_boost` | 5.0 | 0–8 dB | Mid-range clarity boost |
| `presence_freq` | 3000.0 | 2000–5000 Hz | Presence center frequency |
| `air_boost` | 4.0 | 0–6 dB | High shelf shimmer |
| `air_freq` | 12000.0 | 8000–16000 Hz | Air center frequency |

### Dynamics

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `deesser_threshold` | -20.0 | 0 to -30 dB | De-esser threshold (0=off) |
| `compressor_threshold` | -18.0 | 0 to -30 dB | Main compressor threshold |
| `compressor_ratio` | 3.0 | 1.5–6.0 | Compression ratio |
| `compressor_attack` | 5.0 | 1–20 ms | Attack time |
| `compressor_release` | 80.0 | 30–200 ms | Release time |

### Saturation

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `saturation_drive` | 1.5 | 0–4 dB | Harmonic saturation drive |

### Reverb

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `reverb_room_size` | 0.25 | 0–1.0 | Room size |
| `reverb_damping` | 0.5 | 0–1.0 | High-frequency damping |
| `reverb_wet` | 0.10 | 0–0.3 | Wet signal level |
| `reverb_dry` | 0.85 | 0.5–1.0 | Dry signal level |
| `reverb_width` | 0.7 | 0–1.0 | Stereo width |

### Vocal Doubler

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `doubler_enabled` | True | bool | Mono delay doubling |
| `doubler_delay_ms` | 12.0 | 5–30 ms | Delay time |
| `doubler_feedback` | 0.15 | 0–0.3 | Feedback amount |

### Mix

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `duck_depth_db` | 2.0 | 0–4 dB | Frequency ducking depth |
| `vocal_target` | -8.0 | -14 to -4 dBFS | Vocal peak level |
| `karaoke_target` | -1.0 | -6 to 0 dBFS | Karaoke peak level |
| `loudness_target` | -14.0 | -18 to -12 LUFS | Final integrated loudness |
| `true_peak` | -1.0 | -3 to -0.5 dBTP | True peak ceiling |
| `gain` | 1.0 | 0.5–2.0 | Post-chain gain |

## Built-in Vocal Limiter

A fixed -3dBFS limiter is always applied at the end of the vocal chain, before mixing. This is not user-configurable — it ensures headroom for the final bus limiter.

## Processing Chain Order

1. **Noise Reduction** (DeepFilterNet)
2. **Pitch Correction** (librosa + psola)
3. **Vocal Doubler** (mono delay)
4. **High-Pass Filter** (80Hz)
5. **Low Shelf** (200Hz, -1.5dB)
6. **De-esser** (-20dB threshold)
7. **Presence Boost** (3kHz, +5dB)
8. **Air Boost** (12kHz shelf, +4dB)
9. **Compressor** (-18dB, 3:1)
10. **Saturation** (1.5dB drive)
11. **Vocal Limiter** (-3dBFS)
12. **Reverb** (room 0.25, wet 10%)

## Mix Stage

1. Instrumental LUFS normalization (-18 LUFS)
2. Hot master protection (peak > -1dBTP → reduce)
3. Frequency-conscious ducking (2dB @ 1-4kHz)
4. Peak normalization (vocal & karaoke)
5. Sum in float32
6. LUFS normalization (-14 LUFS)
7. Proactive gain backoff (if true peak > ceiling)
8. True-peak limiter (-1 dBTP)
9. Export 24-bit WAV
