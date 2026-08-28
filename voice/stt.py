"""Speech-to-text: local Whisper model. No API key required."""
import os

from tools.facility_tools import list_known_terms

_model = None
SILENCE_THRESHOLD = 0.01
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "base")


def _get_model():
    global _model
    if _model is None:
        import whisper

        _model = whisper.load_model(WHISPER_MODEL)
    return _model


def _vocabulary_hint() -> str:
    """Biases Whisper toward facility jargon (asset codes, building names)
    it would otherwise mishear, e.g. 'AHU-02' -> 'este HQ 0 2'."""
    return ", ".join(list_known_terms())


def transcribe_file(path: str) -> str:
    result = _get_model().transcribe(path, fp16=False, initial_prompt=_vocabulary_hint())
    return result["text"].strip()


def transcribe_audio(audio) -> str:
    """Transcribe a mono float32 numpy array sampled at 16kHz."""
    result = _get_model().transcribe(audio, fp16=False, initial_prompt=_vocabulary_hint())
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


def _record_until_silence(
    sd,
    device,
    sample_rate: int,
    max_duration: float,
    min_duration: float,
    silence_duration: float,
    chunk_seconds: float = 0.2,
):
    """Record from `device` until `silence_duration` seconds of quiet follow
    speech (or `max_duration` is hit), instead of a fixed-length window that
    cuts sentences off mid-word."""
    import queue

    import numpy as np

    chunks = queue.Queue()

    def callback(indata, frames, time_info, status):
        chunks.put(indata.copy())

    frames = []
    elapsed = 0.0
    silence_run = 0.0
    spoke = False

    with sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        device=device,
        blocksize=int(chunk_seconds * sample_rate),
        callback=callback,
    ):
        while elapsed < max_duration:
            chunk = chunks.get()
            frames.append(chunk)
            elapsed += chunk_seconds

            if np.abs(chunk).max() >= SILENCE_THRESHOLD:
                spoke = True
                silence_run = 0.0
            else:
                silence_run += chunk_seconds

            if spoke and elapsed >= min_duration and silence_run >= silence_duration:
                break

    return np.concatenate(frames).flatten()


def record_and_transcribe(
    max_duration: float = 15.0,
    min_duration: float = 0.6,
    silence_duration: float = 1.2,
    sample_rate: int = 16000,
) -> str:
    """Record from the microphone until the speaker pauses, then transcribe."""
    print("Loading audio backend...", flush=True)
    import numpy as np
    import sounddevice as sd

    print("Selecting input device...", flush=True)
    device = _resolve_input_device(sd)
    device_name = sd.query_devices(device)["name"] if device is not None else sd.query_devices(sd.default.device[0])["name"]
    print(f"Listening (device: {device_name}, speak now)...", flush=True)
    audio = _record_until_silence(sd, device, sample_rate, max_duration, min_duration, silence_duration)
    print("Recording finished, transcribing...", flush=True)

    if np.abs(audio).max() < SILENCE_THRESHOLD:
        print(
            f"No audio detected from '{device_name}'. If this isn't your mic, set "
            "AUDIO_INPUT_DEVICE (e.g. AUDIO_INPUT_DEVICE=MacBook). If it is your mic, check "
            "System Settings -> Privacy & Security -> Microphone and make sure your terminal "
            "app is allowed access.",
            flush=True,
        )
        return ""

    return transcribe_audio(audio)
