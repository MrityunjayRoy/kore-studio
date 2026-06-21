# KORE Studio CLI — Implementation Plan

## Overview

Add a `kore studio` subcommand with Rich-based TUI for real-time karaoke recording, device selection, post-recording studio pipeline with pitch correction, effects, and Smule-quality presets.

---

## Step 1: Update `pyproject.toml` — Add Dependencies

**File:** `pyproject.toml`

Add to `dependencies` array:
```toml
"pyaudio>=0.2.14",
"rich>=13.7.0",
"inquirer>=3.2.0",
"psola>=0.0.4",
"numpy>=1.24.0",
```

---

## Step 2: Create `app/pipeline/device_io.py` — PyAudio Wrapper

**New file.** Core audio I/O layer.

### Functions
- `list_input_devices() -> list[dict]` — enumerate all input devices via `pyaudio.PyAudio().get_device_count()`, filter by `maxInputChannels > 0`. Return `[{id, name, channels, sample_rates}]`.
- `list_output_devices() -> list[dict]` — same but `maxOutputChannels > 0`.
- `get_default_input_device() -> dict`
- `get_default_output_device() -> dict`

### Class: `AudioStream`
```python
class AudioStream:
    def __init__(self, input_device_id: int, output_device_id: int, 
                 sample_rate: int = 48000, chunk_size: int = 1024)
    
    # Recording only
    def record(self, duration: float, on_chunk=None) -> np.ndarray
        # on_chunk callback receives each chunk for VU meter display
        # Returns complete recording as numpy array
    
    # Playback only
    def play(self, audio: np.ndarray, on_progress=None)
    
    # Simultaneous record + playback (duplex)
    def record_with_playback(self, backing_track: np.ndarray, duration: float, 
                             on_chunk=None) -> np.ndarray
        # Plays backing_track through output while recording from input
        # Returns recorded vocal as numpy array
    
    def start()
    def stop()
    def close()
```

### Implementation Details
- Use `pyaudio.PyAudio()` singleton
- Non-blocking stream with callback for duplex mode
- Ring buffer for thread-safe audio chunk passing
- Format: `paFloat32`, channels: 1 (mono) for input, 2 (stereo) for output
- Handle device mismatch (input mono → output stereo duplication)
- Cross-platform: use device IDs not names, handle sample rate negotiation

---

## Step 3: Create `app/pipeline/pitch_correct.py` — Pitch Correction

**New file.** Programmatic pitch correction per `pipeline.md` Step 3.

### Functions
```python
def detect_pitch(audio: np.ndarray, sr: int, frame_length: int = 2048, 
                 hop_length: int = 512) -> np.ndarray
    # Uses librosa.pyin
    # Returns f0 array (Hz per frame), 0 = unvoiced

def quantize_to_scale(f0: np.ndarray, key: str = "C", 
                      scale: str = "chromatic") -> np.ndarray
    # Map each f0 value to nearest MIDI note in key/scale
    # Returns target f0 array

def correct_pitch(audio: np.ndarray, sr: int, f0_orig: np.ndarray, 
                  f0_target: np.ndarray, hop_length: int = 512,
                  strength: float = 1.0) -> np.ndarray
    # Uses psola for time-domain pitch shifting
    # Blends original and corrected based on strength (0.0-1.0)
    # Returns pitch-corrected audio array

def auto_pitch_correct(audio: np.ndarray, sr: int, key: str = "C",
                       scale: str = "chromatic", strength: float = 0.8) -> np.ndarray
    # Convenience wrapper: detect → quantize → correct
```

### Musical Scales
```python
SCALES = {
    "chromatic": [0,1,2,3,4,5,6,7,8,9,10,11],
    "major": [0,2,4,5,7,9,11],
    "minor": [0,2,3,5,7,8,10],
    "pentatonic_major": [0,2,4,7,9],
    "pentatonic_minor": [0,3,5,7,10],
}
```

### Key-to-MIDI Mapping
- A0 = MIDI 21, C4 = MIDI 60, etc.
- `key` param is root note (C, C#, D, ..., B)
- Calculate allowed MIDI notes from key + scale, snap each f0 to nearest

### Edge Cases
- Unvoiced frames (f0=0): pass through unmodified
- Strength < 1.0: interpolate between original and target f0
- Audio shorter than frame_length: return unchanged

---

## Step 4: Create `app/cli/studio.py` — Rich TUI

**New file.** Interactive recording studio interface.

### Entry Point
```python
def main(args=None):
    # Called by `kore studio` command
```

### Screen Flow

#### Screen 1: Device Selection
```python
def select_devices():
    # Use inquirer to show:
    # - List input devices (name, channels)
    # - List output devices (name, channels)
    # - Karaoke track path (text input + file validation)
    # Returns: (input_dev_id, output_dev_id, karaoke_path)
```

#### Screen 2: Pre-Roll
```python
def pre_roll_screen(input_dev, output_dev, karaoke_path):
    # Display summary table
    # Show effects chain that will be applied
    # "Press SPACE to begin recording, ESC to cancel"
```

#### Screen 3: Recording (Rich Live)
```python
def recording_screen(audio_stream, karaoke_audio, sr):
    # Rich Live display updating at ~10fps:
    # ┌─────────────────────────────────────┐
    # │  🔴 REC  02:34                      │
    # │                                     │
    # │  INPUT  ████████████░░░░  -6dB      │
    # │  KARAOKE ████████░░░░░░░░ 60%      │
    # │                                     │
    # │  ▁▂▃▅▆▇█▇▆▅▃▂▁▂▃▅▆▇█▇▆▅▃▂        │  ← waveform
    # │                                     │
    # │  [SPACE] Stop  [P] Pause            │
    # └─────────────────────────────────────┘
    # Returns: recorded vocal numpy array
```

#### Screen 4: Post-Recording Menu
```python
def post_recording_menu(raw_vocal, sr, karaoke_path):
    # Loop until user exports or exits:
    # 1. Preview raw recording (playback)
    # 2. Apply effects → show effects menu
    # 3. Re-record
    # 4. Export and exit
```

#### Screen 5: Effects Menu
```python
def effects_menu(vocal, sr):
    # Interactive parameter tweaking:
    # Toggle each effect on/off
    # Adjust parameters with sliders (inquirer text input with validation)
    # 
    # Effects:
    # ☑ Noise Reduction
    # ☑ Pitch Correction    [Key: C] [Scale: chromatic] [Strength: 0.8]
    # ☑ High-pass Filter    [Cutoff: 80 Hz]
    # ☑ Compressor          [Thresh: -20dB] [Ratio: 3.0] [Attack: 2ms] [Release: 50ms]
    # ☑ Reverb              [Room: 0.3] [Damp: 0.5] [Wet: 0.2] [Dry: 0.6] [Width: 0.8]
    # ☐ Gain                [1.0]
    #
    # [APPLY] [RESET] [PRESETS] [CANCEL]
    # Returns: modified vocal array
```

#### Screen 6: Presets
```python
PRESETS = {
    "Studio Clean": {
        "noise_reduction": True,
        "pitch_correct": True, "pitch_key": "C", "pitch_scale": "chromatic", "pitch_strength": 0.5,
        "highpass_cutoff": 80.0,
        "compressor_threshold": -18.0, "compressor_ratio": 2.5, 
        "compressor_attack": 3.0, "compressor_release": 60.0,
        "reverb_room_size": 0.2, "reverb_damping": 0.6,
        "reverb_wet": 0.15, "reverb_dry": 0.7, "reverb_width": 0.7,
    },
    "Live Concert": {
        "noise_reduction": True,
        "pitch_correct": True, "pitch_key": "C", "pitch_scale": "major", "pitch_strength": 0.7,
        "highpass_cutoff": 100.0,
        "compressor_threshold": -22.0, "compressor_ratio": 3.5,
        "compressor_attack": 2.0, "compressor_release": 40.0,
        "reverb_room_size": 0.6, "reverb_damping": 0.3,
        "reverb_wet": 0.4, "reverb_dry": 0.5, "reverb_width": 0.9,
    },
    "Podcast": {
        "noise_reduction": True,
        "pitch_correct": False,
        "highpass_cutoff": 120.0,
        "compressor_threshold": -16.0, "compressor_ratio": 4.0,
        "compressor_attack": 1.0, "compressor_release": 80.0,
        "reverb_room_size": 0.1, "reverb_damping": 0.8,
        "reverb_wet": 0.05, "reverb_dry": 0.9, "reverb_width": 0.3,
    },
    "Raw": {
        "noise_reduction": False, "pitch_correct": False,
        "highpass_cutoff": 20.0,
        "compressor_threshold": 0.0, "compressor_ratio": 1.0,
        "compressor_attack": 10.0, "compressor_release": 100.0,
        "reverb_room_size": 0.0, "reverb_damping": 1.0,
        "reverb_wet": 0.0, "reverb_dry": 1.0, "reverb_width": 0.0,
    }
}
```

### Effects Processing Pipeline
```python
def apply_effects(vocal: np.ndarray, sr: int, params: dict, 
                  karaoke_path: str = None, output_path: str = "kore_studio_output.wav"):
    # 1. Noise reduction (if enabled)
    # 2. Pitch correction (if enabled)
    # 3. High-pass filter
    # 4. Compressor
    # 5. Reverb
    # 6. Gain
    # 7. Mix with karaoke (if karaoke_path provided)
    # 8. Loudness normalize + limit
    # 9. Export
```

### VU Meter Helper
```python
def vu_meter(audio_chunk: np.ndarray, width: int = 20) -> str:
    # Calculate RMS of chunk
    # Map to dB scale (-60 to 0)
    # Return bar string: "████████████░░░░░░░░ -6dB"
    # Color code: green < -12dB, yellow -12 to -3, red > -3
```

### Waveform Display Helper
```python
def ascii_waveform(audio_chunk: np.ndarray, width: int = 40) -> str:
    # Downsample chunk to `width` points
    # Map amplitude to braille chars or ▁▂▃▄▅▆▇█
    # Return string
```

---

## Step 5: Update `app/cli/kore.py` — Add Studio Subcommand + Pitch Args

**Modify existing file.**

### Changes
1. Add `studio` subcommand detection:
```python
def main():
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "studio":
        from app.cli.studio import main as studio_main
        sys.argv.pop(1)  # Remove 'studio' from args
        studio_main()
        return
    # ... existing pipeline code ...
```

2. Add pitch correction arguments to existing parser:
```python
pitch_group = parser.add_argument_group("Pitch correction")
pitch_group.add_argument("--pitch-correct", action="store_true",
                        help="Enable pitch correction")
pitch_group.add_argument("--pitch-key", default="C",
                        help="Musical key for pitch correction (default: C)")
pitch_group.add_argument("--pitch-scale", default="chromatic",
                        choices=["chromatic", "major", "minor", 
                                 "pentatonic_major", "pentatonic_minor"],
                        help="Scale for pitch quantization (default: chromatic)")
pitch_group.add_argument("--pitch-strength", type=float, default=0.8,
                        help="Pitch correction strength 0.0-1.0 (default: 0.8)")
```

3. Integrate pitch correction into pipeline (after noise reduction, before effects):
```python
# In main(), after noise reduction step:
if args.pitch_correct:
    from app.pipeline.pitch_correct import auto_pitch_correct
    denoised, _ = sf.read(denoised_path)
    corrected = auto_pitch_correct(denoised, df_state.sr(), 
                                   key=args.pitch_key,
                                   scale=args.pitch_scale,
                                   strength=args.pitch_strength)
    sf.write(denoised_path, corrected, df_state.sr())
```

---

## Step 6: Update `pyproject.toml` — Add Studio Script Entry

Optional convenience:
```toml
[project.scripts]
kore = "app.cli.kore:main"
kore-studio = "app.cli.studio:main"
```

---

## Execution Order

| Step | File | Action | Depends On |
|------|------|--------|------------|
| 1 | `pyproject.toml` | Edit: add deps | None |
| 2 | `app/pipeline/device_io.py` | Create | Step 1 |
| 3 | `app/pipeline/pitch_correct.py` | Create | Step 1 |
| 4 | `app/cli/studio.py` | Create | Steps 2, 3 |
| 5 | `app/cli/kore.py` | Edit: add studio + pitch args | Steps 3, 4 |
| 6 | Install + test | `uv pip install -e .` | All above |

---

## Key Technical Decisions

### Threading Model
- PyAudio callback runs in separate thread
- Main thread runs Rich Live display
- `queue.Queue` passes audio chunks from callback to UI
- Recording stop signal via `threading.Event`

### Cross-Platform Device Handling
- Use device index (int), not name (string) — names vary by OS
- Fallback to default device if selected device unavailable
- Graceful error messages if PyAudio can't open device

### Sample Rate
- 48000 Hz throughout (matches existing CLI)
- PyAudio stream negotiates with device, resample if needed

### Memory Management
- Pre-allocate recording buffer: `np.zeros(max_samples)` 
- Track write position, trim to actual length on stop
- Avoid dynamic array resizing during recording

### Error Handling
- Device busy → clear error message
- File not found → inquirer validation
- DeepFilterNet OOM → catch and suggest disabling noise reduction
- psola artifacts → strength parameter lets user blend

---

## Non-Goals (This Phase)

- Real-time effects processing (post-recording only)
- VST/AU plugin hosting
- MIDI input
- Multi-track recording (one vocal + one karaoke only)
- Cloud upload/export
