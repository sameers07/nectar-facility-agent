import logging

from agent.orchestrator import Orchestrator
from agent.state import Session

logger = logging.getLogger("voice_agent")


class VoiceAgent:
    """Ties the request router/orchestrator, session memory, and I/O (text
    or voice) together into one runnable loop."""

    def __init__(self, voice: bool = False, orchestrator: Orchestrator = None):
        self.voice = voice
        self.orchestrator = orchestrator or Orchestrator()
        self.session = Session()

    def get_user_message(self) -> str:
        if self.voice:
            from voice.stt import record_and_transcribe

            text = record_and_transcribe().strip()
            if text:
                print(f"You: {text}")
            return text
        return input("\nYou: ").strip()

    def respond(self, result: dict) -> None:
        print(f"\nAgent: {result['conclusion']}")
        if result.get("confidence") is not None:
            print(f"Confidence: {result['confidence']:.0%}")
        if result.get("evidence"):
            print("Evidence:")
            for fact in result["evidence"]:
                print(f"  - {fact}")
        if self.voice:
            from voice.tts import speak

            speak(result["conclusion"])

    def step(self) -> bool:
        """Process one conversational turn. Returns False when the user quits."""
        try:
            user_message = self.get_user_message()
        except (KeyboardInterrupt, EOFError):
            return False
        if not user_message:
            return True

        try:
            result = self.orchestrator.handle(user_message, self.session)
        except Exception:
            logger.exception("Unhandled error processing request")
            result = {"conclusion": "Something went wrong on my end. Could you try that again?", "confidence": None}
        self.respond(result)
        return True

    def run(self) -> None:
        print("Facility investigator ready. Ask about a building or HVAC asset (Ctrl+C to quit).")
        while self.step():
            pass
