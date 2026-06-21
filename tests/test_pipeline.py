"""test_pipeline.py — Regression tests for studio-grade pipeline.

Uses synthetic audio fixtures. No physical mic required.

Usage:
    pytest tests/test_pipeline.py -v
"""
import os
import tempfile
import numpy as np
import soundfile as sf
import pytest

from app.tools.analyze import analyze, TARGETS
from app.pipeline.device_io import clean_vocal, NoiseGate, remove_dc_offset, soft_clip
from app.pipeline.noise_reducer_service import NoiseReducer
from app.cli.studio import _build_effects_chain, _apply_vocal_doubler, PRESETS, apply_effects


SR = 48000
DURATION = 5.0


def make_sine(freq=440.0, sr=SR, duration=DURATION, amplitude=0.5):
    t = np.linspace(0, duration, int(sr * duration), endpoint=False, dtype=np.float32)
    return np.sin(2 * np.pi * freq * t) * amplitude


def make_vocal_like(sr=SR, duration=DURATION):
    t = np.linspace(0, duration, int(sr * duration), endpoint=False, dtype=np.float32)
    fundamental = np.sin(2 * np.pi * 220 * t) * 0.3
    harmonic1 = np.sin(2 * np.pi * 440 * t) * 0.15
    harmonic2 = np.sin(2 * np.pi * 880 * t) * 0.08
    noise = np.random.normal(0, 0.02, len(t)).astype(np.float32)
    envelope = np.ones_like(t)
    attack = int(sr * 0.05)
    envelope[:attack] = np.linspace(0, 1, attack)
    release = int(sr * 0.1)
    envelope[-release:] = np.linspace(1, 0, release)
    return (fundamental + harmonic1 + harmonic2 + noise) * envelope


def make_karaoke_like(sr=SR, duration=DURATION):
    t = np.linspace(0, duration, int(sr * duration), endpoint=False, dtype=np.float32)
    bass = np.sin(2 * np.pi * 80 * t) * 0.2
    mid = np.sin(2 * np.pi * 500 * t) * 0.1
    hihat = np.random.normal(0, 0.05, len(t)).astype(np.float32)
    left = bass + mid + hihat
    right = bass + mid * 0.8 + hihat * 0.9
    return np.column_stack([left, right])


class TestCleanVocal:
    def test_dc_removal(self):
        audio = make_sine() + 0.1
        cleaned = clean_vocal(audio, SR)
        assert abs(np.mean(cleaned)) < 0.01, f"DC offset not removed: {np.mean(cleaned)}"

    def test_fade_in(self):
        audio = make_sine(amplitude=0.5)
        cleaned = clean_vocal(audio, SR)
        assert abs(cleaned[0]) < 0.01, "Fade-in should start near 0"

    def test_fade_out(self):
        audio = make_sine(amplitude=0.5)
        cleaned = clean_vocal(audio, SR)
        assert abs(cleaned[-1]) < 0.01, "Fade-out should end near 0"

    def test_peak_limiting(self):
        audio = make_sine(amplitude=2.0)
        cleaned = clean_vocal(audio, SR)
        assert np.max(np.abs(cleaned)) <= 0.96, "Peak should be limited to 0.95"

    def test_no_clipping(self):
        audio = make_vocal_like()
        cleaned = clean_vocal(audio, SR)
        assert np.max(np.abs(cleaned)) < 1.0, "Cleaned vocal should not clip"

    def test_input_gain(self):
        audio = make_sine(amplitude=0.1)
        cleaned = clean_vocal(audio, SR, input_gain=2.0)
        peak = np.max(np.abs(cleaned))
        assert peak > 0.1, "Input gain should boost signal"

    def test_preserves_length(self):
        audio = make_sine(duration=3.0)
        cleaned = clean_vocal(audio, SR)
        assert len(cleaned) == len(audio), "Length should be preserved"


class TestNoiseGate:
    def test_silence_gated(self):
        silence = np.random.normal(0, 0.0001, SR).astype(np.float32)
        gate = NoiseGate(threshold_db=-40.0, sample_rate=SR)
        result = gate.process(silence)
        assert np.max(np.abs(result)) < 0.001, "Silence should be gated"

    def test_loud_signal_passes(self):
        loud = make_sine(amplitude=0.5, duration=1.0)
        gate = NoiseGate(threshold_db=-40.0, sample_rate=SR)
        result = gate.process(loud)
        assert np.max(np.abs(result)) > 0.1, "Loud signal should pass through"

    def test_attack_time(self):
        signal = np.zeros(SR, dtype=np.float32)
        signal[SR // 2:] = 0.5
        gate = NoiseGate(threshold_db=-40.0, attack_ms=50.0, sample_rate=SR)
        result = gate.process(signal)
        onset = SR // 2
        block_size = int(SR * 0.010)
        assert abs(result[onset]) < 0.3, "Gate should not reach full amplitude in first block"


class TestEffectsChain:
    def test_chain_builds(self):
        params = PRESETS["Studio Clean"]
        chain = _build_effects_chain(params)
        assert len(chain) > 0, "Chain should have plugins"

    def test_chain_processes(self):
        params = PRESETS["Studio Clean"]
        chain = _build_effects_chain(params)
        audio = make_vocal_like(duration=2.0)
        audio_2d = audio[np.newaxis, :]
        result = chain(audio_2d, sample_rate=SR)
        assert result.shape == audio_2d.shape, "Shape should be preserved"
        assert not np.any(np.isnan(result)), "No NaN in output"

    def test_all_presets_build(self):
        for name, params in PRESETS.items():
            chain = _build_effects_chain(params)
            assert len(chain) > 0, f"Preset {name} should build a chain"


class TestVocalDoubler:
    def test_doubler_creates_stereo(self):
        audio = make_vocal_like(duration=2.0)
        doubled = _apply_vocal_doubler(audio, SR, delay_ms=10.0, feedback=0.1)
        assert doubled.ndim == 2, "Doubler should create stereo from mono"
        assert doubled.shape[1] == 2, "Should have 2 channels"
        assert len(doubled) == len(audio), "Length should be preserved"

    def test_doubler_no_clipping(self):
        audio = make_sine(amplitude=0.8, duration=2.0)
        doubled = _apply_vocal_doubler(audio, SR, delay_ms=12.0, feedback=0.15)
        assert np.max(np.abs(doubled)) <= 0.96, "Doubler should not clip"


class TestMixBalance:
    def test_vocal_not_buried(self):
        vocal = make_vocal_like(duration=2.0)
        karaoke = make_karaoke_like(duration=2.0)
        params = dict(PRESETS["Studio Clean"])

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as kf:
            sf.write(kf.name, karaoke, SR)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as of:
                try:
                    apply_effects(vocal, SR, params, kf.name, of.name)
                    result = analyze(of.name)
                    assert result.integrated_loudness_lufs >= -20.0, \
                        f"Mix too quiet: {result.integrated_loudness_lufs} LUFS"
                    assert result.clipped_samples == 0, \
                        f"Mix has {result.clipped_samples} clipped samples"
                finally:
                    os.unlink(kf.name)
                    if os.path.exists(of.name):
                        os.unlink(of.name)


class TestExport:
    def test_export_24bit(self):
        audio = make_vocal_like(duration=1.0)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            sf.write(f.name, audio, SR, subtype="PCM_24")
            info = sf.info(f.name)
            assert info.subtype == "PCM_24", "Export should be 24-bit"
            os.unlink(f.name)

    def test_export_no_dc(self):
        audio = make_vocal_like(duration=2.0)
        cleaned = clean_vocal(audio, SR)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            sf.write(f.name, cleaned, SR)
            result = analyze(f.name)
            assert abs(result.dc_offset) < TARGETS["dc_offset_max"], \
                f"DC offset too high: {result.dc_offset}"
            os.unlink(f.name)


class TestNoStartSuppression:
    """Regression test: first 2 seconds must not be systematically quieter."""

    def test_no_fade_suppression(self):
        """clean_vocal fade-in is 20ms, should not suppress beyond that."""
        steady = np.ones(SR * 5, dtype=np.float32) * 0.3
        cleaned = clean_vocal(steady, SR)
        first_2s_rms = np.sqrt(np.mean(cleaned[:SR * 2].astype(np.float64) ** 2))
        rest_rms = np.sqrt(np.mean(cleaned[SR * 2:].astype(np.float64) ** 2))
        if rest_rms > 0:
            diff_db = 20 * np.log10(max(first_2s_rms, 1e-10)) - 20 * np.log10(rest_rms)
            assert diff_db > -6.0, \
                f"First 2s is {diff_db:.1f}dB quieter than rest (max allowed: -6dB)"

    def test_warmup_preroll_exists(self):
        """Verify record_with_playback has warmup pre-roll before recording loop."""
        import inspect
        from app.pipeline.device_io import AudioStream
        src = inspect.getsource(AudioStream.record_with_playback)
        assert 'warmup_chunks' in src, "Missing warmup pre-roll in recording"
        warmup_pos = src.find('warmup_chunks')
        loop_pos = src.find('for i in range(total)')
        assert warmup_pos < loop_pos, "Warmup must run before recording loop"
