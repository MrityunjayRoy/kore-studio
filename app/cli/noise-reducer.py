import argparse

from df.enhance import enhance, init_df
from df.io import load_audio, save_audio

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reduce noise in an audio file using DeepFilterNet")
    parser.add_argument("input", help="Path to input audio file")
    parser.add_argument("-o", "--output", default="enhanced.wav", help="Output path (default: enhanced.wav)")
    args = parser.parse_args()

    # Load default model
    model, df_state, _ = init_df()
    # Load audio
    audio, _ = load_audio(args.input, sr=df_state.sr())
    # Denoise the audio
    enhanced = enhance(model, df_state, audio)
    # Save for listening
    save_audio(args.output, enhanced, df_state.sr())
    print(f"Enhanced audio saved to {args.output}")
