import os
import sys
import time
import uuid
import threading
import select
import tty
import termios
from datetime import datetime
from typing import Optional

import numpy as np
import soundfile as sf
import inquirer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
from rich.progress import BarColumn, Progress, TextColumn

from app.pipeline.device_io import (
    AudioStream, list_input_devices, list_output_devices,
    get_default_input_device, get_default_output_device,
)
from app.pipeline.latency import (
    LatencyCache, apply_latency_compensation, detect_acoustic_bleed,
    is_headphone_device,
)
from app.pipeline.studio_pipeline import (
    PRESETS, DEFAULT_PARAMS,
    _build_effects_chain, _deess, _apply_vocal_doubler, apply_effects,
)

console = Console()

WAVEFORM_CHARS = " ▁▂▃▄▅▆▇█"

SESSIONS_DIR = "sessions"
KARAOKES_DIR = "karaokes"
AUDIO_EXTS = {".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aac", ".aiff", ".wma"}


def new_session_id() -> str:
    """Generate a sortable, unique session folder id."""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    short = uuid.uuid4().hex[:8]
    return f"{ts}-{short}"


def list_sessions() -> list:
    """Return [(session_id, session_dir), ...] for sessions that have vocal + instrumental, newest first."""
    if not os.path.isdir(SESSIONS_DIR):
        return []
    sessions = []
    for name in sorted(os.listdir(SESSIONS_DIR), reverse=True):
        d = os.path.join(SESSIONS_DIR, name)
        if (os.path.isdir(d)
                and os.path.isfile(os.path.join(d, "vocal.wav"))
                and os.path.isfile(os.path.join(d, "instrumental.wav"))):
            sessions.append((name, d))
    return sessions


def list_karaoke_files() -> list:
    """Return sorted paths of audio files in KARAOKES_DIR."""
    if not os.path.isdir(KARAOKES_DIR):
        return []
    files = []
    for name in sorted(os.listdir(KARAOKES_DIR)):
        if os.path.splitext(name)[1].lower() in AUDIO_EXTS:
            files.append(os.path.join(KARAOKES_DIR, name))
    return files


def select_karaoke() -> str:
    """Pick a karaoke/instrumental from KARAOKES_DIR via list, with manual fallback."""
    files = list_karaoke_files()

    if files:
        console.print(f"[dim]Found {len(files)} track(s) in {KARAOKES_DIR}/[/dim]")
        choices = [(os.path.basename(p), p) for p in files]
        choices.append(("Enter path manually...", None))
        q = [inquirer.List("pick", message="Select karaoke/instrumental",
                           choices=choices, default=choices[0])]
        a = inquirer.prompt(q)
        if a and a["pick"] is not None:
            return a["pick"]
        if not a:
            sys.exit(0)

    console.print(
        f"[yellow]No tracks in {KARAOKES_DIR}/ — drop audio files there,[/yellow]\n"
        f"[yellow]or enter a path manually below.[/yellow]"
    )
    q = [inquirer.Text("path", message="Path to karaoke/instrumental audio file",
                       validate=lambda _, x: os.path.isfile(x) or "File not found")]
    a = inquirer.prompt(q)
    if not a:
        sys.exit(0)
    return a["path"]


def vu_meter(audio_chunk: np.ndarray, width: int = 20) -> Text:
    if len(audio_chunk) == 0:
        return Text("░" * width + " -inf dB", style="dim")
    rms = np.sqrt(np.mean(audio_chunk.astype(np.float64) ** 2))
    if rms <= 0:
        db = -60.0
    else:
        db = 20 * np.log10(rms)
    db = max(-60.0, min(0.0, db))
    fill = int((db + 60) / 60 * width)
    fill = max(0, min(width, fill))

    if db > -3:
        color = "red"
    elif db > -12:
        color = "yellow"
    else:
        color = "green"

    bar = Text()
    bar.append("█" * fill, style=color)
    bar.append("░" * (width - fill), style="dim")
    bar.append(f" {db:>5.1f}dB", style=color)
    return bar


def ascii_waveform(audio_chunk: np.ndarray, width: int = 40) -> str:
    if len(audio_chunk) == 0:
        return WAVEFORM_CHARS[0] * width
    downsampled = audio_chunk[:: max(1, len(audio_chunk) // width)]
    downsampled = downsampled[:width]
    chars = []
    for val in downsampled:
        idx = int((val + 1.0) / 2.0 * (len(WAVEFORM_CHARS) - 1))
        idx = max(0, min(len(WAVEFORM_CHARS) - 1, idx))
        chars.append(WAVEFORM_CHARS[idx])
    while len(chars) < width:
        chars.append(WAVEFORM_CHARS[0])
    return "".join(chars)


def select_devices():
    console.clear()
    console.print(Panel("[bold cyan]KORE Studio[/bold cyan]\nSelect audio devices", style="cyan"))

    karaoke_path = select_karaoke()

    input_devs = list_input_devices()
    output_devs = list_output_devices()

    if not input_devs:
        console.print("[red]No input devices found.[/red]")
        sys.exit(1)
    if not output_devs:
        console.print("[red]No output devices found.[/red]")
        sys.exit(1)

    default_in = get_default_input_device()
    default_out = get_default_output_device()

    in_choices = [f"{d['name']} ({d['channels']}ch)" for d in input_devs]
    out_choices = [f"{d['name']} ({d['channels']}ch)" for d in output_devs]

    default_in_idx = next(
        (i for i, d in enumerate(input_devs) if d["id"] == default_in["id"]), 0
    )
    default_out_idx = next(
        (i for i, d in enumerate(output_devs) if d["id"] == default_out["id"]), 0
    )

    questions = [
        inquirer.List(
            "input_dev",
            message="Input device (microphone)",
            choices=in_choices,
            default=in_choices[default_in_idx],
        ),
        inquirer.List(
            "output_dev",
            message="Output device (speaker/earphones)",
            choices=out_choices,
            default=out_choices[default_out_idx],
        ),
        inquirer.List(
            "monitor_level",
            message="Live vocal monitoring level",
            choices=[
                ("Off (no vocal in headphones)", "0.0"),
                ("Low (subtle vocal bleed)", "0.3"),
                ("Medium (balanced)", "0.5"),
                ("High (full vocal)", "0.8"),
            ],
            default="0.0",
        ),
        inquirer.List(
            "input_gain",
            message="Input gain (mic sensitivity)",
            choices=[
                ("Low (quiet source)", "0.5"),
                ("Normal", "1.0"),
                ("High (quiet mic)", "1.5"),
                ("Very High (distant mic)", "2.0"),
            ],
            default="1.0",
        ),
    ]

    answers = inquirer.prompt(questions)
    if not answers:
        sys.exit(0)

    in_idx = in_choices.index(answers["input_dev"])
    out_idx = out_choices.index(answers["output_dev"])

    return input_devs[in_idx], output_devs[out_idx], karaoke_path, float(answers["monitor_level"]), float(answers["input_gain"])


def pre_roll_screen(input_dev, output_dev, karaoke_path, monitor_level, input_gain, latency_ms=None):
    console.clear()
    table = Table(title="Recording Setup", show_header=False, border_style="cyan")
    table.add_row("Input", input_dev["name"])
    table.add_row("Output", output_dev["name"])
    table.add_row("Karaoke", karaoke_path)
    table.add_row("Sample Rate", "48000 Hz")
    table.add_row("Format", "WAV 24-bit")
    mon_label = "Off" if monitor_level == 0 else f"{monitor_level * 100:.0f}%"
    table.add_row("Monitoring", mon_label)
    table.add_row("Input Gain", f"{input_gain}x")
    if latency_ms is not None:
        table.add_row("Latency", f"{latency_ms:.1f} ms (auto-compensated)")
    console.print(Panel(table, title="KORE Studio", border_style="cyan"))

    if not is_headphone_device(output_dev["name"]):
        console.print("\n[bold red]⚠ SPEAKER DETECTED[/bold red]")
        console.print("[red]Speaker playback will bleed into your microphone.[/red]")
        console.print("[yellow]For best results, use headphones during recording.[/yellow]")

    console.print("\n[dim]A 2-second count-in will play before the music starts — get ready.[/dim]")
    console.print("[dim]Press [bold]ENTER[/bold] to start recording, [bold]Ctrl+C[/bold] to cancel[/dim]")
    try:
        input()
    except KeyboardInterrupt:
        sys.exit(0)

    console.print("\n[bold yellow]⏳ Calibrating microphone... (0.5s)[/bold yellow]")


def recording_screen(stream: AudioStream, karaoke_audio: np.ndarray, sr: int, monitor_level: float = 0.0) -> np.ndarray:
    console.clear()
    start_time = time.time()
    last_vu = Text("")
    last_wave = ""
    recording_done = threading.Event()
    recorded_audio = [None]

    def do_record():
        max_dur = len(karaoke_audio) / sr
        recorded_audio[0] = stream.record_with_playback(
            karaoke_audio, max_dur, on_chunk=on_chunk, monitor_level=monitor_level
        )
        recording_done.set()

    def on_chunk(chunk):
        nonlocal last_vu, last_wave
        last_vu = vu_meter(chunk)
        last_wave = ascii_waveform(chunk, 40)

    thread = threading.Thread(target=do_record, daemon=True)
    thread.start()

    def generate_display():
        elapsed = time.time() - start_time
        mins, secs = divmod(int(elapsed), 60)
        progress = min(1.0, elapsed / (len(karaoke_audio) / sr))

        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="meters", size=6),
            Layout(name="waveform", size=5),
            Layout(name="controls", size=3),
        )

        rec_text = Text()
        rec_text.append("● REC ", style="bold red blink")
        rec_text.append(f"{mins:02d}:{secs:02d}", style="bold white")
        layout["header"].update(Panel(rec_text, border_style="red"))

        meters = Table.grid()
        meters.add_row("INPUT ", last_vu)
        prog_bar = Text()
        filled = int(progress * 20)
        prog_bar.append("█" * filled, style="cyan")
        prog_bar.append("░" * (20 - filled), style="dim")
        prog_bar.append(f" {progress * 100:5.1f}%", style="cyan")
        meters.add_row("KARAOKE ", prog_bar)
        layout["meters"].update(Panel(meters, border_style="cyan"))

        wave_text = Text(last_wave, style="green")
        layout["waveform"].update(Panel(wave_text, title="Live Waveform", border_style="green"))

        controls = Text()
        controls.append("[SPACE] ", style="bold")
        controls.append("Stop  ", style="dim")
        controls.append("[P] ", style="bold")
        controls.append("Pause  ", style="dim")
        controls.append("[M] ", style="bold")
        controls.append("Monitor", style="dim")
        if stream.is_paused:
            controls.append("  PAUSED", style="bold yellow")
        mon_label = "OFF" if stream.monitor_level == 0 else f"{stream.monitor_level * 100:.0f}%"
        mon_style = "dim" if stream.monitor_level == 0 else "green"
        controls.append("  MON: ", style="dim")
        controls.append(mon_label, style=mon_style)
        layout["controls"].update(Panel(controls, border_style="dim"))

        return layout

    try:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        use_tty = True
    except (termios.error, ValueError, OSError):
        use_tty = False

    MONITOR_LEVELS = [0.0, 0.3, 0.5, 0.8, 1.0]
    mon_idx = [MONITOR_LEVELS.index(monitor_level) if monitor_level in MONITOR_LEVELS else 0]

    def key_listener():
        while not recording_done.is_set() and use_tty:
            if select.select([sys.stdin], [], [], 0.1)[0]:
                ch = sys.stdin.read(1)
                if ch == 'm' or ch == 'M':
                    mon_idx[0] = (mon_idx[0] + 1) % len(MONITOR_LEVELS)
                    stream.set_monitor_level(MONITOR_LEVELS[mon_idx[0]])
                elif ch == 'p' or ch == 'P':
                    stream.toggle_pause()
                elif ch == ' ':
                    stream.stop_recording()

    key_thread = threading.Thread(target=key_listener, daemon=True)
    if use_tty:
        key_thread.start()

    try:
        with Live(generate_display(), refresh_per_second=10, screen=True) as live:
            while not recording_done.is_set():
                time.sleep(0.1)
                live.update(generate_display())
    except KeyboardInterrupt:
        stream.stop_recording()
        recording_done.wait(timeout=2)
    finally:
        if use_tty:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    return recorded_audio[0] if recorded_audio[0] is not None else np.array([], dtype=np.float32)


def effects_menu(vocal: np.ndarray, sr: int, karaoke_path: Optional[str] = None,
                 session_dir: Optional[str] = None) -> Optional[str]:
    params = dict(DEFAULT_PARAMS)

    while True:
        console.clear()
        console.print(Panel("[bold cyan]Studio Effects[/bold cyan]", border_style="cyan"))

        status = Table(show_header=False, border_style="dim")
        nr_status = "[green]ON[/green]" if params["noise_reduction"] else "[red]OFF[/red]"
        status.add_row("Noise Reduction", nr_status)

        pc_status = "[green]ON[/green]" if params["pitch_correct"] else "[red]OFF[/red]"
        pc_detail = f"Key={params['pitch_key']} Scale={params['pitch_scale']} Str={params['pitch_strength']}" if params["pitch_correct"] else ""
        status.add_row("Pitch Correction", f"{pc_status} {pc_detail}")

        status.add_row("High-pass", f"Cutoff={params['highpass_cutoff']}Hz")
        status.add_row("Presence", f"Boost={params.get('presence_boost', 0)}dB @{params.get('presence_freq', 5000)}Hz")
        status.add_row("De-esser", f"Thresh={params.get('deesser_threshold', 0)}dB")
        status.add_row("Compressor", f"Thresh={params['compressor_threshold']}dB Ratio={params['compressor_ratio']}")
        status.add_row("Reverb", f"Room={params['reverb_room_size']} Wet={params['reverb_wet']} Dry={params['reverb_dry']}")
        status.add_row("Mix", f"Vocal={params.get('vocal_target', -8)}dB Karaoke={params.get('karaoke_target', -1)}dB")
        status.add_row("Gain", str(params["gain"]))
        console.print(status)

        choices = [
            "Apply & Export",
            "Preview (apply without export)",
            "Toggle Noise Reduction",
            "Configure Pitch Correction",
            "Configure High-pass Filter",
            "Configure Presence / De-esser",
            "Configure Compressor",
            "Configure Reverb",
            "Configure Mix Levels",
            "Configure Gain",
            "Load Preset",
            "Re-record",
            "Cancel",
        ]

        questions = [inquirer.List("action", message="Action", choices=choices)]
        answer = inquirer.prompt(questions)
        if not answer:
            break

        action = answer["action"]

        if action == "Apply & Export":
            default_path = os.path.join(session_dir, "mixed.wav") if session_dir else "kore_studio_output.wav"
            q = [inquirer.Text("path", message="Output path", default=default_path)]
            a = inquirer.prompt(q)
            if a:
                apply_effects(vocal, sr, params, karaoke_path, a["path"])
                return a["path"]

        elif action == "Preview (apply without export)":
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp = f.name
            apply_effects(vocal, sr, params, karaoke_path, tmp)
            console.print("[dim]Playing preview...[/dim]")
            preview, _ = sf.read(tmp, dtype='float32')
            from app.pipeline.device_io import get_default_output_device
            out = get_default_output_device()
            stream = AudioStream(0, out["id"], sr)
            stream.start()
            try:
                stream.play(preview)
            finally:
                stream.close()
            os.unlink(tmp)

        elif action == "Toggle Noise Reduction":
            params["noise_reduction"] = not params["noise_reduction"]

        elif action == "Configure Pitch Correction":
            q = [
                inquirer.Confirm("enabled", message="Enable pitch correction", default=params["pitch_correct"]),
                inquirer.List("key", message="Key", choices=["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"], default=params["pitch_key"]),
                inquirer.List("scale", message="Scale", choices=list(__import__("app.pipeline.pitch_correct", fromlist=["SCALES"]).SCALES.keys()), default=params["pitch_scale"]),
                inquirer.Text("strength", message="Strength (0.0-1.0)", default=str(params["pitch_strength"])),
            ]
            a = inquirer.prompt(q)
            if a:
                params["pitch_correct"] = a["enabled"]
                params["pitch_key"] = a["key"]
                params["pitch_scale"] = a["scale"]
                try:
                    params["pitch_strength"] = float(a["strength"])
                except ValueError:
                    pass

        elif action == "Configure High-pass Filter":
            q = [inquirer.Text("cutoff", message="Cutoff frequency (Hz)", default=str(params["highpass_cutoff"]))]
            a = inquirer.prompt(q)
            if a:
                try:
                    params["highpass_cutoff"] = float(a["cutoff"])
                except ValueError:
                    pass

        elif action == "Configure Presence / De-esser":
            q = [
                inquirer.Text("presence_boost", message="Presence boost (dB, 0=off)", default=str(params.get("presence_boost", 0))),
                inquirer.Text("presence_freq", message="Presence frequency (Hz)", default=str(params.get("presence_freq", 5000))),
                inquirer.Text("deesser_threshold", message="De-esser threshold (dB, 0=off)", default=str(params.get("deesser_threshold", 0))),
            ]
            a = inquirer.prompt(q)
            if a:
                try:
                    params["presence_boost"] = float(a["presence_boost"])
                    params["presence_freq"] = float(a["presence_freq"])
                    params["deesser_threshold"] = float(a["deesser_threshold"])
                except ValueError:
                    pass

        elif action == "Configure Mix Levels":
            q = [
                inquirer.Text("vocal_target", message="Vocal target peak (dBFS)", default=str(params.get("vocal_target", -8))),
                inquirer.Text("karaoke_target", message="Karaoke target peak (dBFS)", default=str(params.get("karaoke_target", -14))),
                inquirer.Text("loudness_target", message="Master loudness (LUFS)", default=str(params.get("loudness_target", -14))),
                inquirer.Text("true_peak", message="True peak ceiling (dB)", default=str(params.get("true_peak", -1))),
            ]
            a = inquirer.prompt(q)
            if a:
                try:
                    params["vocal_target"] = float(a["vocal_target"])
                    params["karaoke_target"] = float(a["karaoke_target"])
                    params["loudness_target"] = float(a["loudness_target"])
                    params["true_peak"] = float(a["true_peak"])
                except ValueError:
                    pass

        elif action == "Configure Compressor":
            q = [
                inquirer.Text("threshold", message="Threshold (dB)", default=str(params["compressor_threshold"])),
                inquirer.Text("ratio", message="Ratio", default=str(params["compressor_ratio"])),
                inquirer.Text("attack", message="Attack (ms)", default=str(params["compressor_attack"])),
                inquirer.Text("release", message="Release (ms)", default=str(params["compressor_release"])),
            ]
            a = inquirer.prompt(q)
            if a:
                try:
                    params["compressor_threshold"] = float(a["threshold"])
                    params["compressor_ratio"] = float(a["ratio"])
                    params["compressor_attack"] = float(a["attack"])
                    params["compressor_release"] = float(a["release"])
                except ValueError:
                    pass

        elif action == "Configure Reverb":
            q = [
                inquirer.Text("room_size", message="Room size (0-1)", default=str(params["reverb_room_size"])),
                inquirer.Text("damping", message="Damping (0-1)", default=str(params["reverb_damping"])),
                inquirer.Text("wet", message="Wet level (0-1)", default=str(params["reverb_wet"])),
                inquirer.Text("dry", message="Dry level (0-1)", default=str(params["reverb_dry"])),
                inquirer.Text("width", message="Width (0-1)", default=str(params["reverb_width"])),
            ]
            a = inquirer.prompt(q)
            if a:
                try:
                    params["reverb_room_size"] = float(a["room_size"])
                    params["reverb_damping"] = float(a["damping"])
                    params["reverb_wet"] = float(a["wet"])
                    params["reverb_dry"] = float(a["dry"])
                    params["reverb_width"] = float(a["width"])
                except ValueError:
                    pass

        elif action == "Configure Gain":
            q = [inquirer.Text("gain", message="Gain multiplier", default=str(params["gain"]))]
            a = inquirer.prompt(q)
            if a:
                try:
                    params["gain"] = float(a["gain"])
                except ValueError:
                    pass

        elif action == "Load Preset":
            q = [inquirer.List("preset", message="Preset", choices=list(PRESETS.keys()))]
            a = inquirer.prompt(q)
            if a:
                params = dict(PRESETS[a["preset"]])

        elif action == "Re-record":
            return None

        elif action == "Cancel":
            return None

    return None


def post_record_menu(recorded: np.ndarray, sr: int, karaoke_path: Optional[str] = None,
                     output_dev_id: int = 0) -> str:
    while True:
        console.clear()
        console.print(Panel("[bold cyan]Recording Complete[/bold cyan]", border_style="cyan"))

        duration = len(recorded) / sr
        peak_db = 20 * np.log10(max(np.max(np.abs(recorded)), 1e-10))
        rms_db = 20 * np.log10(max(np.sqrt(np.mean(recorded.astype(np.float64) ** 2)), 1e-10))

        info = Table(show_header=False, border_style="dim")
        info.add_row("Duration", f"{int(duration // 60):02d}:{int(duration % 60):02d}")
        info.add_row("Peak", f"{peak_db:.1f} dBFS")
        info.add_row("RMS", f"{rms_db:.1f} dBFS")
        console.print(info)

        choices = [
            "Proceed to Effects",
            "Preview Raw Recording",
            "Preview with Karaoke Mix",
            "Re-record",
            "Cancel",
        ]
        q = [inquirer.List("action", message="Action", choices=choices)]
        a = inquirer.prompt(q)
        if not a:
            return "cancel"

        action = a["action"]

        if action == "Proceed to Effects":
            return "effects"

        elif action == "Preview Raw Recording":
            console.print("[dim]Playing raw vocal...[/dim]")
            stream = AudioStream(0, output_dev_id, sr)
            stream.start()
            try:
                stream._recording.set()
                stream.play(recorded)
                stream._recording.clear()
            finally:
                stream.close()

        elif action == "Preview with Karaoke Mix":
            if not karaoke_path:
                console.print("[yellow]No karaoke track specified.[/yellow]")
                time.sleep(1)
                continue
            console.print("[dim]Mixing and playing preview...[/dim]")
            import librosa
            from app.pipeline.mixer import peak_normalize
            karaoke, k_sr = sf.read(karaoke_path, dtype='float32')
            if k_sr != sr:
                karaoke = librosa.resample(karaoke.T, orig_sr=k_sr, target_sr=sr).T
            if karaoke.ndim == 1:
                karaoke = np.column_stack([karaoke, karaoke])

            vocal_stereo = recorded
            if vocal_stereo.ndim == 1:
                vocal_stereo = np.column_stack([vocal_stereo, vocal_stereo])

            vocal_stereo = peak_normalize(vocal_stereo, -10.0)
            karaoke = peak_normalize(karaoke, -11.0)

            min_len = min(len(vocal_stereo), len(karaoke))
            mixed = vocal_stereo[:min_len] + karaoke[:min_len]
            mixed = np.clip(mixed, -1.0, 1.0)

            stream = AudioStream(0, output_dev_id, sr)
            stream.start()
            try:
                stream._recording.set()
                stream.play(mixed)
                stream._recording.clear()
            finally:
                stream.close()

        elif action == "Re-record":
            return "rerecord"

        elif action == "Cancel":
            return "cancel"


def reprocess_session(session_dir: str, preset_name: str = "Studio Clean") -> str:
    """Re-run the full mixing pipeline on an existing session's vocal + instrumental."""
    vocal, sr = sf.read(os.path.join(session_dir, "vocal.wav"), dtype='float32')
    inst_path = os.path.join(session_dir, "instrumental.wav")
    params = dict(PRESETS.get(preset_name, DEFAULT_PARAMS))
    output = os.path.join(session_dir, "mixed.wav")
    apply_effects(vocal, sr, params, karaoke_path=inst_path, output_path=output)
    return output


def reprocess_menu(preset_name: str = "Studio Clean"):
    """Interactive: pick a session (or all), pick a preset, re-process."""
    sessions = list_sessions()
    if not sessions:
        console.print(f"[yellow]No sessions found in {SESSIONS_DIR}/[/yellow]")
        return

    console.print(Panel("[bold cyan]Re-process Existing Sessions[/bold cyan]", border_style="cyan"))
    console.print(f"[dim]Found {len(sessions)} session(s)[/dim]\n")

    choices = [(sid, sdir) for sid, sdir in sessions]
    if len(sessions) > 1:
        choices.append(("All sessions", "__all__"))
    q = [inquirer.List("pick", message="Select session to re-process",
                       choices=choices, default=choices[0])]
    a = inquirer.prompt(q)
    if not a:
        return

    preset_choices = list(PRESETS.keys())
    q = [inquirer.List("preset", message="Select preset", choices=preset_choices,
                       default=preset_name if preset_name in preset_choices else preset_choices[0])]
    a2 = inquirer.prompt(q)
    if not a2:
        return
    preset = a2["preset"]

    selected = a["pick"]
    if selected == "__all__":
        for sid, sdir in sessions:
            console.print(f"\n[bold cyan]Re-processing {sid} ({preset})...[/bold cyan]")
            reprocess_session(sdir, preset)
        console.print(f"\n[bold green]Done![/bold green] Re-processed {len(sessions)} session(s).")
    else:
        sid = os.path.basename(selected)
        console.print(f"\n[bold cyan]Re-processing {sid} ({preset})...[/bold cyan]")
        out = reprocess_session(selected, preset)
        console.print(f"[bold green]Done![/bold green] Output: {out}")


def main(args=None):
    os.makedirs(KARAOKES_DIR, exist_ok=True)
    os.makedirs(SESSIONS_DIR, exist_ok=True)

    # CLI flags: kore studio --reprocess [--all] [--preset "Studio Clean"]
    argv = sys.argv[1:]
    do_reprocess = "--reprocess" in argv
    do_all = "--all" in argv
    preset_name = "Studio Clean"
    if "--preset" in argv:
        idx = argv.index("--preset")
        if idx + 1 < len(argv):
            preset_name = argv[idx + 1]

    if do_reprocess:
        if do_all:
            sessions = list_sessions()
            if not sessions:
                console.print(f"[yellow]No sessions found in {SESSIONS_DIR}/[/yellow]")
                return
            for sid, sdir in sessions:
                console.print(f"\n[bold cyan]Re-processing {sid} ({preset_name})...[/bold cyan]")
                reprocess_session(sdir, preset_name)
            console.print(f"\n[bold green]Done![/bold green] Re-processed {len(sessions)} session(s).")
        else:
            reprocess_menu(preset_name)
        console.print("[dim]Goodbye![/dim]")
        return

    console.print(Panel(
        "[bold cyan]KORE Studio[/bold cyan]\n"
        "Record vocals over karaoke with studio-quality effects",
        border_style="cyan",
    ))

    # If sessions exist, offer to re-process instead of recording
    sessions = list_sessions()
    if sessions:
        q = [inquirer.List("mode", message="What do you want to do?", choices=[
            "Record new take",
            f"Re-process existing session ({len(sessions)} found)",
        ])]
        a = inquirer.prompt(q)
        if a and a["mode"].startswith("Re-process"):
            reprocess_menu()
            console.print("[dim]Goodbye![/dim]")
            return

    input_dev, output_dev, karaoke_path, monitor_level, input_gain = select_devices()

    console.print("\n[yellow]Measuring round-trip latency...[/yellow]")
    cache = LatencyCache()
    latency_samples = cache.get_or_measure(
        input_dev["id"], output_dev["id"],
        input_dev["name"], output_dev["name"],
        sr=48000, chunk_size=2048,
    )
    latency_ms = (latency_samples / 48000) * 1000
    console.print(f"[green]Round-trip latency: {latency_ms:.1f} ms ({latency_samples} samples)[/green]")

    while True:
        pre_roll_screen(input_dev, output_dev, karaoke_path, monitor_level, input_gain, latency_ms)

        karaoke_audio, k_sr = sf.read(karaoke_path, dtype='float32')
        sr = 48000
        if k_sr != sr:
            import librosa
            karaoke_audio = librosa.resample(karaoke_audio.T, orig_sr=k_sr, target_sr=sr).T

        stream = AudioStream(input_dev["id"], output_dev["id"], sr)
        stream.input_gain = input_gain
        stream.start()

        try:
            recorded = recording_screen(stream, karaoke_audio, sr, monitor_level)
        finally:
            stream.close()

        if recorded is None or len(recorded) == 0:
            console.print("[yellow]No audio recorded.[/yellow]")
            break

        if latency_samples != 0:
            console.print(f"[dim]Applying latency compensation: {latency_ms:.1f}ms[/dim]")
            recorded = apply_latency_compensation(recorded, latency_samples)

        bleed = detect_acoustic_bleed(recorded, karaoke_audio, sr, latency_samples)
        if bleed["detected"]:
            console.print(f"[bold red]⚠ {bleed['message']}[/bold red]")
            console.print(f"[dim]Correlation: {bleed['correlation']}[/dim]")

        session_id = new_session_id()
        session_dir = os.path.join(SESSIONS_DIR, session_id)
        os.makedirs(session_dir, exist_ok=True)

        vocal_path = os.path.join(session_dir, "vocal.wav")
        sf.write(vocal_path, recorded, sr, subtype="PCM_24")

        instrumental_path = os.path.join(session_dir, "instrumental.wav")
        sf.write(instrumental_path, karaoke_audio, sr, subtype="PCM_24")

        console.print(
            f"[green]Session exported:[/green] {session_dir}/\n"
            f"[dim]  vocal.wav         (unprocessed)[/dim]\n"
            f"[dim]  instrumental.wav  (matching backing track)[/dim]"
        )

        decision = post_record_menu(recorded, sr, karaoke_path, output_dev["id"])

        if decision == "rerecord":
            continue
        elif decision == "cancel":
            break

        output = effects_menu(recorded, sr, karaoke_path, session_dir)
        if output:
            console.print(f"\n[bold green]Done![/bold green] Output: {output}")

        q = [inquirer.Confirm("again", message="Record another take?", default=False)]
        a = inquirer.prompt(q)
        if not a or not a["again"]:
            break

    console.print("[dim]Goodbye![/dim]")


if __name__ == "__main__":
    main()
