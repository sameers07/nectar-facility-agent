from agent.errors import LLMProviderError, RoutingError
from agent.investigator import Investigator
from agent.orchestrator import Orchestrator
from agent.router import FAST_MODEL, STRONG_MODEL
from agent.state import Session
from tests.support import ScriptedClient, llm_response, tool_call


class FixedRouter:
    def __init__(self, contract):
        self.contract = contract

    def route(self, user_message, session):
        return self.contract


class RaisingRouter:
    def __init__(self, error):
        self.error = error

    def route(self, user_message, session):
        raise self.error


def test_knowledge_question_routes_to_rag_placeholder():
    contract = {
        "intent": "knowledge_question",
        "sources": ["rag"],
        "action_required": False,
        "complexity": "low",
        "confidence": 0.98,
    }
    orchestrator = Orchestrator(router=FixedRouter(contract))
    session = Session()

    result = orchestrator.handle("What is an AHU?", session)

    assert "knowledge base" in result["conclusion"]
    assert session.conversation[0] == {"role": "user", "content": "What is an AHU?"}


def test_live_status_delegates_to_investigator_with_fast_model():
    contract = {
        "intent": "live_status",
        "sources": ["live_data"],
        "action_required": False,
        "complexity": "low",
        "confidence": 0.99,
    }
    responses = [
        llm_response(tool_calls=[tool_call("1", "get_building_temperature", {"building": "Building A"})]),
        llm_response(
            tool_calls=[
                tool_call(
                    "2",
                    "submit_conclusion",
                    {"conclusion": "Building A is at 28.4C.", "confidence": 1.0, "evidence": []},
                )
            ]
        ),
    ]
    used_models = []

    def investigator_factory(model):
        used_models.append(model)
        return Investigator(client=ScriptedClient(responses))

    orchestrator = Orchestrator(router=FixedRouter(contract), investigator_factory=investigator_factory)
    result = orchestrator.handle("What is Chiller-01's current temperature?", Session())

    assert used_models == [FAST_MODEL]
    assert "28.4" in result["conclusion"]


def test_diagnosis_delegates_to_investigator_with_strong_model():
    contract = {
        "intent": "diagnosis",
        "sources": ["live_data", "rag"],
        "action_required": False,
        "complexity": "high",
        "confidence": 0.91,
    }
    responses = [
        llm_response(
            tool_calls=[
                tool_call(
                    "1",
                    "submit_conclusion",
                    {"conclusion": "AHU-02 low airflow is the likely cause.", "confidence": 0.9, "evidence": []},
                )
            ]
        )
    ]
    used_models = []

    def investigator_factory(model):
        used_models.append(model)
        return Investigator(client=ScriptedClient(responses))

    orchestrator = Orchestrator(router=FixedRouter(contract), investigator_factory=investigator_factory)
    orchestrator.handle("Why did Chiller-01 fail?", Session())

    assert used_models == [STRONG_MODEL]


def test_action_request_routes_to_action_placeholder():
    contract = {
        "intent": "action_request",
        "sources": ["live_data", "action"],
        "action_required": True,
        "complexity": "low",
        "confidence": 0.95,
    }
    orchestrator = Orchestrator(router=FixedRouter(contract))
    result = orchestrator.handle("Create a maintenance request for AHU-02.", Session())

    assert "live systems" in result["conclusion"]


def test_low_confidence_asks_for_clarification():
    contract = {
        "intent": "unknown",
        "sources": [],
        "action_required": False,
        "complexity": "low",
        "confidence": 0.31,
    }
    orchestrator = Orchestrator(router=FixedRouter(contract))
    result = orchestrator.handle("Something seems wrong.", Session())

    assert "clarify" in result["conclusion"].lower()


def test_llm_provider_error_gives_try_again_message():
    orchestrator = Orchestrator(router=RaisingRouter(LLMProviderError("boom")))
    result = orchestrator.handle("What is an AHU?", Session())

    assert "try again" in result["conclusion"].lower()


def test_routing_error_gives_rephrase_message():
    orchestrator = Orchestrator(router=RaisingRouter(RoutingError("bad contract")))
    result = orchestrator.handle("What is an AHU?", Session())

    assert "rephrase" in result["conclusion"].lower()


def test_unavailable_capability_declines_instead_of_hallucinating():
    contract = {
        "intent": "energy_usage",
        "sources": ["energy"],
        "action_required": False,
        "complexity": "low",
        "confidence": 0.9,
    }
    orchestrator = Orchestrator(router=FixedRouter(contract))
    result = orchestrator.handle("What's the current energy consumption?", Session())

    assert "energy" in result["conclusion"]
    assert "can't access" in result["conclusion"]
