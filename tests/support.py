"""Shared test doubles for exercising Investigator without a real OpenAI call."""
import json
from types import SimpleNamespace


def tool_call(call_id, name, arguments):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


def llm_response(tool_calls=None, content=None):
    message = SimpleNamespace(tool_calls=tool_calls, content=content)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class ScriptedClient:
    """Fake OpenAI client that replays a fixed sequence of responses."""

    def __init__(self, responses):
        self._responses = iter(responses)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return next(self._responses)
