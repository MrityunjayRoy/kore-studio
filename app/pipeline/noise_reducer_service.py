import numpy as np
import torch
import librosa
from df.enhance import enhance, init_df


def _resample(audio: np.ndarray, orig_sr: int, target_sr: int, target_samples: int | None = None) -> np.ndarray:
    resampled = librosa.resample(audio, orig_sr=orig_sr, target_sr=target_sr, res_type="soxr_hq")
    if target_samples is not None and resampled.shape[-1] != target_samples:
        if resampled.shape[-1] > target_samples:
            resampled = resampled[..., :target_samples]
        else:
            pad = [(0, 0)] * (resampled.ndim - 1) + [(0, target_samples - resampled.shape[-1])]
            resampled = np.pad(resampled, pad, mode="constant")
    return resampled


class NoiseReducer:
    def __init__(self) -> None:
        self.model, self.df_state, _ = init_df()
        self.model_sr: int = self.df_state.sr()

    def reduce(self, audio: np.ndarray, sr: int) -> np.ndarray:
        n_samples = audio.shape[-1]
        needs_resample = sr != self.model_sr

        if needs_resample:
            audio = _resample(audio, orig_sr=sr, target_sr=self.model_sr)

        if audio.ndim == 1:
            audio_tensor = torch.from_numpy(audio).unsqueeze(0)
        else:
            audio_tensor = torch.from_numpy(audio)

        with torch.no_grad():
            enhanced = enhance(self.model, self.df_state, audio_tensor)

        enhanced_np = enhanced.cpu().numpy()
        if enhanced_np.ndim == 2 and enhanced_np.shape[0] == 1:
            enhanced_np = enhanced_np.squeeze(0)

        if needs_resample:
            enhanced_np = _resample(enhanced_np, orig_sr=self.model_sr, target_sr=sr, target_samples=n_samples)

        return enhanced_np
