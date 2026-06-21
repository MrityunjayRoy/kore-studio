# Phase 4-6: Processing & Mix Fixes

## Phase 4: Vocal Processing Chain

### Chain Order Fixed
**Before (WRONG):** HPF → Low Cut → **Presence** → Air → **De-esser** → Comp → Fake Sat → Reverb
**After (CORRECT):** HPF → Low Cut → **De-esser** → Presence → Air → Comp → **Real Sat** → **Limiter** → Reverb

### Changes
| Stage | Fix | Rationale |
|-------|-----|-----------|
| De-esser | Moved BEFORE presence boost | Presence boost amplifies sibilance; de-esser must control it first |
| Saturation | `Gain+PeakFilter` → `Distortion` plugin | Real harmonic saturation, not fake EQ trick |
| Vocal Limiter | **ADDED** at -3dBFS | Catches peaks before mix stage, leaves headroom for bus limiter |
| Low Cut | `PeakFilter` → `LowShelfFilter` | Broader, more musical mud removal |
| Air | `PeakFilter` → `HighShelfFilter` | Natural high-frequency shelf, not narrow peak |
| Compressor | attack 3ms → 5ms | Let initial transient through for clarity |

### Verified
- All 5 presets build correct chain ✅
- De-esser always before presence ✅
- Limiter always present ✅
- 18/18 tests pass ✅

---

## Phase 5: Instrumental Handling

### LUFS Normalization
- Instrumental normalized to **-18 LUFS** on load (consistent baseline)
- Prevents wildly different karaoke volumes across songs

### Hot Master Protection
- If instrumental true peak > -1 dBTP, auto-reduce to -2 dBFS
- Prevents clipping when vocal is added

### Frequency-Conscious Ducking
- **2dB dip** in 1-4kHz range on instrumental when vocal is present
- Envelope follower detects vocal activity
- Only affects vocal frequency band (not full-band pumping)
- Configurable via `duck_depth_db` preset parameter

---

## Phase 6: Mix Stage

### Proactive Gain Backoff
**Root cause of -0.3 dBTP true peak:** pyloudnorm boosted mix to hit -14 LUFS target, pushing peaks above ceiling.

**Fix:** After loudness normalization, measure true peak via 4x oversampling. If above target:
1. Calculate exact backoff needed
2. Reduce gain BEFORE limiter
3. Then apply limiter as final safety net

This eliminates distortion from the limiter working too hard.

### `--vocal-balance` CLI Flag
```bash
kore vocal.wav karaoke.mp3 --vocal-balance +3   # Louder vocal
kore vocal.wav karaoke.mp3 --vocal-balance -2   # Quieter vocal
```
Additive offset to `--vocal-target`. Default: 0dB.

### Mix Balance Targets
| Preset | Vocal | Karaoke | Gap |
|--------|-------|---------|-----|
| Studio Clean | -8 dBFS | -1 dBFS | 7dB (karaoke louder) |
| Smule Style | -8 dBFS | -1 dBFS | 7dB |
| Live Concert | -8 dBFS | -1 dBFS | 7dB |
| Podcast | -8 dBFS | -1 dBFS | 7dB |
| Raw | -8 dBFS | -1 dBFS | 7dB |
