import tempfile
import os
import shutil
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

import soundfile as sf
import numpy as np

try:
    from fastapi import FastAPI, UploadFile, File, Form
    from fastapi.responses import FileResponse
    import uvicorn
except ImportError:
    import subprocess
    import sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "fastapi", "uvicorn", "python-multipart"])
    from fastapi import FastAPI, UploadFile, File, Form
    from fastapi.responses import FileResponse
    import uvicorn

from app.pipeline.studio_pipeline import PRESETS, process_files
from app.pipeline.noise_reducer_service import NoiseReducer

logging.basicConfig(level=logging.INFO, format='%(asctime)s [KoreAPI] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

WORK_DIR = Path(tempfile.mkdtemp(prefix="kore_api_"))
_noise_reducer: Optional[NoiseReducer] = None

_PRESET_ALIASES = {k.lower(): v for v in PRESETS for k in [v, v.lower()]}


def _resolve_preset(name: str) -> dict:
    if name in PRESETS:
        return dict(PRESETS[name])
    lower = name.lower()
    for key in PRESETS:
        if key.lower() == lower or lower == key.lower().split()[0]:
            return dict(PRESETS[key])
    logger.warning(f"Unknown preset '{name}', falling back to Studio Clean")
    return dict(PRESETS["Studio Clean"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _noise_reducer
    logger.info("Loading DeepFilterNet noise reducer (shared across requests)...")
    _noise_reducer = NoiseReducer()
    yield
    shutil.rmtree(WORK_DIR, ignore_errors=True)


app = FastAPI(title="Kore Processing API", lifespan=lifespan)


@app.post("/process")
async def process(
    vocal: UploadFile = File(...),
    instrumental: UploadFile = File(...),
    preset: str = Form("Studio Clean"),
    pitch_correct: Optional[bool] = Form(None),
    pitch_key: Optional[str] = Form(None),
    pitch_scale: Optional[str] = Form(None),
    pitch_strength: Optional[float] = Form(None),
    highpass_cutoff: Optional[float] = Form(None),
    compressor_threshold: Optional[float] = Form(None),
    compressor_ratio: Optional[float] = Form(None),
    compressor_attack: Optional[float] = Form(None),
    compressor_release: Optional[float] = Form(None),
    reverb_room_size: Optional[float] = Form(None),
    reverb_damping: Optional[float] = Form(None),
    reverb_wet: Optional[float] = Form(None),
    reverb_dry: Optional[float] = Form(None),
    reverb_width: Optional[float] = Form(None),
    vocal_target: Optional[float] = Form(None),
    karaoke_target: Optional[float] = Form(None),
    loudness_target: Optional[float] = Form(None),
    true_peak: Optional[float] = Form(None),
    noise_reduction: Optional[bool] = Form(None),
    saturation_drive: Optional[float] = Form(None),
    presence_boost: Optional[float] = Form(None),
    presence_freq: Optional[float] = Form(None),
    air_boost: Optional[float] = Form(None),
    air_freq: Optional[float] = Form(None),
    deesser_threshold: Optional[float] = Form(None),
    doubler_enabled: Optional[bool] = Form(None),
    doubler_delay_ms: Optional[float] = Form(None),
    doubler_feedback: Optional[float] = Form(None),
    duck_depth_db: Optional[float] = Form(None),
    gate_enabled: Optional[bool] = Form(None),
    gate_threshold_db: Optional[float] = Form(None),
    low_cut_db: Optional[float] = Form(None),
    low_cut_freq: Optional[float] = Form(None),
    boxiness_db: Optional[float] = Form(None),
    boxiness_freq: Optional[float] = Form(None),
    harshness_db: Optional[float] = Form(None),
    harshness_freq: Optional[float] = Form(None),
    leveler_threshold: Optional[float] = Form(None),
    leveler_ratio: Optional[float] = Form(None),
    leveler_attack: Optional[float] = Form(None),
    leveler_release: Optional[float] = Form(None),
    input_gain: Optional[float] = Form(None),
    gain: Optional[float] = Form(None),
):
    logger.info(f"Request: preset={preset}, vocal={vocal.filename}, inst={instrumental.filename}")
    params = _resolve_preset(preset)

    float_overrides = {
        "pitch_strength": pitch_strength,
        "highpass_cutoff": highpass_cutoff,
        "compressor_threshold": compressor_threshold,
        "compressor_ratio": compressor_ratio,
        "compressor_attack": compressor_attack,
        "compressor_release": compressor_release,
        "reverb_room_size": reverb_room_size,
        "reverb_damping": reverb_damping,
        "reverb_wet": reverb_wet,
        "reverb_dry": reverb_dry,
        "reverb_width": reverb_width,
        "vocal_target": vocal_target,
        "karaoke_target": karaoke_target,
        "loudness_target": loudness_target,
        "true_peak": true_peak,
        "saturation_drive": saturation_drive,
        "presence_boost": presence_boost,
        "presence_freq": presence_freq,
        "air_boost": air_boost,
        "air_freq": air_freq,
        "deesser_threshold": deesser_threshold,
        "doubler_delay_ms": doubler_delay_ms,
        "doubler_feedback": doubler_feedback,
        "duck_depth_db": duck_depth_db,
        "gate_threshold_db": gate_threshold_db,
        "low_cut_db": low_cut_db,
        "low_cut_freq": low_cut_freq,
        "boxiness_db": boxiness_db,
        "boxiness_freq": boxiness_freq,
        "harshness_db": harshness_db,
        "harshness_freq": harshness_freq,
        "leveler_threshold": leveler_threshold,
        "leveler_ratio": leveler_ratio,
        "leveler_attack": leveler_attack,
        "leveler_release": leveler_release,
        "input_gain": input_gain,
        "gain": gain,
    }

    bool_overrides = {
        "pitch_correct": pitch_correct,
        "noise_reduction": noise_reduction,
        "doubler_enabled": doubler_enabled,
        "gate_enabled": gate_enabled,
    }

    str_overrides = {
        "pitch_key": pitch_key,
        "pitch_scale": pitch_scale,
    }

    for key, value in float_overrides.items():
        if value is not None:
            params[key] = value

    for key, value in bool_overrides.items():
        if value is not None:
            params[key] = value

    for key, value in str_overrides.items():
        if value is not None:
            params[key] = value

    job_id = os.urandom(4).hex()
    job_dir = WORK_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    try:
        vocal_path = job_dir / "vocal.wav"
        inst_path = job_dir / "instrumental.wav"
        out_path = job_dir / "output.wav"
        conv_path = job_dir / "output_16bit.wav"

        with open(vocal_path, "wb") as f:
            f.write(await vocal.read())
        with open(inst_path, "wb") as f:
            f.write(await instrumental.read())

        logger.info(f"Processing with {len(params)} params...")
        process_files(str(vocal_path), str(inst_path), str(out_path), params,
                      noise_reducer=_noise_reducer)

        if not out_path.exists():
            logger.error("Output not created!")
            return {"error": "Output not created"}, 500

        logger.info(f"Output: {out_path.stat().st_size} bytes, converting to 16-bit...")
        data, sr = sf.read(str(out_path), dtype='float32')
        sf.write(str(conv_path), data, int(sr), subtype="PCM_16")

        logger.info(f"Final output: {conv_path.stat().st_size} bytes")
        return FileResponse(str(conv_path), media_type="audio/wav", filename="kore_output.wav")

    except Exception as e:
        logger.exception("Unexpected error")
        return {"error": str(e)}, 500


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8765)
