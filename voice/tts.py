"""Text-to-speech: local engine (pyttsx3). No API key required."""


def speak(text: str) -> None:
    import pyttsx3

    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()
