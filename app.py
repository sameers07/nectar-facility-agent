"""Interactive CLI for the facility investigator.

Text mode (default):   python app.py
Voice mode (mic/speaker, local Whisper STT + local TTS): python app.py --voice
"""
import argparse
import logging
import os
import sys

from dotenv import load_dotenv

from agent.voice_agent import VoiceAgent

sys.stdout.reconfigure(line_buffering=True)
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(message)s")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--voice", action="store_true", help="Use microphone input and spoken output.")
    args = parser.parse_args()

    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")):
        print("GEMINI_API_KEY is not set. Copy .env.example to .env and fill it in.")
        sys.exit(1)

    VoiceAgent(voice=args.voice).run()


if __name__ == "__main__":
    main()
