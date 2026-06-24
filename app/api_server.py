import tempfile
import os
import subprocess
import sys
import atexit
import shutil
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [KoreAPI] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

try:
    from fastapi import FastAPI, UploadFile, File, Form
    from fastapi.responses import FileResponse
    import uvicorn
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "fastapi", "uvicorn", "python-multipart"])
    from fastapi import FastAPI, UploadFile, File, Form
    from fastapi.responses import FileResponse
    import uvicorn

app = FastAPI(title="Kore Processing API")
KORE_DIR = Path(__file__).resolve().parent.parent
WORK_DIR = Path(tempfile.mkdtemp(prefix="kore_api_"))
atexit.register(lambda: shutil.rmtree(WORK_DIR, ignore_errors=True))

PRESETS = {
    "studio": {"pitch_correct": True, "pitch_key": "C", "pitch_scale": "chromatic", "pitch_strength": 0.5,
               "highpass_cutoff": 80, "compressor_threshold": -18, "compressor_ratio": 3.0,
               "compressor_attack": 3, "compressor_release": 60, "reverb_room_size": 0.25,
               "reverb_damping": 0.5, "reverb_wet": 0.10, "reverb_dry": 0.85, "reverb_width": 0.7,
               "vocal_target": -8, "karaoke_target": -12, "loudness_target": -14, "true_peak": -1.0},
    "smule":  {"pitch_correct": True, "pitch_key": "C", "pitch_scale": "major", "pitch_strength": 0.7,
               "highpass_cutoff": 80, "compressor_threshold": -20, "compressor_ratio": 3.5,
               "compressor_attack": 1.5, "compressor_release": 40, "reverb_room_size": 0.28,
               "reverb_damping": 0.4, "reverb_wet": 0.12, "reverb_dry": 0.82, "reverb_width": 0.8,
               "vocal_target": -8, "karaoke_target": -12, "loudness_target": -13, "true_peak": -1.0},
    "live":   {"pitch_correct": True, "pitch_key": "C", "pitch_scale": "major", "pitch_strength": 0.6,
               "highpass_cutoff": 80, "compressor_threshold": -22, "compressor_ratio": 4.0,
               "compressor_attack": 2, "compressor_release": 40, "reverb_room_size": 0.45,
               "reverb_damping": 0.3, "reverb_wet": 0.15, "reverb_dry": 0.78, "reverb_width": 1.0,
               "vocal_target": -8, "karaoke_target": -12, "loudness_target": -13, "true_peak": -1.0},
    "podcast":{"pitch_correct": False, "pitch_strength": 0.0,
               "highpass_cutoff": 80, "compressor_threshold": -16, "compressor_ratio": 4.0,
               "compressor_attack": 1, "compressor_release": 80, "reverb_room_size": 0.08,
               "reverb_damping": 0.8, "reverb_wet": 0.02, "reverb_dry": 0.95, "reverb_width": 0.3,
               "vocal_target": -8, "karaoke_target": -12, "loudness_target": -16, "true_peak": -1.0},
    "raw":    {"pitch_correct": False, "pitch_strength": 0.0,
               "highpass_cutoff": 20, "compressor_threshold": 0, "compressor_ratio": 1.0,
               "compressor_attack": 10, "compressor_release": 100, "reverb_room_size": 0.0,
               "reverb_damping": 1.0, "reverb_wet": 0.0, "reverb_dry": 1.0, "reverb_width": 0.0,
               "vocal_target": -8, "karaoke_target": -12, "loudness_target": -14, "true_peak": -1.0},
}


@app.post("/process")
async def process(
    vocal: UploadFile = File(...),
    instrumental: UploadFile = File(...),
    preset: str = Form("smule"),
    pitch_correct: bool = Form(True),
    pitch_key: str = Form("C"),
    pitch_scale: str = Form("major"),
    pitch_strength: float = Form(0.7),
    highpass_cutoff: float = Form(80.0),
    compressor_threshold: float = Form(-20.0),
    compressor_ratio: float = Form(3.5),
    compressor_attack: float = Form(1.5),
    compressor_release: float = Form(40.0),
    reverb_room_size: float = Form(0.28),
    reverb_damping: float = Form(0.4),
    reverb_wet: float = Form(0.12),
    reverb_dry: float = Form(0.82),
    reverb_width: float = Form(0.8),
    vocal_target: float = Form(-8.0),
    karaoke_target: float = Form(-12.0),
    loudness_target: float = Form(-13.0),
    true_peak: float = Form(-1.0),
):
    logger.info(f"Request: preset={preset}, vocal={vocal.filename}, inst={instrumental.filename}")
    p = PRESETS.get(preset, PRESETS["smule"])
    params = {
        "pitch_correct": pitch_correct, "pitch_key": pitch_key,
        "pitch_scale": pitch_scale, "pitch_strength": pitch_strength,
        "highpass_cutoff": highpass_cutoff, "compressor_threshold": compressor_threshold,
        "compressor_ratio": compressor_ratio, "compressor_attack": compressor_attack,
        "compressor_release": compressor_release, "reverb_room_size": reverb_room_size,
        "reverb_damping": reverb_damping, "reverb_wet": reverb_wet,
        "reverb_dry": reverb_dry, "reverb_width": reverb_width,
        "vocal_target": vocal_target, "karaoke_target": karaoke_target,
        "loudness_target": loudness_target, "true_peak": true_peak,
    }

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

        # Convert instrumental to WAV if it's not already
        inst_wav = job_dir / "instrumental_conv.wav"
        logger.info("Converting instrumental with ffmpeg...")
        conv_result = subprocess.run(["ffmpeg", "-y", "-i", str(inst_path), "-vn", "-acodec", "pcm_s16le", "-ar", "48000", "-ac", "2", str(inst_wav)], capture_output=True, timeout=60)
        if inst_wav.exists() and inst_wav.stat().st_size > 1000:
            logger.info(f"Converted OK: {inst_wav.stat().st_size} bytes")
            inst_path = inst_wav
        else:
            logger.warning(f"Conversion failed. ffmpeg stderr: {conv_result.stderr[-300:]}")
            return {"error": f"Failed to convert instrumental: {conv_result.stderr[-200:]}"}, 500

        args = [sys.executable, "-m", "app.cli.kore", str(vocal_path), str(inst_path), "-o", str(out_path)]
        # Pitch correction runs separately to avoid torch/numpy conflict
        if params.get("pitch_correct"):
            corrected_path = job_dir / "corrected.wav"
            pc_args = [sys.executable, "-c", """
import sys
sys.path.insert(0, '{}')
from app.pipeline.pitch_correct import auto_pitch_correct
import soundfile as sf
audio, sr = sf.read('{}')
corrected = auto_pitch_correct(audio, sr, key='{}', scale='{}', strength={})
sf.write('{}', corrected, sr)
""".format(KORE_DIR, vocal_path, params.get("pitch_key", "C"), params.get("pitch_scale", "major"), params.get("pitch_strength", 0.7), corrected_path)]
            logger.info("Running pitch correction in isolated process...")
            pc_result = subprocess.run(pc_args, cwd=str(KORE_DIR), capture_output=True, text=True, timeout=60)
            if pc_result.returncode == 0 and corrected_path.exists():
                logger.info("Pitch correction OK, using corrected vocal")
                vocal_path = str(corrected_path)
            else:
                logger.warning(f"Pitch correction failed: {pc_result.stderr[-200:]}, using uncorrected")

        logger.info(f"Running kore CLI: {args[0]} {args[1]} {' '.join(args[2:6])}...")
        for k, v in params.items():
            if v is not None and not k.startswith("pitch"):
                kebab = k.replace("_", "-")
                if isinstance(v, bool):
                    if v:
                        args.append(f"--{kebab}")
                else:
                    args.extend([f"--{kebab}", str(v)])

        result = subprocess.run(args, cwd=str(KORE_DIR), capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            logger.error(f"Kore failed (code {result.returncode}): {result.stderr[-500:]}")
            return {"error": result.stderr or result.stdout, "code": result.returncode}, 500
        logger.info(f"Kore done, output: {out_path.stat().st_size if out_path.exists() else 'MISSING'} bytes")
        if not out_path.exists():
            logger.error("Output not created!")
            return {"error": "Output not created"}, 500

        logger.info("Converting to 16-bit...")
        subprocess.run(["ffmpeg", "-y", "-i", str(out_path), "-acodec", "pcm_s16le", "-ar", "48000", str(conv_path)], capture_output=True, timeout=60)
        final_path = conv_path if conv_path.exists() else out_path
        logger.info(f"Final output: {final_path.stat().st_size} bytes")
        return FileResponse(str(final_path), media_type="audio/wav", filename="kore_output.wav")

    except Exception as e:
        logger.exception("Unexpected error")
        return {"error": str(e)}, 500


@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8765)
