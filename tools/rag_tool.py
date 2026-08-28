"""Facility knowledge retrieval as a tool, backed by rag/store.py. Only
attached to an investigation when the router decides a request needs
"rag" -- kept separate from tools/registry.py's always-on facility tools
since it's conditionally exposed, not part of the default set.
"""
from rag.store import get_store

RAG_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "retrieve_facility_docs",
        "description": (
            "Search facility documentation (manuals, troubleshooting guides, "
            "maintenance procedures, safety instructions, policies) for "
            "passages relevant to a query."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "A full natural-language question or sentence, not a bare keyword or "
                        "acronym -- e.g. 'What should I check if AHU airflow is low?', not "
                        "'AHU airflow'. Short keyword-only queries retrieve much worse."
                    ),
                }
            },
            "required": ["query"],
        },
    },
}


def retrieve_facility_docs(query: str) -> dict:
    results = get_store().search(query)
    if not results:
        return {"found": False, "results": []}
    return {
        "found": True,
        "results": [
            {"source": r["source"], "heading": r["heading"], "text": r["text"], "score": round(r["score"], 3)}
            for r in results
        ],
    }
