import argparse
import importlib.util
import os
import tempfile

_MODULES_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_module(path):
    name = os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    reducer = _load_module(os.path.join(_MODULES_DIR, "noise-reducer.py"))
    effects = _load_module(os.path.join(_MODULES_DIR, "vocal-effects.py"))
    mixer = _load_module(os.path.join(_MODULES_DIR, "mixer.py"))

    parser = argparse.ArgumentParser(
        description="KORE: full karaoke mixing pipeline — noise reduction, vocal effects, and mix"
    )
    parser.add_argument("vocal", help="Path to vocal (voice) audio file")
    parser.add_argument("karaoke", help="Path to karaoke / instrumental audio file")
    parser.add_argument("-o", "--output", default="kore_output.wav",
                        help="Output path for final mix (default: kore_output.wav)")

    parser.add_argument("--gain", type=float, default=1.0,
                        help="Output gain multiplier (default: 1.0)")

    hp_group = parser.add_argument_group("High-pass filter")
    hp_group.add_argument("--highpass-cutoff", type=float, default=80.0,
                          help="High-pass cutoff frequency in Hz (default: 80)")

    comp_group = parser.add_argument_group("Compressor")
    comp_group.add_argument("--compressor-threshold", type=float, default=-20.0,
                            help="Compressor threshold in dB (default: -20)")
    comp_group.add_argument("--compressor-ratio", type=float, default=3.0,
                            help="Compressor ratio (default: 3)")
    comp_group.add_argument("--compressor-attack", type=float, default=2.0,
                            help="Compressor attack in ms (default: 2)")
    comp_group.add_argument("--compressor-release", type=float, default=50.0,
                            help="Compressor release in ms (default: 50)")

    rev_group = parser.add_argument_group("Reverb")
    rev_group.add_argument("--reverb-room-size", type=float, default=0.3,
                           help="Reverb room size 0-1 (default: 0.3)")
    rev_group.add_argument("--reverb-damping", type=float, default=0.5,
                           help="Reverb damping 0-1 (default: 0.5)")
    rev_group.add_argument("--reverb-wet", type=float, default=0.2,
                           help="Reverb wet level 0-1 (default: 0.2)")
    rev_group.add_argument("--reverb-dry", type=float, default=0.6,
                           help="Reverb dry level 0-1 (default: 0.6)")
    rev_group.add_argument("--reverb-width", type=float, default=0.8,
                           help="Reverb stereo width 0-1 (default: 0.8)")

    mix_group = parser.add_argument_group("Mixer")
    mix_group.add_argument("--vocal-target", type=float, default=-9.0,
                           help="Target peak for vocals in dBFS (default: -9)")
    mix_group.add_argument("--karaoke-target", type=float, default=-13.0,
                           help="Target peak for karaoke in dBFS (default: -13)")
    mix_group.add_argument("--loudness-target", type=float, default=-14.0,
                           help="Target integrated loudness in LUFS (default: -14)")
    mix_group.add_argument("--true-peak", type=float, default=-1.0,
                           help="True peak ceiling in dB (default: -1.0)")

    parser.add_argument("--keep-denoised", help="Save intermediate denoised vocal to this path")
    parser.add_argument("--keep-processed", help="Save intermediate processed vocal to this path")

    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmpdir:
        denoised_path = args.keep_denoised or os.path.join(tmpdir, "denoised.wav")
        model, df_state, _ = reducer.init_df()
        audio, _ = reducer.load_audio(args.vocal, sr=df_state.sr())
        enhanced = reducer.enhance(model, df_state, audio)
        reducer.save_audio(denoised_path, enhanced, df_state.sr())

        processed_path = args.keep_processed or os.path.join(tmpdir, "processed.wav")
        chain = effects.build_chain(args)
        effects.process(denoised_path, processed_path, chain, args.gain)

        mixer.mix(processed_path, args.karaoke, args.output,
                  args.vocal_target, args.karaoke_target,
                  args.loudness_target, args.true_peak)


if __name__ == "__main__":
    main()
