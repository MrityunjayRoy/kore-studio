import os
from typing import Optional

import numpy as np
import soundfile as sf
from rich.console import Console

console = Console()

PRESETS = {
    "Studio Clean": {
        "noise_reduction": True,
        "pitch_correct": True, "pitch_key": "C", "pitch_scale": "chromatic", "pitch_strength": 0.5,
        "highpass_cutoff": 80.0,
        "low_cut_db": -1.5, "low_cut_freq": 200.0,
        "gate_enabled": True, "gate_threshold_db": -60.0,
        "boxiness_db": -2.0, "boxiness_freq": 400.0,
        "harshness_db": -2.0, "harshness_freq": 3500.0,
        "presence_boost": 5.0, "presence_freq": 3000.0,
        "air_boost": 4.0, "air_freq": 12000.0,
        "deesser_threshold": -20.0,
        "saturation_drive": 1.5,
        "leveler_threshold": -24.0, "leveler_ratio": 2.0,
        "leveler_attack": 10.0, "leveler_release": 150.0,
        "compressor_threshold": -18.0, "compressor_ratio": 3.0,
        "compressor_attack": 3.0, "compressor_release": 60.0,
        "reverb_room_size": 0.25, "reverb_damping": 0.5,
        "reverb_wet": 0.10, "reverb_dry": 0.85, "reverb_width": 0.7,
        "doubler_enabled": True, "doubler_delay_ms": 12.0, "doubler_feedback": 0.15,
        "duck_depth_db": 2.0,
        "vocal_target": -8.0, "karaoke_target": -12.0,
        "loudness_target": -14.0, "true_peak": -1.0,
        "input_gain": 1.0, "gain": 1.0,
    },
    "Smule Style": {
        "noise_reduction": True,
        "pitch_correct": True, "pitch_key": "C", "pitch_scale": "major", "pitch_strength": 0.7,
        "highpass_cutoff": 80.0,
        "low_cut_db": -1.0, "low_cut_freq": 200.0,
        "gate_enabled": True, "gate_threshold_db": -58.0,
        "boxiness_db": -2.0, "boxiness_freq": 350.0,
        "harshness_db": -3.0, "harshness_freq": 3000.0,
        "presence_boost": 6.0, "presence_freq": 3000.0,
        "air_boost": 5.0, "air_freq": 12000.0,
        "deesser_threshold": -22.0,
        "saturation_drive": 2.0,
        "leveler_threshold": -22.0, "leveler_ratio": 2.5,
        "leveler_attack": 8.0, "leveler_release": 120.0,
        "compressor_threshold": -20.0, "compressor_ratio": 3.5,
        "compressor_attack": 1.5, "compressor_release": 40.0,
        "reverb_room_size": 0.28, "reverb_damping": 0.4,
        "reverb_wet": 0.12, "reverb_dry": 0.82, "reverb_width": 0.8,
        "doubler_enabled": True, "doubler_delay_ms": 15.0, "doubler_feedback": 0.2,
        "vocal_target": -8.0, "karaoke_target": -12.0,
        "loudness_target": -13.0, "true_peak": -1.0,
        "input_gain": 1.0, "gain": 1.0,
    },
    "Live Concert": {
        "noise_reduction": True,
        "pitch_correct": True, "pitch_key": "C", "pitch_scale": "major", "pitch_strength": 0.6,
        "highpass_cutoff": 80.0,
        "low_cut_db": -1.0, "low_cut_freq": 200.0,
        "gate_enabled": True, "gate_threshold_db": -65.0,
        "boxiness_db": -1.5, "boxiness_freq": 400.0,
        "harshness_db": -1.5, "harshness_freq": 3500.0,
        "presence_boost": 4.0, "presence_freq": 3000.0,
        "air_boost": 3.5, "air_freq": 12000.0,
        "deesser_threshold": -18.0,
        "saturation_drive": 1.8,
        "leveler_threshold": -20.0, "leveler_ratio": 2.5,
        "leveler_attack": 8.0, "leveler_release": 100.0,
        "compressor_threshold": -22.0, "compressor_ratio": 4.0,
        "compressor_attack": 2.0, "compressor_release": 40.0,
        "reverb_room_size": 0.45, "reverb_damping": 0.3,
        "reverb_wet": 0.15, "reverb_dry": 0.78, "reverb_width": 1.0,
        "doubler_enabled": True, "doubler_delay_ms": 20.0, "doubler_feedback": 0.25,
        "vocal_target": -8.0, "karaoke_target": -12.0,
        "loudness_target": -13.0, "true_peak": -1.0,
        "input_gain": 1.0, "gain": 1.0,
    },
    "Podcast": {
        "noise_reduction": True,
        "pitch_correct": False, "pitch_key": "C", "pitch_scale": "chromatic", "pitch_strength": 0.0,
        "highpass_cutoff": 80.0,
        "low_cut_db": -2.0, "low_cut_freq": 200.0,
        "gate_enabled": True, "gate_threshold_db": -65.0,
        "boxiness_db": -3.0, "boxiness_freq": 450.0,
        "harshness_db": -2.0, "harshness_freq": 3500.0,
        "presence_boost": 3.5, "presence_freq": 3000.0,
        "air_boost": 2.0, "air_freq": 12000.0,
        "deesser_threshold": -22.0,
        "saturation_drive": 1.2,
        "leveler_threshold": -26.0, "leveler_ratio": 2.0,
        "leveler_attack": 12.0, "leveler_release": 200.0,
        "compressor_threshold": -16.0, "compressor_ratio": 4.0,
        "compressor_attack": 1.0, "compressor_release": 80.0,
        "reverb_room_size": 0.08, "reverb_damping": 0.8,
        "reverb_wet": 0.02, "reverb_dry": 0.95, "reverb_width": 0.3,
        "doubler_enabled": False, "doubler_delay_ms": 0.0, "doubler_feedback": 0.0,
        "vocal_target": -8.0, "karaoke_target": -12.0,
        "loudness_target": -16.0, "true_peak": -1.0,
        "input_gain": 1.0, "gain": 1.0,
    },
    "Raw": {
        "noise_reduction": False,
        "pitch_correct": False, "pitch_key": "C", "pitch_scale": "chromatic", "pitch_strength": 0.0,
        "highpass_cutoff": 20.0,
        "low_cut_db": 0.0, "low_cut_freq": 200.0,
        "gate_enabled": False, "gate_threshold_db": -60.0,
        "boxiness_db": 0.0, "boxiness_freq": 400.0,
        "harshness_db": 0.0, "harshness_freq": 3500.0,
        "presence_boost": 0.0, "presence_freq": 5000.0,
        "air_boost": 0.0, "air_freq": 12000.0,
        "deesser_threshold": 0.0,
        "saturation_drive": 0.0,
        "leveler_threshold": 0.0, "leveler_ratio": 1.0,
        "leveler_attack": 10.0, "leveler_release": 100.0,
        "compressor_threshold": 0.0, "compressor_ratio": 1.0,
        "compressor_attack": 10.0, "compressor_release": 100.0,
        "reverb_room_size": 0.0, "reverb_damping": 1.0,
        "reverb_wet": 0.0, "reverb_dry": 1.0, "reverb_width": 0.0,
        "doubler_enabled": False, "doubler_delay_ms": 0.0, "doubler_feedback": 0.0,
        "vocal_target": -8.0, "karaoke_target": -12.0,
        "loudness_target": -14.0, "true_peak": -1.0,
        "input_gain": 1.0, "gain": 1.0,
    },
}

DEFAULT_PARAMS = dict(PRESETS["Studio Clean"])


def _build_effects_chain(params: dict):
    from pedalboard import (
        Compressor, HighpassFilter, Pedalboard, Reverb,
        PeakFilter, HighShelfFilter, LowShelfFilter,
        Distortion, Limiter, Delay,
    )
    plugins = []

    plugins.append(HighpassFilter(cutoff_frequency_hz=params.get("highpass_cutoff", 80.0)))

    low_cut = params.get("low_cut_db", 0.0)
    if low_cut < 0:
        plugins.append(LowShelfFilter(
            cutoff_frequency_hz=params.get("low_cut_freq", 250.0),
            gain_db=low_cut,
        ))

    boxiness_db = params.get("boxiness_db", 0.0)
    if boxiness_db < 0:
        plugins.append(PeakFilter(
            cutoff_frequency_hz=params.get("boxiness_freq", 400.0),
            gain_db=boxiness_db,
            q=1.5,
        ))

    harshness_db = params.get("harshness_db", 0.0)
    if harshness_db < 0:
        plugins.append(PeakFilter(
            cutoff_frequency_hz=params.get("harshness_freq", 3500.0),
            gain_db=harshness_db,
            q=2.0,
        ))

    if params.get("leveler_threshold", 0) < 0:
        plugins.append(Compressor(
            threshold_db=params["leveler_threshold"],
            ratio=params.get("leveler_ratio", 2.0),
            attack_ms=params.get("leveler_attack", 10.0),
            release_ms=params.get("leveler_release", 150.0),
        ))

    if params.get("compressor_threshold", 0) < 0:
        plugins.append(Compressor(
            threshold_db=params["compressor_threshold"],
            ratio=params.get("compressor_ratio", 3.0),
            attack_ms=params.get("compressor_attack", 5.0),
            release_ms=params.get("compressor_release", 80.0),
        ))

    drive = params.get("saturation_drive", 0.0)
    if drive > 0:
        plugins.append(Distortion(drive_db=drive))

    presence = params.get("presence_boost", 0.0)
    if presence > 0:
        plugins.append(PeakFilter(
            cutoff_frequency_hz=params.get("presence_freq", 3000.0),
            gain_db=presence,
            q=0.8,
        ))

    air = params.get("air_boost", 0.0)
    if air > 0:
        plugins.append(HighShelfFilter(
            cutoff_frequency_hz=params.get("air_freq", 12000.0),
            gain_db=air,
        ))

    plugins.append(Limiter(
        threshold_db=-3.0,
        release_ms=100,
    ))

    pre_delay = params.get("pre_delay_ms", 0.0)
    if pre_delay > 0:
        plugins.append(Delay(
            delay_seconds=pre_delay / 1000.0,
            feedback=0.0,
            mix=1.0,
        ))

    if params.get("reverb_wet", 0) > 0:
        plugins.append(Reverb(
            room_size=params.get("reverb_room_size", 0.25),
            damping=params.get("reverb_damping", 0.5),
            wet_level=params["reverb_wet"],
            dry_level=params.get("reverb_dry", 0.85),
            width=params.get("reverb_width", 0.7),
        ))

    return Pedalboard(plugins)


def _deess(audio: np.ndarray, sr: int, threshold_db: float = -20.0,
           ratio: float = 3.0, split_freq: float = 6000.0) -> np.ndarray:
    if threshold_db >= 0 or len(audio) == 0:
        return audio

    from scipy.signal import butter, sosfiltfilt

    mono = audio if audio.ndim == 1 else np.mean(audio, axis=1)
    mono = mono.astype(np.float32)

    sos = butter(4, split_freq / (sr / 2), btype='high', output='sos')
    high = sosfiltfilt(sos, mono).astype(np.float32)

    env = np.abs(high)
    win = max(1, int(sr * 0.03))
    env = np.convolve(env, np.ones(win) / win, mode='same')

    threshold_lin = 10 ** (threshold_db / 20)
    gain = np.ones_like(env)
    over = env > threshold_lin
    if np.any(over):
        oe = env[over]
        gain[over] = (threshold_lin * (oe / threshold_lin) ** (1.0 / ratio)) / oe

    low = mono - high
    mono_out = (low + high * gain).astype(np.float32)

    if audio.ndim == 2:
        return np.column_stack([mono_out, mono_out])
    return mono_out


def _apply_vocal_doubler(audio: np.ndarray, sr: int, delay_ms: float = 12.0,
                         feedback: float = 0.15) -> np.ndarray:
    if delay_ms <= 0 or len(audio) == 0:
        return audio
    delay_samples = int(sr * delay_ms / 1000)
    if delay_samples >= len(audio):
        return audio

    stereo = np.column_stack([audio, audio]).astype(np.float32)

    left_delay = int(delay_samples * 0.6)
    right_delay = delay_samples

    if left_delay < len(audio):
        l_tap = np.zeros_like(audio)
        l_tap[left_delay:] = audio[:-left_delay] * 0.25
        stereo[:, 0] += l_tap

    if right_delay < len(audio):
        r_tap = np.zeros_like(audio)
        r_tap[right_delay:] = audio[:-right_delay] * 0.25
        stereo[:, 1] += r_tap

    target = np.max(np.abs(audio))
    if target > 0:
        ch_peak = np.max(np.abs(stereo), axis=0)
        nz = ch_peak > 0
        stereo[:, nz] *= target / ch_peak[nz]

    return stereo


def apply_effects(vocal: np.ndarray, sr: int, params: dict,
                  karaoke_path: Optional[str] = None,
                  output_path: str = "kore_studio_output.wav",
                  noise_reducer: Optional['NoiseReducer'] = None) -> np.ndarray:
    from app.pipeline.noise_reducer_service import NoiseReducer
    from app.pipeline.pitch_correct import auto_pitch_correct
    import librosa
    import pyloudnorm as pyln
    from pedalboard import Limiter

    processed = vocal.copy()
    if processed.ndim == 2:
        processed = np.mean(processed, axis=1)

    console.print("\n[bold cyan]Processing Pipeline[/bold cyan]")

    if params.get("noise_reduction"):
        nr_limit = params.get("nr_atten_lim_db", 6.0)
        console.print(f"  [yellow]→[/yellow] Noise reduction (DeepFilterNet, max {nr_limit}dB)...")
        nr = noise_reducer if noise_reducer is not None else NoiseReducer()
        processed = nr.reduce(processed, sr, atten_lim_db=nr_limit)

    if params.get("gate_enabled", True):
        gate_db = params.get("gate_threshold_db", -60.0)
        console.print(f"  [yellow]→[/yellow] Noise gate (threshold {gate_db}dB)...")
        from app.pipeline.device_io import NoiseGate
        gate = NoiseGate(
            threshold_db=gate_db,
            attack_ms=5.0, release_ms=150.0, hold_ms=200.0,
            sample_rate=sr,
        )
        processed = gate.process(processed)

    if params.get("pitch_correct") and params.get("pitch_strength", 0) > 0:
        key = params.get("pitch_key", "C")
        scale = params.get("pitch_scale", "chromatic")
        strength = params.get("pitch_strength", 0.8)
        console.print(f"  [yellow]→[/yellow] Pitch correction ({key} {scale}, strength={strength})...")
        processed = auto_pitch_correct(processed, sr, key=key, scale=scale, strength=strength)

    console.print("  [yellow]→[/yellow] Vocal effects chain...")
    chain = _build_effects_chain(params)
    audio_2d = processed[np.newaxis, :]
    audio_2d = chain(audio_2d, sample_rate=sr)
    processed = audio_2d[0]

    gain = params.get("gain", 1.0)
    processed = np.clip(processed * gain, -1.0, 1.0)

    deess_thresh = params.get("deesser_threshold", 0.0)
    if deess_thresh < 0:
        console.print("  [yellow]→[/yellow] De-esser (sibilance control, freq-selective)...")
        processed = _deess(processed, sr, threshold_db=deess_thresh)

    use_doubler = params.get("doubler_enabled", False)
    doubler_delay = params.get("doubler_delay_ms", 12.0)
    doubler_feedback = params.get("doubler_feedback", 0.15)

    if karaoke_path:
        console.print("  [yellow]→[/yellow] Mixing with karaoke...")
        karaoke, k_sr = sf.read(karaoke_path, dtype='float32')
        if k_sr != sr:
            karaoke = librosa.resample(karaoke.T, orig_sr=k_sr, target_sr=sr).T

        meter = pyln.Meter(sr)
        inst_loudness = meter.integrated_loudness(karaoke)
        inst_target_lufs = -18.0
        if not np.isinf(inst_loudness):
            karaoke = pyln.normalize.loudness(karaoke, inst_loudness, inst_target_lufs)
            console.print(f"  [dim]Instrumental normalized: {inst_loudness:.1f} → {inst_target_lufs} LUFS[/dim]")

        inst_peak = np.max(np.abs(karaoke))
        inst_peak_db = 20 * np.log10(max(inst_peak, 1e-10))
        if inst_peak_db > -1.0:
            karaoke *= 10 ** ((-2.0 - inst_peak_db) / 20)
            console.print(f"  [dim]Instrumental peak reduced: {inst_peak_db:.1f} → -2.0 dBFS[/dim]")

        if use_doubler and processed.ndim == 1:
            console.print("  [yellow]→[/yellow] Vocal doubler (stereo width)...")
            processed_stereo = _apply_vocal_doubler(processed, sr, doubler_delay, doubler_feedback)
        else:
            processed_stereo = processed
            if processed_stereo.ndim == 1:
                processed_stereo = np.column_stack([processed_stereo, processed_stereo])

        if karaoke.ndim == 1:
            karaoke = np.column_stack([karaoke, karaoke])

        duck_depth = params.get("duck_depth_db", 2.0)
        if duck_depth > 0:
            console.print(f"  [yellow]→[/yellow] Multiband ducking ({duck_depth}dB @ 1-4kHz)...")
            from scipy.signal import butter, sosfiltfilt

            vocal_env = np.sqrt(np.mean(processed_stereo ** 2, axis=1)) if processed_stereo.ndim == 2 else np.abs(processed_stereo)
            env_smooth = np.convolve(vocal_env, np.ones(4800) / 4800, mode='same')
            threshold = np.percentile(env_smooth[env_smooth > 0], 25) if np.any(env_smooth > 0) else 0
            duck_gain = np.where(env_smooth > threshold, 10 ** (-duck_depth / 20), 1.0)

            sos = butter(4, [1000.0 / (sr / 2), 4000.0 / (sr / 2)], btype='band', output='sos')
            duck_len = min(len(duck_gain), len(karaoke))
            for ch in range(karaoke.shape[1]):
                mid = sosfiltfilt(sos, karaoke[:duck_len, ch])
                karaoke[:duck_len, ch] = karaoke[:duck_len, ch] - mid + mid * duck_gain[:duck_len]

        meter = pyln.Meter(sr)
        inst_loud = meter.integrated_loudness(karaoke)
        vocal_loud = meter.integrated_loudness(processed_stereo)
        if not (np.isinf(inst_loud) or np.isinf(vocal_loud)):
            processed_stereo = pyln.normalize.loudness(processed_stereo, vocal_loud, inst_loud)
            console.print(
                f"  [dim]Vocal matched to instrumental: "
                f"{vocal_loud:.1f} → {inst_loud:.1f} LUFS[/dim]"
            )

        min_len = min(len(processed_stereo), len(karaoke))
        processed_stereo = processed_stereo[:min_len]
        karaoke = karaoke[:min_len]

        mixed = processed_stereo + karaoke

        true_peak_target = params.get("true_peak", -1.0)
        target_linear = 10 ** (true_peak_target / 20.0)

        def _measure_true_peak(sig):
            chans = [sig] if sig.ndim == 1 else [sig[:, c] for c in range(sig.shape[1])]
            return max(
                float(np.max(np.abs(librosa.resample(ch, orig_sr=sr, target_sr=sr * 4))))
                for ch in chans
            )

        tp = _measure_true_peak(mixed)
        if tp > target_linear:
            backoff = tp / target_linear
            mixed /= backoff
            console.print(f"  [dim]Pre-limit backoff: -{20*np.log10(backoff):.1f}dB (true peak {20*np.log10(max(tp, 1e-10)):.1f} dBTP)[/dim]")

        if mixed.ndim == 2:
            mixed_fmt = mixed.T.copy()
        else:
            mixed_fmt = mixed[np.newaxis, :].copy()

        limiter = Limiter(threshold_db=true_peak_target, release_ms=100)
        limited = limiter(mixed_fmt, sample_rate=sr)

        if mixed.ndim == 2:
            final = limited.T
        else:
            final = limited[0]

        out_tp = _measure_true_peak(final)
        if out_tp > target_linear:
            final *= target_linear / out_tp
            console.print(
                f"  [dim]ISP backoff: -{20*np.log10(out_tp / target_linear):.1f}dB "
                f"({20*np.log10(max(out_tp, 1e-10)):.1f} → {true_peak_target:.1f} dBTP)[/dim]"
            )
    else:
        final = processed

    sf.write(output_path, final, sr, subtype="PCM_24")
    console.print(f"  [green]✓[/green] Saved to [bold]{output_path}[/bold]")

    try:
        from app.tools.analyze import analyze
        result = analyze(output_path)
        status = "[green]PASS[/green]" if result.all_pass else "[red]FAIL[/red]"
        console.print(f"\n  [bold]Diagnostic:[/bold] {status}")
        console.print(f"  Loudness: {result.integrated_loudness_lufs} LUFS | Peak: {result.true_peak_dbtp} dBTP | DC: {result.dc_offset}")
        if result.failures:
            for f in result.failures:
                console.print(f"  [yellow]⚠[/yellow] {f}")
    except Exception:
        pass

    return final


def process_files(vocal_path: str, karaoke_path: str, output_path: str, params: dict,
                  noise_reducer: Optional['NoiseReducer'] = None) -> np.ndarray:
    vocal, sr = sf.read(vocal_path, dtype='float32')
    return apply_effects(vocal, sr, params, karaoke_path=karaoke_path,
                         output_path=output_path, noise_reducer=noise_reducer)
