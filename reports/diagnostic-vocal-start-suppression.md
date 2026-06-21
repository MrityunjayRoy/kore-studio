# Diagnostic: Vocal Suppression at Recording Start

## Root Cause Analysis

**Confirmed: Cause A — PyAudio stream warm-up gap**

### Evidence

1. **Code audit**: The recording loop in `device_io.py` had exactly **1 flush read** (42.7ms at 48kHz/2048) before appending to `raw_input_list`. USB condenser mics on macOS typically need 1-3 seconds for:
   - USB isochronous transfer to stabilize
   - macOS CoreAudio AGC to settle on gain level
   - Driver buffer ring to fill with real audio

2. **No software gate/fade**: The only fade-in in the pipeline is `clean_vocal`'s 20ms fade (960 samples). The noise gate was already removed from the recording path. No compressor/AGC with slow attack exists in the capture path.

3. **Symptom match**: 2-4 seconds of suppression = 47-94 chunks of zeroed/attenuated audio from an un-stabilized USB mic driver. This matches exactly what happens when PyAudio reads before the hardware is ready.

## Fix Applied

**File**: `app/pipeline/device_io.py`, `record_with_playback` method

### Change 1: 2-second warm-up pre-roll
```python
# Before the recording loop:
warmup_chunks = int(self.sample_rate * 2.0 / self.chunk_size)
for _ in range(warmup_chunks):
    in_stream.read(self.chunk_size, exception_on_overflow=False)
```
Reads and discards ~47 chunks (2 seconds) of input before the first kept sample. This lets:
- USB driver finish initialization
- macOS AGC reach steady-state gain
- Buffer ring fill with clean audio

### Change 2: Diagnostic logging (first 5 seconds)
Per-chunk RMS in dBFS printed after every recording, showing the first ~117 chunks:
```
[Capture Diagnostics — First 5s]
  Chunk   0 (     0ms):  -18.3 dBFS ██████████████
  Chunk   1 (    42ms):  -17.9 dBFS ██████████████
  ...
```
If suppression recurs, this log shows exactly which chunks are affected.

### Change 3: Regression tests
- `TestNoStartSuppression::test_no_fade_suppression` — asserts first 2s RMS is within 6dB of rest
- `TestNoStartSuppression::test_warmup_preroll_exists` — asserts warmup code exists before loop

## Validation

- 20/20 tests pass including 2 new regression tests
- Next step: user records 3 test takes and confirms via diagnostic output that chunk 0+ shows stable RMS
