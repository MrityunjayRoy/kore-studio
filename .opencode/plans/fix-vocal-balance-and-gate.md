# Fix Vocal Balance and Sync Issues

## Issues Fixed

### 1. Vocals Louder Than Karaoke
**Root cause**: RMS-based gain normalization doesn't account for crest factor difference.
- Vocals: 10-15dB peak-to-RMS ratio (high dynamic range)
- Karaoke: 6-8dB peak-to-RMS ratio (compressed/mastered)
- Even when vocal RMS is lower, vocal PEAKS exceed karaoke peaks

**Fix**: Switch to peak-based normalization
- `vocal_target`: -8.0 dBFS peak
- `karaoke_target`: -1.0 dBFS peak
- Guaranteed 7dB gap at peak level
- Uses existing `peak_normalize()` from mixer.py
- Removed RMS gain calculation entirely

**Files changed**:
- `app/cli/studio.py` lines 542-547: replaced RMS gain with `peak_normalize()`
- `app/cli/studio.py` all presets: updated vocal_target/karaoke_target
- `app/pipeline/device_io.py` line 314: backing track peak limit 0.7 → 0.95

### 2. Recording Not In Sync
**Root cause**: In `record_with_playback` loop, `in_stream.read()` ran before `out_stream.write()`.
- Each iteration delayed output by 1 chunk (2048/48000 = 42.7ms)
- Over 65 seconds: ~1500 chunks × 42.7ms = ~64 seconds of accumulated drift
- Vocal appeared to start "late" relative to karaoke

**Fix**: Write output BEFORE reading input
- Non-monitoring path: `out_stream.write()` → `in_stream.read()`
- Playback starts immediately on first iteration
- Recording stays synchronized throughout

**Files changed**:
- `app/pipeline/device_io.py` lines 361-395: reordered read/write in audio_io_thread

## Testing
```bash
uv run kore studio
# Select "Studio Clean" preset
# Record and export
# Verify: karaoke louder than vocals, vocals in sync from start
```
