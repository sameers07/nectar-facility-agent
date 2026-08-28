# RAG Evaluation (Task 3)

## Retrieval quality (no LLM, `rag/store.py` directly)

Query: "What should I check when AHU airflow is low?" (threshold 0.35)

```
0.805  [PASS]  troubleshooting_faqs :: What should I check if AHU airflow is low?
0.724  [PASS]  ahu_troubleshooting :: Low airflow
0.655  [PASS]  troubleshooting_faqs :: What does a LOW_AIRFLOW alert mean in practice?
0.630  [PASS]  hvac_operating_procedures :: What is an AHU?
0.614  [PASS]  equipment_specifications :: AHU units
```

Query: "What is the recommended lubricant viscosity for Chiller-01's compressor?" (genuinely unsupported)

```
0.332  [FILTERED OUT]  chiller_manual :: Normal operating range
0.285  [FILTERED OUT]  equipment_specifications :: Chiller units
0.281  [FILTERED OUT]  chiller_manual :: Maintenance interval
0.238  [FILTERED OUT]  maintenance_procedures :: Severity levels
0.216  [FILTERED OUT]  hvac_operating_procedures :: Startup sequence

What actually reaches the LLM (score >= 0.35): (nothing)
```

## Bug found and fixed during acceptance testing: query phrasing sensitivity

The embedding model is very sensitive to query length/phrasing. Same
document, two queries:

```
query='AHU'                -> 0.301 (below threshold, false "not found")
query='what is an AHU'     -> 0.829 (correct match)
```

A bare acronym/keyword query embeds too weakly to match; a full
natural-language question embeds far more distinctively. The investigator
sometimes rewrote user questions into terse keyword queries when calling
`retrieve_facility_docs`.

**Fix**: `tools/rag_tool.py`'s tool description now explicitly requires a
full natural-language question, with an example showing the failure mode
directly ("e.g. 'What should I check if AHU airflow is low?', not 'AHU
airflow'"). `agent/prompts.py` also instructs the model to retry once with
different phrasing before concluding something isn't covered, rather than
giving up after one narrow query.

**Verified fixed** — see E2E-01 and E2E-06 in `e2e_results.md`, both live
after the fix.

## Grounded answer with source citation (E2E-01, post-fix)

```
Query: "What is an AHU?"
TOOL -> retrieve_facility_docs({'query': 'What is an AHU?'})
TOOL <- found=True, top result: hvac_operating_procedures :: What is an AHU? (score 0.832)

Agent: An AHU, or Air Handling Unit, is responsible for circulating and
conditioning air within a building zone. It works by drawing in air,
filtering it, and then heating or cooling it before supplying it through
ductwork. The airflow through an AHU is a key indicator of the health of
the zone it serves.
Confidence: 100%
Evidence:
  - hvac_operating_procedures: What is an AHU?
```

## No-hallucination test (E2E-06, PDF's explicit required test)

```
Query: "What is the recommended lubricant viscosity for Chiller-01's compressor?"
TOOL -> retrieve_facility_docs({'query': "...Chiller-01's compressor?"})
TOOL <- found=False, results=[]
TOOL -> retrieve_facility_docs({'query': 'What is the recommended lubricant viscosity for chiller compressors?'})
TOOL <- found=True but only a 0.353-score tangential match (chiller power deviation, not lubricant)

Agent: I couldn't find the recommended lubricant viscosity for Chiller-01's
compressor in the facility documentation. The available documents do not
contain this specific information.
Confidence: 10%
```

Retried with a rephrased query per the fixed prompt guidance, still
correctly refused to invent a viscosity number even though a marginal
match came back on the second attempt.

## Design decisions

- **Chunking**: split by each document's own `## ` sections rather than a
  fixed character window — documents are already organized into
  self-contained topics.
- **Embeddings**: local `sentence-transformers` (`all-MiniLM-L6-v2`), zero
  API calls.
- **Vector store**: plain numpy cosine similarity, not FAISS/Chroma —
  right-sized for a corpus of a few dozen chunks; a full ANN index solves
  a problem this dataset doesn't have.
- **Reranking/filtering**: similarity-score threshold (`MIN_SCORE = 0.35`)
  drops low-relevance chunks before they reach the LLM.
- **Integration**: retrieval is a tool (`retrieve_facility_docs`) in the
  *same* Investigator loop as the live-data tools, not a separate RAG
  agent/pipeline — the model can interleave live lookups and
  documentation retrieval within one continuous reasoning chain.
