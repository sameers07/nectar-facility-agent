"""Speech-to-text: local Whisper model. No API key required."""
import os

_model = None
SILENCE_THRESHOLD = 0.01


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


def _resolve_input_device(sd):
    """AUDIO_INPUT_DEVICE env var (name substring or index) overrides the
    system default, which on some machines points at the wrong device
    (e.g. a connected accessory instead of the built-in mic)."""
    override = os.environ.get("AUDIO_INPUT_DEVICE")
    if not override:
        return None
    if override.isdigit():
        return int(override)
    for index, dev in enumerate(sd.query_devices()):
        if override.lower() in dev["name"].lower() and dev["max_input_channels"] > 0:
            return index
    raise ValueError(f"No input device matching AUDIO_INPUT_DEVICE={override!r}")


def record_and_transcribe(duration: float = 5.0, sample_rate: int = 16000) -> str:
    """Record `duration` seconds from the microphone and transcribe it."""
    import numpy as np
    import sounddevice as sd

    device = _resolve_input_device(sd)
    device_name = sd.query_devices(device)["name"] if device is not None else sd.query_devices(sd.default.device[0])["name"]
    print(f"Listening for {duration:.0f}s (device: {device_name})...")
    audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype="float32", device=device)
    sd.wait()
    audio = audio.flatten()

    if np.abs(audio).max() < SILENCE_THRESHOLD:
        print(
            f"No audio detected from '{device_name}'. If this isn't your mic, set "
            "AUDIO_INPUT_DEVICE (e.g. AUDIO_INPUT_DEVICE=MacBook) or check macOS "
            "microphone permissions for this terminal."
        )
        return ""

    return transcribe_audio(audio)
