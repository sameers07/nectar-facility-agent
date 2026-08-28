"""Interactive CLI for the facility investigator.

Text mode (default):   python app.py
Voice mode (mic/speaker, local Whisper STT + local TTS): python app.py --voice
"""
import argparse
import logging
import os
import sys

from dotenv import load_dotenv

from agent.investigator import Investigator
from agent.state import Session

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(message)s")


def get_user_message(voice: bool) -> str:
    if voice:
        from voice.stt import record_and_transcribe

        text = record_and_transcribe().strip()
        if text:
            print(f"You: {text}")
        return text
    return input("\nYou: ").strip()


def respond(result: dict, voice: bool) -> None:
    print(f"\nAgent: {result['conclusion']}")
    if result.get("confidence") is not None:
        print(f"Confidence: {result['confidence']:.0%}")
    if result.get("evidence"):
        print("Evidence:")
        for fact in result["evidence"]:
            print(f"  - {fact}")
    if voice:
        from voice.tts import speak

        speak(result["conclusion"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--voice", action="store_true", help="Use microphone input and spoken output.")
    args = parser.parse_args()

    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")):
        print("GEMINI_API_KEY is not set. Copy .env.example to .env and fill it in.")
        sys.exit(1)

    investigator = Investigator()
    session = Session()
    print("Facility investigator ready. Ask about a building or HVAC asset (Ctrl+C to quit).")

    while True:
        try:
            user_message = get_user_message(args.voice)
        except (KeyboardInterrupt, EOFError):
            break
        if not user_message:
            continue

        result = investigator.investigate(user_message, session)
        respond(result, args.voice)


if __name__ == "__main__":
    main()
