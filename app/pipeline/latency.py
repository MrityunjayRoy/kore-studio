"""Latency measurement and compensation for live-monitoring recording.

Generates a calibration signal, plays it through the output device while
simultaneously recording from the input device, then cross-correlates to
find the round-trip sample offset.

Usage:
    from app.pipeline.latency import measure_latency, LatencyCache
    offset_samples = measure_latency(input_dev_id, output_dev_id, sr)
"""
import json
import os
from typing import Optional

import numpy as np
import pyaudio
from scipy import signal as scipy_signal


CACHE_FILE = os.path.join(os.path.expanduser("~"), ".kore_latency_cache.json")


def generate_calibration_signal(sr: int = 48000, duration_ms: int = 100) -> np.ndarray:
    """Generate a distinctive chirp for latency measurement."""
    n_samples = int(sr * duration_ms / 1000)
    t = np.linspace(0, duration_ms / 1000, n_samples, endpoint=False, dtype=np.float32)
    f0, f1 = 1000.0, 8000.0
    phase = 2 * np.pi * (f0 * t + (f1 - f0) * t ** 2 / (2 * duration_ms / 1000))
    chirp = np.sin(phase).astype(np.float32)
    envelope = np.ones_like(chirp)
    attack = int(sr * 0.005)
    release = int(sr * 0.005)
    if len(envelope) > attack:
        envelope[:attack] = np.linspace(0, 1, attack)
    if len(envelope) > release:
        envelope[-release:] = np.linspace(1, 0, release)
    return chirp * envelope * 0.5


def measure_latency(input_device_id: int, output_device_id: int,
                    sample_rate: int = 48000, chunk_size: int = 2048,
                    duration_ms: int = 500) -> Optional[int]:
    """Measure round-trip latency in samples between output and input devices.

    Returns the offset in samples (positive = input is delayed relative to output),
    or None if measurement failed.
    """
    pa = pyaudio.PyAudio()
    try:
        cal_signal = generate_calibration_signal(sample_rate, duration_ms=100)
        cal_stereo = np.column_stack([cal_signal, cal_signal]).astype(np.float32)
        silence_pad = np.zeros((int(sample_rate * 0.2), 2), dtype=np.float32)
        playback_signal = np.vstack([silence_pad, cal_stereo, silence_pad])

        recorded_chunks = []

        out_stream = pa.open(
            format=pyaudio.paFloat32,
            channels=2,
            rate=sample_rate,
            output=True,
            output_device_index=output_device_id,
            frames_per_buffer=chunk_size,
        )
        in_stream = pa.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=sample_rate,
            input=True,
            input_device_index=input_device_id,
            frames_per_buffer=chunk_size,
        )

        in_stream.read(chunk_size, exception_on_overflow=False)

        pos = 0
        while pos < len(playback_signal):
            end = min(pos + chunk_size, len(playback_signal))
            chunk = playback_signal[pos:end]
            if len(chunk) < chunk_size:
                chunk = np.vstack([chunk, np.zeros((chunk_size - len(chunk), 2), dtype=np.float32)])
            out_stream.write(chunk.tobytes())
            data = in_stream.read(chunk_size, exception_on_overflow=False)
            recorded_chunks.append(np.frombuffer(data, dtype=np.float32).copy())
            pos += chunk_size

        in_stream.stop_stream()
        in_stream.close()
        out_stream.stop_stream()
        out_stream.close()

    except Exception as e:
        print(f"Latency measurement failed: {e}")
        return None
    finally:
        pa.terminate()

    if not recorded_chunks:
        return None

    recorded = np.concatenate(recorded_chunks)
    if len(recorded) < len(cal_signal):
        return None

    correlation = scipy_signal.correlate(recorded, cal_signal, mode='full')
    peak_idx = np.argmax(np.abs(correlation))
    offset = peak_idx - (len(cal_signal) - 1)

    return int(offset)


class LatencyCache:
    """Cache latency measurements per device pair."""

    def __init__(self, cache_path: str = CACHE_FILE):
        self.cache_path = cache_path
        self._cache = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save(self):
        with open(self.cache_path, 'w') as f:
            json.dump(self._cache, f, indent=2)

    def _key(self, input_name: str, output_name: str, sr: int, chunk: int) -> str:
        return f"{input_name}|{output_name}|{sr}|{chunk}"

    def get(self, input_name: str, output_name: str,
            sr: int, chunk_size: int) -> Optional[int]:
        key = self._key(input_name, output_name, sr, chunk_size)
        return self._cache.get(key)

    def set(self, input_name: str, output_name: str,
            sr: int, chunk_size: int, offset_samples: int):
        key = self._key(input_name, output_name, sr, chunk_size)
        self._cache[key] = offset_samples
        self._save()

    def get_or_measure(self, input_id: int, output_id: int,
                       input_name: str, output_name: str,
                       sr: int = 48000, chunk_size: int = 2048) -> int:
        cached = self.get(input_name, output_name, sr, chunk_size)
        if cached is not None:
            return cached

        offset = measure_latency(input_id, output_id, sr, chunk_size)
        if offset is not None:
            self.set(input_name, output_name, sr, chunk_size, offset)
            return offset
        return 0


def apply_latency_compensation(vocal: np.ndarray, offset_samples: int) -> np.ndarray:
    """Shift vocal to compensate for measured latency.

    Positive offset = vocal was recorded late = shift it earlier (trim start).
    Negative offset = vocal was recorded early = pad start.
    """
    if offset_samples == 0 or len(vocal) == 0:
        return vocal

    if offset_samples > 0:
        if offset_samples >= len(vocal):
            return vocal
        return vocal[offset_samples:]
    else:
        pad_len = abs(offset_samples)
        return np.concatenate([np.zeros(pad_len, dtype=vocal.dtype), vocal])


def detect_acoustic_bleed(vocal: np.ndarray, instrumental: np.ndarray,
                          sr: int, latency_offset: int = 0,
                          threshold: float = 0.3) -> dict:
    """Detect acoustic bleed by correlating vocal with instrumental.

    Returns dict with 'detected' bool and 'correlation' float.
    """
    comp_vocal = apply_latency_compensation(vocal, latency_offset)

    min_len = min(len(comp_vocal), len(instrumental))
    if min_len < sr:
        return {"detected": False, "correlation": 0.0, "message": "Too short to analyze"}

    if instrumental.ndim == 2:
        inst_mono = np.mean(instrumental, axis=1)
    else:
        inst_mono = instrumental

    v = comp_vocal[:min_len]
    i = inst_mono[:min_len]

    block_size = sr * 2
    n_blocks = min_len // block_size
    if n_blocks == 0:
        return {"detected": False, "correlation": 0.0, "message": "Too short"}

    correlations = []
    for b in range(n_blocks):
        start = b * block_size
        end = start + block_size
        vb = v[start:end]
        ib = i[start:end]
        v_std = np.std(vb)
        i_std = np.std(ib)
        if v_std > 0.001 and i_std > 0.001:
            corr = abs(float(np.corrcoef(vb, ib)[0, 1]))
            correlations.append(corr)

    if not correlations:
        return {"detected": False, "correlation": 0.0, "message": "No analyzable blocks"}

    avg_corr = np.mean(correlations)
    high_corr_blocks = sum(1 for c in correlations if c > threshold)

    detected = avg_corr > threshold or (high_corr_blocks / len(correlations)) > 0.5

    return {
        "detected": bool(detected),
        "correlation": round(float(avg_corr), 3),
        "high_corr_ratio": round(high_corr_blocks / len(correlations), 3),
        "message": "Acoustic bleed detected — use headphones for cleaner recording" if detected else "No significant bleed detected",
    }


def is_headphone_device(device_name: str) -> bool:
    """Heuristic check if a device name suggests headphones."""
    name_lower = device_name.lower()
    keywords = ["headphone", "headset", "earbud", "earphone", "airpod",
                "bluetooth", "wireless", "in-ear", "over-ear", "on-ear",
                "hifi", "studio monitor"]
    return any(kw in name_lower for kw in keywords)
