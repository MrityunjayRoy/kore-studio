Step 1: Ingestion and Normalization (The Buffer Layer)

Libraries: soundfile, librosa
When your FastAPI backend receives the raw vocal and karaoke files from the client, the first step is loading them into memory as NumPy arrays.

    Action: You read the files into floating-point arrays and force them to a unified sample rate (e.g., 44100 Hz).

    The Code Reality: If the vocal is mono and the karaoke is stereo, you must convert the vocal to a 2D array (duplicate the mono signal to left and right channels) so the matrix dimensions match for addition later.

Step 2: The Neural Network Pass (Heavy Compute)

Libraries: demucs, DeepFilterNet
This is the most CPU/GPU intensive part of the pipeline. You process the arrays through pre-trained models.

    Vocal Cleanup: Pass the raw vocal array to DeepFilterNet. It mathematically subtracts background noise and room reverb, returning a clean vocal tensor.

    Instrumental Verification (Optional): If the karaoke track isn't a true instrumental, pass it through Demucs to strip out any residual frequencies that clash with the human voice.

Step 3: Algorithmic DSP & Tuning (CPU Bound)

Libraries: librosa, psola (Pitch-Synchronous Overlap-and-Add)
Without Melodyne, you have to execute pitch correction programmatically.

    Frequency Tracking: Use librosa.pyin to extract the fundamental frequency of the vocal array frame-by-frame.

    Quantization: Write a script that rounds those frequencies to the nearest exact note in the song's musical key.

    Shifting: Use the psola library to time-stretch and pitch-shift the audio array to match the quantized notes without introducing "chipmunk" artifacts.

Step 4: Programmatic Mixing and Dynamics

Libraries: pedalboard (using native C++ objects, not VSTs), scipy
This replaces your Neutron and Trackspacer plugins. pedalboard has built-in, headless digital signal processors.

    Vocal Chain: Instantiate a pedalboard.Compressor, pedalboard.HighpassFilter, and pedalboard.Reverb. Pass your vocal array through them to level the volume and add space.

    Programmatic Trackspacer (Ducking): Instead of a VST, you calculate the Root Mean Square (RMS) energy of the vocal track at every millisecond. You invert that energy curve and apply it as a volume multiplier to the instrumental track. When the vocal gets loud, the instrumental volume automatically drops by a few decibels.

Step 5: The Summing Mixer

At this point, mixing is literal array addition.
mixed_audio_array = (vocal_array * vocal_gain) + (instrumental_array * instrumental_gain)
Step 6: Automated AI Mastering

Libraries: pyloudnorm
This replaces Ozone 11. It is a strict mathematical implementation of ITU-R BS.1770-4 loudness algorithms.

    Action: You feed the mixed_audio_array into pyloudnorm. You set the target to -14 LUFS and -1.0 dB True Peak.

    Result: The library measures the integrated loudness of the entire song, calculates the exact mathematical gain offset required, and scales the array so it perfectly matches streaming standards without clipping.

Step 7: Export and Delivery

Libraries: soundfile
Write the final mastered NumPy array back to a .wav or .mp3 buffer in memory, and stream it back out to the client website via your API response.
