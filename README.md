# KORE — Vocal-Karaoke Mixing Tool

KORE is a vocal-karaoke mixing pipeline that runs noise reduction, vocal effects (high-pass filter, compressor, reverb), and loudness-normalized mixing from the command line.

It has two modes:
- **`kore studio`** — Interactive TUI for recording vocals over karaoke in real time, then applying studio-grade effects.
- **`kore <vocal> <karaoke>`** — Offline batch pipeline for mixing pre-recorded vocal files with instrumentals.

## Installation

Requires Python >= 3.11 and [uv](https://docs.astral.sh/uv/).

**macOS:** Install PortAudio first (required for live audio I/O):
```bash
brew install portaudio
```

**All platforms:**
```bash
git clone https://github.com/MrityunjayRoy/kore && cd kore
uv venv
uv sync
```

This installs the `kore` and `kore-studio` commands into the virtual environment. Activate with `source .venv/bin/activate`, or use `uv run kore ...` / `uv run kore-studio`.

## KORE Studio — Interactive Recording

`kore studio` launches a Rich-based terminal UI that lets you select your microphone and headphones, play a karaoke track, record your vocals in sync, and then process everything through a studio-grade effects chain.

### Quick start

```bash
uv run kore studio
```

Use headphones or earphones to prevent the karaoke track from bleeding into the microphone.

### Recording flow

1. **Device selection** — Choose your input device (USB condenser mic, built-in mic, etc.), output device (headphones, Bluetooth earbuds, speakers), and the path to your karaoke/instrumental audio file. You can also set the live vocal monitoring level and input gain.
2. **Latency calibration** — On first use of a device pair, KORE automatically measures round-trip latency by playing a calibration chirp and cross-correlating the captured signal. The result is cached in `~/.kore_latency_cache.json` and reused on subsequent sessions.
3. **Pre-roll** — Review your setup summary (devices, sample rate, monitoring level, measured latency). Press **Enter** to begin.
4. **Recording** — The karaoke plays through your output device while your mic records simultaneously. A live display shows:
   - Recording timer
   - Input VU meter (color-coded: green/yellow/red)
   - Karaoke playback progress bar
   - Real-time waveform visualization
   - Monitor level indicator

   **Key bindings during recording:**
   | Key | Action |
   |-----|--------|
   | `Space` | Stop recording |
   | `P` | Pause / resume |
   | `M` | Cycle monitor level (Off → 30% → 50% → 80% → 100%) |

5. **Post-recording menu** — After recording stops, you can:
   - Preview the raw vocal
   - Preview the vocal mixed with karaoke
   - Proceed to the effects studio
   - Re-record
   - Cancel

6. **Effects studio** — Toggle and configure each stage of the processing chain:
   - Noise Reduction (DeepFilterNet AI)
   - Pitch Correction (key, scale, strength)
   - High-pass Filter
   - Presence / De-esser
   - Compressor
   - Reverb
   - Mix Levels (vocal/karaoke balance)
   - Gain

   **Presets** apply a full set of tuned parameters in one click:
   | Preset | Character |
   |--------|-----------|
   | Studio Clean | Natural, balanced, light reverb |
   | Smule Style | Bright, forward, moderate pitch correction |
   | Live Concert | Big reverb, wider stereo, heavier compression |
   | Podcast | Dry, tight, minimal effects |
   | Raw | No processing |

7. **Export** — Apply & Export runs the full pipeline and saves a 24-bit WAV file. An automatic diagnostic prints pass/fail against studio-grade targets (true peak, DC offset, clipping, clicks).

### Tips for best results

- **Use headphones.** Speaker playback bleeds into the mic and causes phase artifacts that no software can fully remove.
- **Set input gain so your loudest notes peak around -6 dBFS.** The pre-roll screen shows the current gain setting; adjust your mic's hardware gain knob or use the software input gain option.
- **Start singing immediately.** A 2-second mic warm-up runs before recording starts, so the first sound captured is already stable.
- **Try "Smule Style" preset** if you want that polished, pitch-corrected karaoke sound. "Studio Clean" is better for a natural vocal performance.
- **Use `--vocal-balance` on the CLI** to adjust the vocal/karaoke ratio without re-recording:
  ```bash
  uv run kore vocal.wav karaoke.mp3 --vocal-balance +3   # Louder vocal
  uv run kore vocal.wav karaoke.mp3 --vocal-balance -2   # Quieter vocal
  ```

## Offline Pipeline

```bash
kore <vocal> <karaoke> [options]
```

### Positional arguments

| Argument    | Description                  |
|-------------|------------------------------|
| `vocal`     | Path to vocal audio file     |
| `karaoke`   | Path to karaoke/instrumental |

### General options

| Option                  | Default          | Description                          |
|-------------------------|------------------|--------------------------------------|
| `-o`, `--output`        | `kore_output.wav`| Output path for final mix            |
| `--gain`                | `1.0`            | Output gain multiplier               |
| `--keep-denoised`       | —                | Save intermediate denoised vocal     |
| `--keep-processed`      | —                | Save intermediate processed vocal    |

### High-pass filter

| Option                 | Default | Description                        |
|------------------------|---------|------------------------------------|
| `--highpass-cutoff`    | `80.0`  | Cutoff frequency in Hz             |

### Compressor

| Option                     | Default | Description                   |
|----------------------------|---------|-------------------------------|
| `--compressor-threshold`   | `-20.0` | Threshold in dB               |
| `--compressor-ratio`       | `3.0`   | Ratio                         |
| `--compressor-attack`      | `2.0`   | Attack in ms                  |
| `--compressor-release`     | `50.0`  | Release in ms                 |

### Reverb

| Option               | Default | Description               |
|----------------------|---------|---------------------------|
| `--reverb-room-size` | `0.3`   | Room size 0–1             |
| `--reverb-damping`   | `0.5`   | Damping 0–1               |
| `--reverb-wet`       | `0.2`   | Wet level 0–1             |
| `--reverb-dry`       | `0.6`   | Dry level 0–1             |
| `--reverb-width`     | `0.8`   | Stereo width 0–1          |

### Pitch correction

| Option               | Default      | Description                                    |
|----------------------|--------------|------------------------------------------------|
| `--pitch-correct`    | off          | Enable pitch correction                        |
| `--pitch-key`        | `C`          | Musical key (C, C#, D, ..., B)                |
| `--pitch-scale`      | `chromatic`  | Scale: chromatic, major, minor, pentatonic_*   |
| `--pitch-strength`   | `0.8`        | Correction strength 0.0–1.0                    |

### Mixer / loudness

| Option               | Default | Description                            |
|----------------------|---------|----------------------------------------|
| `--vocal-balance`    | `0.0`   | Vocal balance offset in dB (+ = louder)|
| `--vocal-target`     | `-9.0`  | Vocal peak target in dBFS              |
| `--karaoke-target`   | `-13.0` | Karaoke peak target in dBFS            |
| `--loudness-target`  | `-14.0` | Integrated loudness target in LUFS     |
| `--true-peak`        | `-1.0`  | True peak ceiling in dB                |

## Example

```bash
# Interactive studio recording
uv run kore studio

# Offline mix with pitch correction
uv run kore vocal.wav karaoke.mp3 -o mix.wav \
  --pitch-correct --pitch-key G --pitch-scale major \
  --highpass-cutoff 100 \
  --compressor-threshold -24 \
  --reverb-wet 0.25 \
  --vocal-target -10 \
  --loudness-target -14

# Adjust vocal balance without re-recording
uv run kore vocal.wav karaoke.mp3 --vocal-balance +2
```

## Pipeline

See [pipeline.md](pipeline.md) for the full signal path diagram.

### Recording path (`kore studio`)
1. **Device selection** — Pick input (mic), output (headphones), karaoke file, monitoring level, input gain.
2. **Latency calibration** — Cross-correlation chirp measures round-trip delay, cached per device pair.
3. **Live recording** — Karaoke plays while mic records simultaneously. 2-second mic warm-up pre-roll ensures stable capture from the first sample.
4. **Post-processing** — DeepFilterNet noise reduction → pitch correction → vocal doubler → HPF → de-esser → EQ → compression → saturation → limiting → reverb → mix with LUFS-normalized instrumental → frequency ducking → true-peak safe gain staging → final limiting → 24-bit WAV export.
5. **Auto-diagnostic** — Every export is measured against studio-grade targets (true peak ≤ -1.0 dBTP, zero clips, DC < 0.001) and a pass/fail report is printed.

### Offline path (`kore <vocal> <karaoke>`)
1. **Noise reduction** — DeepFilterNet removes background noise and reverb from the vocal.
2. **Pitch correction** (optional) — librosa.pyin detects pitch, quantizes to scale, psola shifts.
3. **Vocal effects** — A pedalboard chain applies high-pass filter → de-esser → EQ → compressor → saturation → limiter → reverb.
4. **Mix & master** — Peak-normalized vocal and karaoke are summed, true-peak safe gain staging is applied, and the result is limited to -1.0 dBTP.

## Analysis tools

KORE includes studio-grade measurement tools:

```bash
# Analyze any WAV file against studio targets
uv run python -m app.tools.analyze output.wav

# Compare two files (e.g. baseline vs processed)
uv run python -m app.tools.compare old.wav new.wav

# JSON output for CI/scripting
uv run python -m app.tools.analyze output.wav --json
```

Metrics measured: integrated loudness (LUFS), true peak (dBTP), sample peak, RMS, crest factor, DC offset, stereo correlation, clipping, click/pop detection, spectral balance.

## Standalone subcommands

Each stage can be run independently:

```bash
python -m app.cli.noise-reducer <input> -o denoised.wav
python -m app.cli.vocal-effects <input> -o processed.wav [effect options]
python -m app.cli.mixer <vocals> <karaoke> -o mixed.wav [mix options]
```

Run `kore --help` for a full list of offline pipeline options.
