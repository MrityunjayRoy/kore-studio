import threading
import time
from typing import Optional, Callable

import numpy as np
import pyaudio


def list_input_devices() -> list[dict]:
    pa = pyaudio.PyAudio()
    devices = []
    try:
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0:
                devices.append({
                    "id": i,
                    "name": info["name"],
                    "channels": info["maxInputChannels"],
                    "default_sr": int(info["defaultSampleRate"]),
                })
    finally:
        pa.terminate()
    return devices


def list_output_devices() -> list[dict]:
    pa = pyaudio.PyAudio()
    devices = []
    try:
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info["maxOutputChannels"] > 0:
                devices.append({
                    "id": i,
                    "name": info["name"],
                    "channels": info["maxOutputChannels"],
                    "default_sr": int(info["defaultSampleRate"]),
                })
    finally:
        pa.terminate()
    return devices


def get_default_input_device() -> dict:
    pa = pyaudio.PyAudio()
    try:
        info = pa.get_default_input_device_info()
        return {"id": info["index"], "name": info["name"], "channels": info["maxInputChannels"]}
    finally:
        pa.terminate()


def get_default_output_device() -> dict:
    pa = pyaudio.PyAudio()
    try:
        info = pa.get_default_output_device_info()
        return {"id": info["index"], "name": info["name"], "channels": info["maxOutputChannels"]}
    finally:
        pa.terminate()


class NoiseGate:
    def __init__(self, threshold_db: float = -45.0, attack_ms: float = 10.0,
                 release_ms: float = 200.0, hold_ms: float = 300.0,
                 sample_rate: int = 48000):
        self.threshold = 10 ** (threshold_db / 20.0)
        self.attack_ms = attack_ms
        self.release_ms = release_ms
        self.hold_ms = hold_ms
        self.sample_rate = sample_rate

    def process(self, audio: np.ndarray) -> np.ndarray:
        if len(audio) == 0:
            return audio

        block_size = max(1, int(self.sample_rate * 0.010))  # 10ms blocks
        n_blocks = len(audio) // block_size
        if n_blocks == 0:
            return audio

        trimmed = audio[:n_blocks * block_size]
        reshaped = trimmed.reshape(n_blocks, block_size)
        rms_per_block = np.sqrt(np.mean(reshaped.astype(np.float64) ** 2, axis=1))

        block_duration_ms = block_size / self.sample_rate * 1000
        attack_blocks = self.attack_ms / block_duration_ms
        release_blocks = self.release_ms / block_duration_ms
        hold_blocks = self.hold_ms / block_duration_ms

        attack_inc = 1.0 / max(1, attack_blocks)
        release_dec = 1.0 / max(1, release_blocks)

        gain = np.zeros(n_blocks * block_size, dtype=np.float32)
        env = 0.0
        hold_counter = 0

        for i in range(n_blocks):
            block_rms = rms_per_block[i]
            if block_rms >= self.threshold:
                hold_counter = hold_blocks
                env = min(1.0, env + attack_inc)
            elif hold_counter > 0:
                hold_counter -= 1
                env = 1.0
            else:
                env = max(0.0, env - release_dec)

            start = i * block_size
            end = start + block_size
            gain[start:end] = env

        if n_blocks * block_size < len(audio):
            gain = np.concatenate([gain, np.zeros(len(audio) - n_blocks * block_size, dtype=np.float32)])

        return audio * gain


def remove_dc_offset(audio: np.ndarray) -> np.ndarray:
    if len(audio) == 0:
        return audio
    return audio - np.mean(audio)


def declick(audio: np.ndarray, threshold: float = 0.35,
            kernel_size: int = 5) -> np.ndarray:
    """Remove transient clicks/pops via median-filter interpolation.

    Detects samples that deviate sharply from their local neighbourhood
    (digital clicks, mouth pops, buffer glitches) and replaces only those
    with a median-filtered value. Legitimate transients (consonant attacks)
    are preserved because the threshold targets discrete spikes, not edges.
    """
    if len(audio) == 0:
        return audio
    from scipy.signal import medfilt

    mono = audio if audio.ndim == 1 else np.mean(audio, axis=1)
    mono = mono.astype(np.float32)

    if kernel_size % 2 == 0:
        kernel_size += 1
    if len(mono) < kernel_size:
        return audio

    smoothed = medfilt(mono, kernel_size=kernel_size).astype(np.float32)
    residual = np.abs(mono - smoothed)
    click_mask = residual > threshold
    if not np.any(click_mask):
        return audio

    out = mono.copy()
    out[click_mask] = smoothed[click_mask]

    if audio.ndim == 2:
        return np.column_stack([out, out])
    return out


def soft_clip(audio: np.ndarray, threshold: float = 0.8) -> np.ndarray:
    out = audio.copy()
    mask = np.abs(out) > threshold
    if np.any(mask):
        x = out[mask]
        sign = np.sign(x)
        normalized = (np.abs(x) - threshold) / (1.0 - threshold)
        softened = threshold + (1.0 - threshold) * np.tanh(normalized * 2.0) / np.tanh(2.0)
        out[mask] = sign * np.clip(softened, threshold, 1.0)
    return out


def normalize_recording_level(audio: np.ndarray, target_dbfs: float = -12.0) -> np.ndarray:
    if len(audio) == 0:
        return audio
    peak = np.max(np.abs(audio))
    if peak == 0:
        return audio
    target_linear = 10 ** (target_dbfs / 20.0)
    gain = target_linear / peak
    return audio * gain


def clean_vocal(audio: np.ndarray, sample_rate: int = 48000,
                noise_gate_threshold_db: float = -45.0,
                input_gain: float = 1.0) -> np.ndarray:
    if len(audio) == 0:
        return audio

    cleaned = audio.astype(np.float64) * input_gain
    cleaned = cleaned.astype(np.float32)
    cleaned = remove_dc_offset(cleaned)
    cleaned = declick(cleaned)

    fade_samples = min(int(sample_rate * 0.020), len(cleaned))
    if fade_samples > 0:
        fade_in = np.linspace(0, 1, fade_samples, dtype=np.float32)
        cleaned[:fade_samples] *= fade_in
        fade_out = np.linspace(1, 0, fade_samples, dtype=np.float32)
        cleaned[-fade_samples:] *= fade_out

    cleaned = soft_clip(cleaned, threshold=0.90)

    peak = np.max(np.abs(cleaned))
    if peak > 0.95:
        cleaned *= 0.95 / peak

    return cleaned


class AudioStream:
    def __init__(self, input_device_id: int, output_device_id: int,
                 sample_rate: int = 48000, chunk_size: int = 2048):
        self.input_device_id = input_device_id
        self.output_device_id = output_device_id
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.pa: Optional[pyaudio.PyAudio] = None
        self._recording = threading.Event()
        self._paused = threading.Event()
        self._chunks: list[np.ndarray] = []
        self.monitor_level: float = 0.0
        self.input_gain: float = 1.0
        self._latest_rms: float = 0.0

    def start(self):
        self.pa = pyaudio.PyAudio()

    def stop(self):
        if self.pa:
            self.pa.terminate()
            self.pa = None

    def close(self):
        self.stop()

    def get_rms(self, chunk: np.ndarray) -> float:
        if len(chunk) == 0:
            return 0.0
        return float(np.sqrt(np.mean(chunk.astype(np.float64) ** 2)))

    def record(self, duration: float, on_chunk: Optional[Callable] = None) -> np.ndarray:
        if not self.pa:
            self.start()

        self._chunks = []
        self._recording.set()
        self._paused.clear()
        total_chunks = int(self.sample_rate * duration / self.chunk_size) + 1

        stream = self.pa.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=self.sample_rate,
            input=True,
            input_device_index=self.input_device_id,
            frames_per_buffer=self.chunk_size,
        )

        try:
            for _ in range(total_chunks):
                if not self._recording.is_set():
                    break
                if self._paused.is_set():
                    time.sleep(0.01)
                    continue
                data = stream.read(self.chunk_size, exception_on_overflow=False)
                chunk = np.frombuffer(data, dtype=np.float32).copy()
                self._chunks.append(chunk)
                self._latest_rms = self.get_rms(chunk)
                if on_chunk:
                    on_chunk(chunk)
        finally:
            stream.stop_stream()
            stream.close()
            self._recording.clear()

        if not self._chunks:
            return np.array([], dtype=np.float32)
        raw = np.concatenate(self._chunks)
        return clean_vocal(raw, self.sample_rate, input_gain=self.input_gain)

    def play(self, audio: np.ndarray, on_progress: Optional[Callable] = None):
        if not self.pa:
            self.start()

        if audio.ndim == 2 and audio.shape[0] == 2:
            audio = audio.T
        if audio.ndim == 1:
            audio = np.column_stack([audio, audio])

        audio = np.ascontiguousarray(audio, dtype=np.float32)

        stream = self.pa.open(
            format=pyaudio.paFloat32,
            channels=2,
            rate=self.sample_rate,
            output=True,
            output_device_index=self.output_device_id,
            frames_per_buffer=self.chunk_size,
        )

        total_frames = len(audio)
        played = 0

        try:
            while played < total_frames:
                if not self._recording.is_set():
                    break
                if self._paused.is_set():
                    time.sleep(0.01)
                    continue

                end = min(played + self.chunk_size, total_frames)
                chunk = audio[played:end]
                if len(chunk) < self.chunk_size:
                    pad_len = self.chunk_size - len(chunk)
                    chunk = np.vstack([chunk, np.zeros((pad_len, 2), dtype=np.float32)])

                stream.write(chunk.tobytes())
                played = end
                if on_progress:
                    on_progress(played / total_frames)
        finally:
            stream.stop_stream()
            stream.close()

    def record_with_playback(self, backing_track: np.ndarray, duration: float,
                             on_chunk: Optional[Callable] = None,
                             monitor_level: float = 0.0) -> np.ndarray:
        if not self.pa:
            self.start()

        self._chunks = []
        self._recording.set()
        self._paused.clear()
        self.monitor_level = monitor_level
        self._latest_rms = 0.0

        if backing_track.ndim == 1:
            backing_track = np.column_stack([backing_track, backing_track])

        backing_track = np.ascontiguousarray(backing_track, dtype=np.float32)

        peak = np.max(np.abs(backing_track))
        if peak > 0.95:
            backing_track = backing_track * (0.95 / peak)

        chunk_samples = self.chunk_size
        silence_bytes = (np.zeros((chunk_samples, 2), dtype=np.float32)).tobytes()

        out_bytes_list = []
        pos = 0
        while pos < len(backing_track):
            end = min(pos + chunk_samples, len(backing_track))
            c = backing_track[pos:end]
            if len(c) < chunk_samples:
                c = np.vstack([c, np.zeros((chunk_samples - len(c), 2), dtype=np.float32)])
            out_bytes_list.append(c.tobytes())
            pos += chunk_samples

        raw_input_list: list[bytes] = []
        io_done = threading.Event()
        io_error = [None]
        self._monitor_gain = [monitor_level]
        input_gain = self.input_gain

        def audio_io_thread():
            in_stream = None
            out_stream = None
            try:
                in_stream = self.pa.open(
                    format=pyaudio.paFloat32,
                    channels=1,
                    rate=self.sample_rate,
                    input=True,
                    input_device_index=self.input_device_id,
                    frames_per_buffer=self.chunk_size,
                )
                out_stream = self.pa.open(
                    format=pyaudio.paFloat32,
                    channels=2,
                    rate=self.sample_rate,
                    output=True,
                    output_device_index=self.output_device_id,
                    frames_per_buffer=self.chunk_size,
                )

                total = int(self.sample_rate * duration / self.chunk_size) + 1
                n_out = len(out_bytes_list)

                # Warm-up pre-roll: discard first 2 seconds of input to let
                # USB mic / Bluetooth driver stabilize. Play karaoke from the
                # start so user hears music immediately.
                warmup_chunks = int(self.sample_rate * 2.0 / self.chunk_size)
                warmup_out_pos = 0
                for _ in range(warmup_chunks):
                    in_stream.read(self.chunk_size, exception_on_overflow=False)
                    out_data = out_bytes_list[warmup_out_pos] if warmup_out_pos < n_out else silence_bytes
                    out_stream.write(out_data)
                    warmup_out_pos += 1

                prev_vocal = None
                diagnostic_chunks = min(total, int(self.sample_rate * 5.0 / self.chunk_size))
                diag_log = []
                out_pos = warmup_out_pos

                for i in range(total):
                    if not self._recording.is_set():
                        break

                    while self._paused.is_set() and self._recording.is_set():
                        out_stream.write(silence_bytes)
                        in_stream.read(self.chunk_size, exception_on_overflow=False)
                        time.sleep(0.01)

                    if not self._recording.is_set():
                        break

                    out_data = out_bytes_list[out_pos] if out_pos < n_out else silence_bytes
                    out_pos += 1

                    mg = self._monitor_gain[0]
                    if mg > 0.0:
                        if prev_vocal is not None:
                            backing = np.frombuffer(out_data, dtype=np.float32).copy()
                            vocal_monitor = prev_vocal * mg * 0.4
                            backing[0::2] += vocal_monitor
                            backing[1::2] += vocal_monitor
                            np.clip(backing, -0.95, 0.95, out=backing)
                            out_stream.write(backing.tobytes())
                        else:
                            out_stream.write(out_data)
                        data = in_stream.read(self.chunk_size, exception_on_overflow=False)
                        if input_gain != 1.0:
                            samples = np.frombuffer(data, dtype=np.float32).copy()
                            samples *= input_gain
                            np.clip(samples, -1.0, 1.0, out=samples)
                            data = samples.astype(np.float32).tobytes()
                        raw_input_list.append(data)
                        if i < diagnostic_chunks:
                            s = np.frombuffer(data, dtype=np.float32)
                            rms = np.sqrt(np.mean(s.astype(np.float64) ** 2))
                            db = 20 * np.log10(max(rms, 1e-10))
                            diag_log.append((i, round(db, 1)))
                        prev_vocal = np.frombuffer(data, dtype=np.float32).copy()
                    else:
                        out_stream.write(out_data)
                        data = in_stream.read(self.chunk_size, exception_on_overflow=False)
                        if input_gain != 1.0:
                            samples = np.frombuffer(data, dtype=np.float32).copy()
                            samples *= input_gain
                            np.clip(samples, -1.0, 1.0, out=samples)
                            data = samples.astype(np.float32).tobytes()
                        raw_input_list.append(data)
                        if i < diagnostic_chunks:
                            s = np.frombuffer(data, dtype=np.float32)
                            rms = np.sqrt(np.mean(s.astype(np.float64) ** 2))
                            db = 20 * np.log10(max(rms, 1e-10))
                            diag_log.append((i, round(db, 1)))

                self._diag_log = diag_log

            except Exception as e:
                io_error[0] = e
            finally:
                if in_stream:
                    in_stream.stop_stream()
                    in_stream.close()
                if out_stream:
                    out_stream.stop_stream()
                    out_stream.close()
                io_done.set()

        ui_thread = None
        if on_chunk:
            def ui_updater():
                last = 0
                while not io_done.is_set():
                    n = len(raw_input_list)
                    if n > last:
                        for j in range(last, n):
                            c = np.frombuffer(raw_input_list[j], dtype=np.float32)
                            self._latest_rms = float(np.sqrt(np.mean(c.astype(np.float64) ** 2)))
                            on_chunk(c)
                        last = n
                    time.sleep(0.02)

            ui_thread = threading.Thread(target=ui_updater, daemon=True)
            ui_thread.start()

        io_thread = threading.Thread(target=audio_io_thread, daemon=True)
        io_thread.start()

        while not io_done.is_set():
            time.sleep(0.05)

        if ui_thread:
            ui_thread.join(timeout=1)

        if io_error[0]:
            raise RuntimeError(f"Audio I/O error: {io_error[0]}")

        if not raw_input_list:
            return np.array([], dtype=np.float32)

        if hasattr(self, '_diag_log') and self._diag_log:
            print("\n[Capture Diagnostics — First 5s]")
            for chunk_idx, db in self._diag_log[:10]:
                t_ms = chunk_idx * self.chunk_size / self.sample_rate * 1000
                bar = "█" * max(1, int((db + 60) / 60 * 20)) if db > -60 else "░"
                print(f"  Chunk {chunk_idx:3d} ({t_ms:6.0f}ms): {db:>6.1f} dBFS {bar}")
            if len(self._diag_log) > 10:
                rest = [d[1] for d in self._diag_log[10:]]
                print(f"  Chunks 10-{len(self._diag_log)-1}: avg {sum(rest)/len(rest):.1f} dBFS")
            print()

        raw_audio = np.frombuffer(b"".join(raw_input_list), dtype=np.float32).copy()
        cleaned = clean_vocal(raw_audio, self.sample_rate, input_gain=input_gain)

        expected_samples = len(backing_track)
        if len(cleaned) > expected_samples:
            cleaned = cleaned[:expected_samples]
        elif len(cleaned) < expected_samples:
            cleaned = np.concatenate([cleaned, np.zeros(expected_samples - len(cleaned), dtype=np.float32)])

        return cleaned

    def set_monitor_level(self, level: float):
        self.monitor_level = max(0.0, min(1.0, level))
        if hasattr(self, '_monitor_gain'):
            self._monitor_gain[0] = self.monitor_level

    def stop_recording(self):
        self._recording.clear()

    def toggle_pause(self):
        if self._paused.is_set():
            self._paused.clear()
        else:
            self._paused.set()

    @property
    def is_paused(self) -> bool:
        return self._paused.is_set()
