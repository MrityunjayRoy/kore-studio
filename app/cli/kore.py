import argparse
import os
import sys

from app.pipeline.studio_pipeline import PRESETS, process_files


def _try_apply_override(param_value, arg_value):
    return arg_value if arg_value is not None else param_value


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "studio":
        from app.cli.studio import main as studio_main
        sys.argv.pop(1)
        studio_main()
        return

    parser = argparse.ArgumentParser(
        description="KORE: full karaoke mixing pipeline — studio-grade processing"
    )
    parser.add_argument("vocal", help="Path to vocal (voice) audio file")
    parser.add_argument("karaoke", help="Path to karaoke / instrumental audio file")
    parser.add_argument("-o", "--output", default="kore_output.wav",
                        help="Output path for final mix (default: kore_output.wav)")

    parser.add_argument("--preset", default="Studio Clean",
                        choices=list(PRESETS.keys()),
                        help="Processing preset (default: Studio Clean)")

    parser.add_argument("--gain", type=float, default=None,
                        help="Output gain multiplier (overrides preset)")

    hp_group = parser.add_argument_group("High-pass filter")
    hp_group.add_argument("--highpass-cutoff", type=float, default=None,
                          help="High-pass cutoff frequency in Hz (overrides preset)")

    comp_group = parser.add_argument_group("Compressor")
    comp_group.add_argument("--compressor-threshold", type=float, default=None,
                            help="Compressor threshold in dB (overrides preset)")
    comp_group.add_argument("--compressor-ratio", type=float, default=None,
                            help="Compressor ratio (overrides preset)")
    comp_group.add_argument("--compressor-attack", type=float, default=None,
                            help="Compressor attack in ms (overrides preset)")
    comp_group.add_argument("--compressor-release", type=float, default=None,
                            help="Compressor release in ms (overrides preset)")

    rev_group = parser.add_argument_group("Reverb")
    rev_group.add_argument("--reverb-room-size", type=float, default=None,
                           help="Reverb room size 0-1 (overrides preset)")
    rev_group.add_argument("--reverb-damping", type=float, default=None,
                           help="Reverb damping 0-1 (overrides preset)")
    rev_group.add_argument("--reverb-wet", type=float, default=None,
                           help="Reverb wet level 0-1 (overrides preset)")
    rev_group.add_argument("--reverb-dry", type=float, default=None,
                           help="Reverb dry level 0-1 (overrides preset)")
    rev_group.add_argument("--reverb-width", type=float, default=None,
                           help="Reverb stereo width 0-1 (overrides preset)")

    mix_group = parser.add_argument_group("Mixer")
    mix_group.add_argument("--vocal-balance", type=float, default=None,
                           help="Vocal balance offset in dB (positive = louder vocal)")
    mix_group.add_argument("--vocal-target", type=float, default=None,
                           help="Target peak for vocals in dBFS (overrides preset)")
    mix_group.add_argument("--karaoke-target", type=float, default=None,
                           help="Target peak for karaoke in dBFS (overrides preset)")
    mix_group.add_argument("--loudness-target", type=float, default=None,
                           help="Target integrated loudness in LUFS (overrides preset)")
    mix_group.add_argument("--true-peak", type=float, default=None,
                           help="True peak ceiling in dB (overrides preset)")

    pitch_group = parser.add_argument_group("Pitch correction")
    pitch_group.add_argument("--pitch-correct", action=argparse.BooleanOptionalAction, default=None,
                             help="Enable/disable pitch correction (overrides preset)")
    pitch_group.add_argument("--pitch-key", default=None,
                             help="Musical key for pitch correction (overrides preset)")
    pitch_group.add_argument("--pitch-scale", default=None,
                             choices=["chromatic", "major", "minor",
                                      "pentatonic_major", "pentatonic_minor"],
                             help="Scale for pitch quantization (overrides preset)")
    pitch_group.add_argument("--pitch-strength", type=float, default=None,
                             help="Pitch correction strength 0.0-1.0 (overrides preset)")

    studio_group = parser.add_argument_group("Studio effects")
    studio_group.add_argument("--noise-reduction", action=argparse.BooleanOptionalAction, default=None,
                              help="Enable/disable noise reduction (overrides preset)")
    studio_group.add_argument("--gate-enabled", action=argparse.BooleanOptionalAction, default=None,
                              help="Enable/disable noise gate (overrides preset)")
    studio_group.add_argument("--gate-threshold-db", type=float, default=None,
                              help="Noise gate threshold in dB (overrides preset)")
    studio_group.add_argument("--saturation-drive", type=float, default=None,
                              help="Saturation drive in dB (overrides preset)")
    studio_group.add_argument("--deesser-threshold", type=float, default=None,
                              help="De-esser threshold in dB, 0=off (overrides preset)")
    studio_group.add_argument("--presence-boost", type=float, default=None,
                              help="Presence boost in dB (overrides preset)")
    studio_group.add_argument("--presence-freq", type=float, default=None,
                              help="Presence frequency in Hz (overrides preset)")
    studio_group.add_argument("--air-boost", type=float, default=None,
                              help="Air boost in dB (overrides preset)")
    studio_group.add_argument("--air-freq", type=float, default=None,
                              help="Air frequency in Hz (overrides preset)")
    studio_group.add_argument("--low-cut-db", type=float, default=None,
                              help="Low shelf cut in dB (overrides preset)")
    studio_group.add_argument("--low-cut-freq", type=float, default=None,
                              help="Low shelf cutoff frequency in Hz (overrides preset)")
    studio_group.add_argument("--boxiness-db", type=float, default=None,
                              help="Boxiness notch cut in dB (overrides preset)")
    studio_group.add_argument("--boxiness-freq", type=float, default=None,
                              help="Boxiness notch frequency in Hz (overrides preset)")
    studio_group.add_argument("--harshness-db", type=float, default=None,
                              help="Harshness notch cut in dB (overrides preset)")
    studio_group.add_argument("--harshness-freq", type=float, default=None,
                              help="Harshness notch frequency in Hz (overrides preset)")
    studio_group.add_argument("--leveler-threshold", type=float, default=None,
                              help="Leveling compressor threshold in dB (overrides preset)")
    studio_group.add_argument("--leveler-ratio", type=float, default=None,
                              help="Leveling compressor ratio (overrides preset)")
    studio_group.add_argument("--leveler-attack", type=float, default=None,
                              help="Leveling compressor attack in ms (overrides preset)")
    studio_group.add_argument("--leveler-release", type=float, default=None,
                              help="Leveling compressor release in ms (overrides preset)")
    studio_group.add_argument("--doubler-enabled", action=argparse.BooleanOptionalAction, default=None,
                              help="Enable/disable vocal doubler (overrides preset)")
    studio_group.add_argument("--doubler-delay-ms", type=float, default=None,
                              help="Vocal doubler delay in ms (overrides preset)")
    studio_group.add_argument("--doubler-feedback", type=float, default=None,
                              help="Vocal doubler feedback 0-1 (overrides preset)")
    studio_group.add_argument("--duck-depth-db", type=float, default=None,
                              help="Multiband ducking depth in dB (overrides preset)")
    studio_group.add_argument("--input-gain", type=float, default=None,
                              help="Input gain multiplier (overrides preset)")

    args = parser.parse_args()

    params = dict(PRESETS.get(args.preset, PRESETS["Studio Clean"]))

    param_overrides = {
        "highpass_cutoff": args.highpass_cutoff,
        "compressor_threshold": args.compressor_threshold,
        "compressor_ratio": args.compressor_ratio,
        "compressor_attack": args.compressor_attack,
        "compressor_release": args.compressor_release,
        "reverb_room_size": args.reverb_room_size,
        "reverb_damping": args.reverb_damping,
        "reverb_wet": args.reverb_wet,
        "reverb_dry": args.reverb_dry,
        "reverb_width": args.reverb_width,
        "gain": args.gain,
        "vocal_target": args.vocal_target,
        "karaoke_target": args.karaoke_target,
        "loudness_target": args.loudness_target,
        "true_peak": args.true_peak,
        "pitch_key": args.pitch_key,
        "pitch_scale": args.pitch_scale,
        "pitch_strength": args.pitch_strength,
        "gate_threshold_db": args.gate_threshold_db,
        "saturation_drive": args.saturation_drive,
        "deesser_threshold": args.deesser_threshold,
        "presence_boost": args.presence_boost,
        "presence_freq": args.presence_freq,
        "air_boost": args.air_boost,
        "air_freq": args.air_freq,
        "low_cut_db": args.low_cut_db,
        "low_cut_freq": args.low_cut_freq,
        "boxiness_db": args.boxiness_db,
        "boxiness_freq": args.boxiness_freq,
        "harshness_db": args.harshness_db,
        "harshness_freq": args.harshness_freq,
        "leveler_threshold": args.leveler_threshold,
        "leveler_ratio": args.leveler_ratio,
        "leveler_attack": args.leveler_attack,
        "leveler_release": args.leveler_release,
        "doubler_delay_ms": args.doubler_delay_ms,
        "doubler_feedback": args.doubler_feedback,
        "duck_depth_db": args.duck_depth_db,
        "input_gain": args.input_gain,
    }

    bool_overrides = {
        "pitch_correct": args.pitch_correct,
        "noise_reduction": args.noise_reduction,
        "gate_enabled": args.gate_enabled,
        "doubler_enabled": args.doubler_enabled,
    }

    for key, value in param_overrides.items():
        if value is not None:
            params[key] = value

    for key, value in bool_overrides.items():
        if value is not None:
            params[key] = value

    if args.vocal_balance is not None:
        params["vocal_target"] = params.get("vocal_target", -8.0) + args.vocal_balance

    process_files(args.vocal, args.karaoke, args.output, params)


if __name__ == "__main__":
    main()
