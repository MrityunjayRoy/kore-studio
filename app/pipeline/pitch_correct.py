import numpy as np
import librosa
import psola


NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

SCALES = {
    "chromatic": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "pentatonic_major": [0, 2, 4, 7, 9],
    "pentatonic_minor": [0, 3, 5, 7, 10],
}


def _note_to_midi(note: str) -> int:
    note = note.strip()
    name = note[:-1] if len(note) > 1 and note[-1].isdigit() else note
    octave = int(note[-1]) if len(note) > 1 and note[-1].isdigit() else 4
    if name not in NOTE_NAMES:
        raise ValueError(f"Unknown note name: {name}. Valid: {NOTE_NAMES}")
    return octave * 12 + NOTE_NAMES.index(name) + 12


def _midi_to_freq(midi: int) -> float:
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))


def _freq_to_midi(freq: float) -> float:
    if freq <= 0:
        return 0.0
    return 69.0 + 12.0 * np.log2(freq / 440.0)


def _get_allowed_midi_notes(key: str, scale: str, min_midi: int = 36, max_midi: int = 84) -> list[int]:
    root_midi = _note_to_midi(key + "0")
    intervals = SCALES.get(scale, SCALES["chromatic"])
    notes = []
    for octave in range(12):
        for interval in intervals:
            midi = root_midi + octave * 12 + interval
            if min_midi <= midi <= max_midi:
                notes.append(midi)
    return sorted(set(notes))


def detect_pitch(audio: np.ndarray, sr: int, frame_length: int = 2048,
                 hop_length: int = 512) -> np.ndarray:
    if audio.ndim == 2:
        audio = np.mean(audio, axis=1)

    f0, voiced_flag, voiced_probs = librosa.pyin(
        audio,
        fmin=librosa.note_to_hz("C2"),
        fmax=librosa.note_to_hz("C7"),
        sr=sr,
        frame_length=frame_length,
        hop_length=hop_length,
    )
    f0 = np.nan_to_num(f0, nan=0.0)
    return f0


def quantize_to_scale(f0: np.ndarray, key: str = "C",
                      scale: str = "chromatic") -> np.ndarray:
    allowed_notes = _get_allowed_midi_notes(key, scale)
    if not allowed_notes:
        return f0.copy()

    allowed_freqs = [_midi_to_freq(n) for n in allowed_notes]
    target_f0 = np.zeros_like(f0)

    for i, freq in enumerate(f0):
        if freq <= 0:
            target_f0[i] = 0.0
            continue
        distances = [abs(freq - af) for af in allowed_freqs]
        best_idx = np.argmin(distances)
        target_f0[i] = allowed_freqs[best_idx]

    return target_f0


def correct_pitch(audio: np.ndarray, sr: int, f0_orig: np.ndarray,
                  f0_target: np.ndarray, hop_length: int = 512,
                  strength: float = 1.0) -> np.ndarray:
    if audio.ndim == 2:
        audio = np.mean(audio, axis=1)

    blended_f0 = np.where(
        f0_target > 0,
        f0_orig + (f0_target - f0_orig) * strength,
        f0_orig
    )

    valid_mask = (f0_orig > 0) & (blended_f0 > 0)
    if not np.any(valid_mask):
        return audio

    try:
        corrected = psola.vocode(
            audio,
            sample_rate=sr,
            target_f0=blended_f0,
            hop_length=hop_length,
        )
        min_len = min(len(audio), len(corrected))
        result = audio.copy()
        result[:min_len] = corrected[:min_len]
        return result
    except Exception:
        return audio


def auto_pitch_correct(audio: np.ndarray, sr: int, key: str = "C",
                       scale: str = "chromatic", strength: float = 0.8,
                       frame_length: int = 2048, hop_length: int = 512) -> np.ndarray:
    f0 = detect_pitch(audio, sr, frame_length, hop_length)
    target_f0 = quantize_to_scale(f0, key, scale)
    return correct_pitch(audio, sr, f0, target_f0, hop_length, strength)
