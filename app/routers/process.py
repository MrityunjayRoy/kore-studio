import os
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from app.pipeline.studio_pipeline import PRESETS, process_files

logger = logging.getLogger(__name__)
router = APIRouter()


def _resolve_preset(name: str) -> dict:
    if name in PRESETS:
        return dict(PRESETS[name])
    lower = name.lower()
    for key in PRESETS:
        if key.lower() == lower or lower == key.lower().split()[0]:
            return dict(PRESETS[key])
    logger.warning("Unknown preset '%s', falling back to Studio Clean", name)
    return dict(PRESETS["Studio Clean"])


@router.post("/process")
async def process_audio(
    request: Request,
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
    logger.info(
        "Request: preset=%s, vocal=%s, inst=%s",
        preset, vocal.filename, instrumental.filename,
    )
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

    import tempfile
    work_dir = Path(tempfile.mkdtemp(prefix="kore_process_"))

    try:
        vocal_path = work_dir / "vocal.wav"
        inst_path = work_dir / "instrumental.wav"
        out_path = work_dir / "output.wav"

        with open(vocal_path, "wb") as f:
            f.write(await vocal.read())
        with open(inst_path, "wb") as f:
            f.write(await instrumental.read())

        process_files(
            str(vocal_path), str(inst_path), str(out_path), params,
            noise_reducer=request.app.state.noise_reducer,
        )

        if not out_path.exists():
            raise HTTPException(status_code=500, detail="Output not created")

        return FileResponse(
            str(out_path),
            media_type="audio/wav",
            filename="kore_output.wav",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Processing failed")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        import shutil
        shutil.rmtree(work_dir, ignore_errors=True)
