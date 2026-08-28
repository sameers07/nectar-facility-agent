"""Speech-to-text: local Whisper model. No API key required."""

_model = None


def _get_model():
    global _model
    if _model is None:
        import whisper

        _model = whisper.load_model("base")
    return _model


def transcribe_file(path: str) -> str:
    result = _get_model().transcribe(path, fp16=False)
    return result["text"].strip()


def transcribe_audio(audio) -> str:
    """Transcribe a mono float32 numpy array sampled at 16kHz."""
    result = _get_model().transcribe(audio, fp16=False)
    return result["text"].strip()


def record_and_transcribe(duration: float = 5.0, sample_rate: int = 16000) -> str:
    """Record `duration` seconds from the default microphone and transcribe it."""
    import sounddevice as sd

    print(f"Listening for {duration:.0f}s...")
    audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype="float32")
    sd.wait()
    return transcribe_audio(audio.flatten())
