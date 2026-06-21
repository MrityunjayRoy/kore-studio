# Phase 7: Listening Validation

## Status: Awaiting Human Review

The following fixes have been implemented across Phases 1-6. **Numbers alone cannot confirm studio grade** — human listening is required.

## Files to Evaluate

Record a new take using:
```bash
uv run kore studio
```

Select "Studio Clean" or "Smule Style" preset. The improvements below will be applied automatically.

## What Changed (Audible Differences)

| Fix | What You Should Hear |
|-----|---------------------|
| **De-esser before presence** | Clear vocals without harsh "s" sounds |
| **Vocal limiter at -3dBFS** | No distortion on loud notes |
| **Real saturation** | Slightly warmer, fuller vocal tone |
| **Instrumental LUFS norm** | Consistent karaoke volume across songs |
| **Frequency ducking (2dB @ 1-4kHz)** | Vocal cuts through without fighting instrumental |
| **Proactive gain backoff** | No clipping or pumping on final export |
| **Latency calibration** | Vocal and karaoke in sync from start to end |
| **No noise gate** | Voice doesn't cut out between phrases |
| **Fade-in/fade-out** | No click/pop at recording start/end |
| **Float32 throughout** | No bit-depth truncation artifacts |

## Listening Checklist

Please evaluate the exported file against each item:

- [ ] **Balance**: Does the vocal sit comfortably with the instrumental? (Not buried, not overpowering)
- [ ] **Clarity**: Can you hear every word clearly? (No muddiness in 200-400Hz range)
- [ ] **Sibilance**: Are "s" and "t" sounds controlled? (No ear-piercing harshness)
- [ ] **Dynamics**: Does the vocal stay present in quiet passages and not spike in loud ones?
- [ ] **Reverb**: Does the vocal sound like it's in the same space as the instrumental? (Not pasted on)
- [ ] **Sync**: Is the vocal in time with the beat from start to finish? (No drift)
- [ ] **Noise**: Is background noise (fan, room tone) absent or minimal?
- [ ] **Start/End**: Any click or pop at the very beginning or end?
- [ ] **Loudness**: Comfortable at normal listening volume without reaching for the volume knob?
- [ ] **Fatigue**: Can you listen 3+ times without ear fatigue?

## Known Issues with OLD Output

The existing `kore_studio_output.wav` was generated **before** Phases 1-6 fixes:
- Loudness: -10.5 LUFS (too loud)
- True Peak: -0.3 dBTP (clipping risk)
- Mid range: -24.6dB (vocal buried)
- Air: -41.6dB (dead)

**Please record a NEW take to hear the improvements.**

## How to Provide Feedback

After recording and exporting, reply with:
1. Which preset you used
2. Pass/fail for each checklist item
3. Any specific issues you hear
4. Your audio device (mic model, headphones/speakers)
