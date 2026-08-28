from rag.loader import load_chunks
from rag.store import VectorStore
from tools.rag_tool import retrieve_facility_docs


def test_load_chunks_covers_all_knowledge_docs():
    chunks = load_chunks()
    sources = {c["source"] for c in chunks}
    assert "ahu_troubleshooting" in sources
    assert "chiller_manual" in sources
    assert all(c["heading"] and c["text"] for c in chunks)


def test_search_finds_relevant_chunk_for_low_airflow():
    store = VectorStore()
    results = store.search("AHU low airflow troubleshooting")
    assert results
    assert any(r["source"] == "ahu_troubleshooting" for r in results)


def test_search_returns_nothing_below_score_threshold():
    store = VectorStore()
    results = store.search("unrelated query", min_score=1.1)  # impossible to reach
    assert results == []


def test_retrieve_facility_docs_tool_returns_found_true():
    result = retrieve_facility_docs("What should I check if AHU airflow is low?")
    assert result["found"] is True
    assert any("airflow" in r["text"].lower() for r in result["results"])


def test_retrieve_facility_docs_reports_not_found_for_irrelevant_query():
    from rag import store as rag_store

    # force a fresh store scoped to an empty corpus for this test only
    empty_store = VectorStore(chunks=[])
    original = rag_store._store
    rag_store._store = empty_store
    try:
        result = retrieve_facility_docs("anything")
        assert result == {"found": False, "results": []}
    finally:
        rag_store._store = original
