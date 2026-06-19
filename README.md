# KORE — Vocal-Karaoke Mixing Tool

KORE is a vocal-karaoke mixing pipeline that runs noise reduction, vocal effects (high-pass filter, compressor, reverb), and loudness-normalized mixing from the command line.

## Installation

Requires Python >= 3.11.

```bash
uv sync
```

## Usage

```bash
python -m app.cli.kore <vocal> <karaoke> [options]
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

### Mixer / loudness

| Option               | Default | Description                            |
|----------------------|---------|----------------------------------------|
| `--vocal-target`     | `-9.0`  | Vocal peak target in dBFS              |
| `--karaoke-target`   | `-13.0` | Karaoke peak target in dBFS            |
| `--loudness-target`  | `-14.0` | Integrated loudness target in LUFS     |
| `--true-peak`        | `-1.0`  | True peak ceiling in dB                |

## Example

```bash
python -m app.cli.kore vocal.wav karaoke.mp3 -o mix.wav \
  --highpass-cutoff 100 \
  --compressor-threshold -24 \
  --reverb-wet 0.25 \
  --vocal-target -10 \
  --loudness-target -14
```

## Pipeline

![KORE pipeline](pipeline.md)

1. **Noise reduction** — DeepFilterNet removes background noise and reverb from the vocal.
2. **Vocal effects** — A pedalboard chain applies high-pass filter → compressor → reverb.
3. **Mix & master** — Peak-normalized vocal and karaoke are summed, then loudness-normalized to the target LUFS and true-peak limited.

## Standalone subcommands

Each stage can be run independently:

```bash
python -m app.cli.noise-reducer <input> -o denoised.wav
python -m app.cli.vocal-effects <input> -o processed.wav [effect options]
python -m app.cli.mixer <vocals> <karaoke> -o mixed.wav [mix options]
```
