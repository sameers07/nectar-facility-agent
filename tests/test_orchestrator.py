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


def test_knowledge_question_delegates_to_investigator_with_rag_tool():
    contract = {
        "intent": "knowledge_question",
        "sources": ["rag"],
        "action_required": False,
        "complexity": "low",
        "confidence": 0.98,
    }
    responses = [
        llm_response(
            tool_calls=[
                tool_call(
                    "1",
                    "submit_conclusion",
                    {"conclusion": "An AHU circulates and conditions air.", "confidence": 0.9, "evidence": []},
                )
            ]
        )
    ]
    captured = {}

    def investigator_factory(model, extra_schemas=None, extra_dispatch=None):
        captured["schemas"] = extra_schemas
        captured["dispatch"] = extra_dispatch
        return Investigator(client=ScriptedClient(responses))

    orchestrator = Orchestrator(router=FixedRouter(contract), investigator_factory=investigator_factory)
    result = orchestrator.handle("What is an AHU?", Session())

    assert captured["schemas"][0]["function"]["name"] == "retrieve_facility_docs"
    assert "retrieve_facility_docs" in captured["dispatch"]
    assert "AHU" in result["conclusion"]


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

    def investigator_factory(model, extra_schemas=None, extra_dispatch=None):
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
    captured = {}

    def investigator_factory(model, extra_schemas=None, extra_dispatch=None):
        used_models.append(model)
        captured["schemas"] = extra_schemas
        return Investigator(client=ScriptedClient(responses))

    orchestrator = Orchestrator(router=FixedRouter(contract), investigator_factory=investigator_factory)
    orchestrator.handle("Why did Chiller-01 fail?", Session())

    assert used_models == [STRONG_MODEL]
    # diagnosis needs both live_data and rag -- the investigator should get the rag tool too
    assert captured["schemas"][0]["function"]["name"] == "retrieve_facility_docs"


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


def test_rag_not_found_does_not_hallucinate():
    """PDF's explicit Task 3 test: a question the knowledge base doesn't
    cover must say so, not invent an answer."""
    contract = {
        "intent": "knowledge_question",
        "sources": ["rag"],
        "action_required": False,
        "complexity": "low",
        "confidence": 0.9,
    }
    responses = [
        llm_response(tool_calls=[tool_call("1", "retrieve_facility_docs", {"query": "elevator maintenance"})]),
        llm_response(
            tool_calls=[
                tool_call(
                    "2",
                    "submit_conclusion",
                    {
                        "conclusion": "I don't have documentation covering elevator maintenance.",
                        "confidence": 0.1,
                        "evidence": [],
                    },
                )
            ]
        ),
    ]

    def investigator_factory(model, extra_schemas=None, extra_dispatch=None):
        return Investigator(client=ScriptedClient(responses), extra_tool_schemas=extra_schemas, extra_tool_dispatch=extra_dispatch)

    orchestrator = Orchestrator(router=FixedRouter(contract), investigator_factory=investigator_factory)
    result = orchestrator.handle("How do I service the elevator?", Session())

    assert result["confidence"] < 0.5
    assert "don't have" in result["conclusion"].lower()
