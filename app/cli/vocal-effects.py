import argparse

import numpy as np
import soundfile as sf
from pedalboard import Compressor, HighpassFilter, Pedalboard, Reverb
from pedalboard.io import AudioFile


def build_chain(args: argparse.Namespace) -> Pedalboard:
    plugins = []

    plugins.append(HighpassFilter(cutoff_frequency_hz=args.highpass_cutoff))

    plugins.append(
        Compressor(
            threshold_db=args.compressor_threshold,
            ratio=args.compressor_ratio,
            attack_ms=args.compressor_attack,
            release_ms=args.compressor_release,
        )
    )

    plugins.append(
        Reverb(
            room_size=args.reverb_room_size,
            damping=args.reverb_damping,
            wet_level=args.reverb_wet,
            dry_level=args.reverb_dry,
            width=args.reverb_width,
        )
    )

    return Pedalboard(plugins)


def process(input_path: str, output_path: str, chain: Pedalboard, gain: float):
    with AudioFile(input_path) as f:
        audio = f.read(f.frames)
        sr = f.samplerate

    audio = chain(audio, sample_rate=sr)
    audio = np.clip(audio * gain, -1.0, 1.0)

    sf.write(output_path, audio.T, sr, subtype="PCM_24")
    print(f"Processed audio saved to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Apply vocal effects chain (high-pass filter, compressor, reverb) to an audio file using pedalboard"
    )
    parser.add_argument("input", help="Path to input audio file")
    parser.add_argument("-o", "--output", default="vocal-processed.wav", help="Output path (default: vocal-processed.wav)")

    parser.add_argument("--gain", type=float, default=1.0, help="Output gain multiplier (default: 1.0)")

    hp_group = parser.add_argument_group("High-pass filter")
    hp_group.add_argument("--highpass-cutoff", type=float, default=80.0, help="High-pass cutoff frequency in Hz (default: 80)")

    comp_group = parser.add_argument_group("Compressor")
    comp_group.add_argument("--compressor-threshold", type=float, default=-20.0, help="Compressor threshold in dB (default: -20)")
    comp_group.add_argument("--compressor-ratio", type=float, default=3.0, help="Compressor ratio (default: 3)")
    comp_group.add_argument("--compressor-attack", type=float, default=2.0, help="Compressor attack in ms (default: 2)")
    comp_group.add_argument("--compressor-release", type=float, default=50.0, help="Compressor release in ms (default: 50)")

    rev_group = parser.add_argument_group("Reverb")
    rev_group.add_argument("--reverb-room-size", type=float, default=0.3, help="Reverb room size 0-1 (default: 0.3)")
    rev_group.add_argument("--reverb-damping", type=float, default=0.5, help="Reverb damping 0-1 (default: 0.5)")
    rev_group.add_argument("--reverb-wet", type=float, default=0.2, help="Reverb wet level 0-1 (default: 0.2)")
    rev_group.add_argument("--reverb-dry", type=float, default=0.6, help="Reverb dry level 0-1 (default: 0.6)")
    rev_group.add_argument("--reverb-width", type=float, default=0.8, help="Reverb stereo width 0-1 (default: 0.8)")

    args = parser.parse_args()

    chain = build_chain(args)
    process(args.input, args.output, chain, args.gain)
