import io

import librosa
import numpy as np
import soundfile as sf
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from app.database import get_audio, insert_audio

router = APIRouter()

TARGET_SR = 44100


def _ensure_2d(data: np.ndarray) -> np.ndarray:
    if data.ndim == 1:
        data = data[np.newaxis, :]
    return data


@router.post("/upload")
async def upload_audio(
    request: Request,
    vocal: UploadFile = File(...),
    karaoke: UploadFile = File(...),
):
    vocal_bytes = await vocal.read()
    karaoke_bytes = await karaoke.read()

    vocal_data, _ = librosa.load(
        io.BytesIO(vocal_bytes), sr=TARGET_SR, mono=False
    )
    karaoke_data, _ = librosa.load(
        io.BytesIO(karaoke_bytes), sr=TARGET_SR, mono=False
    )

    vocal_data = _ensure_2d(vocal_data)
    karaoke_data = _ensure_2d(karaoke_data)

    # Match channels: if one is mono and the other stereo, duplicate mono channel
    if vocal_data.shape[0] == 1 and karaoke_data.shape[0] == 2:
        vocal_data = np.repeat(vocal_data, 2, axis=0)
    elif karaoke_data.shape[0] == 1 and vocal_data.shape[0] == 2:
        karaoke_data = np.repeat(karaoke_data, 2, axis=0)

    # Step 2: Vocal Cleanup via DeepFilterNet
    vocal_data = request.app.state.noise_reducer.reduce(vocal_data, TARGET_SR)

    # Transpose to (n_samples, n_channels) for storage convention
    vocal_data = vocal_data.T
    karaoke_data = karaoke_data.T

    def _serialise(arr: np.ndarray) -> bytes:
        buf = io.BytesIO()
        np.save(buf, arr, allow_pickle=False)
        return buf.getvalue()

    vocal_id = insert_audio(
        filename=vocal.filename or "vocal.wav",
        sample_rate=TARGET_SR,
        num_channels=vocal_data.shape[1],
        num_samples=vocal_data.shape[0],
        audio_blob=_serialise(vocal_data),
    )
    karaoke_id = insert_audio(
        filename=karaoke.filename or "karaoke.wav",
        sample_rate=TARGET_SR,
        num_channels=karaoke_data.shape[1],
        num_samples=karaoke_data.shape[0],
        audio_blob=_serialise(karaoke_data),
    )

    return {"vocal_id": vocal_id, "karaoke_id": karaoke_id}


@router.get("/audio/{audio_id}")
async def download_audio(audio_id: str):
    record = get_audio(audio_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Audio not found")

    buf = io.BytesIO(record["audio_blob"])
    arr = np.load(buf, allow_pickle=False)

    wav_buf = io.BytesIO()
    sf.write(wav_buf, arr, samplerate=record["sample_rate"], format="WAV")
    wav_buf.seek(0)

    return StreamingResponse(
        wav_buf,
        media_type="audio/wav",
        headers={"Content-Disposition": f'attachment; filename="{record["filename"]}"'},
    )
