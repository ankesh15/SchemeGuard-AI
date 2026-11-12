# Approved-source retrieval and explanations

Retrieval augments citations and explanation presentation. **Only the deterministic eligibility engine computes PASS, FAIL or UNKNOWN.** A vector score, question answer, extraction candidate or Gemini response cannot change its result, operators or thresholds.

## Embeddings and storage

`ChunkEmbedding` references the existing immutable `DocumentChunk`. It stores provider, model, dimension, text checksum, normalized vector and creation time; `(chunk_id, provider, model)` is unique. The migration installs pgvector in PostgreSQL 16. No additional database or vector service runs.

The default provider uses the official Google GenAI SDK with `gemini-embedding-001`, `output_dimensionality=768`, `RETRIEVAL_DOCUMENT` for chunks and `RETRIEVAL_QUERY` for queries. Exactly 768 finite, nonzero values are required and L2-normalized. Changing dimension requires a new migration and compatible namespace, not relabeling old vectors. Provider and model namespaces never mix. Indexing operates on one document with bounded batches and commits atomically; failures roll back vectors without altering source pages or policy records. Re-indexing preserves existing rows. The model/key stay backend-only.

`EMBEDDING_PROVIDER=local_hash` is an explicit development/test fixture using deterministic lexical feature hashing. It is **not a semantic model or a Gemini fallback**, and is forbidden in production. The UI/API label its retrieval mode `local_fixture_vector`. Automated pgvector integration tests use this fixture for reproducibility.

Configuration: `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS=768`, `EMBEDDING_TIMEOUT`, `EMBEDDING_MAX_RETRIES`, `RAG_TOP_K` (max 10), `RAG_MAX_CHUNKS` (max 1000), `RAG_MIN_SIMILARITY`. Transient timeout/429/5xx failures receive bounded exponential backoff. Missing credentials, invalid vectors and provider failures never generate fabricated embeddings. Administrator indexing returns 503 when unavailable.

## Retrieval boundaries

Public callers cannot choose pending policy authority. The service first selects the currently effective approved rule set using the unchanged RuleRepository. SQL then restricts chunks to that exact scheme and source document version. An optional document filter can narrow this further; a mismatching version returns no evidence. Model, text checksum and dimension are checked. Cosine distance ranks only the resulting allowed rows. Exact vector scans are appropriate for this MVP; no approximate HNSW tuning or performance claims are made.

Each retrieved excerpt must occur on its stored source page/block. Citations include scheme ID, approved rule-set ID, document version, SHA-256, chunk ID, page number, source title, publisher, exact excerpt and official URL with `#page=N`. An inaccessible/changed remote website does not alter preserved original bytes; public links still point to the official source and protected administrators can download the preserved original.

If embeddings or vectors are unavailable, a bounded lexical search may return matching passages from the same approved document. This is explicitly `lexical_fallback`, not successful semantic retrieval. If no relevant passage exists, the response says the approved source does not establish the information. Sources from unrelated schemes and unapproved versions are never substituted. Legacy fictional Markdown evidence has section references rather than invented PDF page numbers.

## Assessment explanations

`POST /api/v1/eligibility/explain` accepts the existing synthetic-only request, evaluates it on the server and returns `{report, explanation}`. The existing `/eligibility/check` contract remains available unchanged. The report's approved RuleEvidence remains authoritative even if retrieval fails. Passed, failed and unknown requirements, missing fields, result and version are copied from that server-produced report.

Default explanations are deterministic templates plus citations. With `EXPLANATION_USE_GEMINI=true`, Gemini may produce a structured plan containing only existing trace keys and citation IDs. Unknown, duplicate or missing identifiers and any provider error fall back to templates. The model never returns decision values or policy prose to users. No applicant profile is supplied to Gemini, persisted or logged. The frontend keeps the report and explanation only in React memory.

## Constrained document questions

`POST /schemes/{id}/questions` recognizes requirements, income, documents, disability, application and benefit intents. Only a fixed intent query is sent to embeddings; arbitrary questions or personal details are not forwarded to the provider. Responses quote up to three relevant approved-document excerpts with page citations and no generated eligibility advice. General-purpose questions and absent information receive an explicit evidence gap. Public grounding calls are database-rate-limited by the hashed direct connection address and return no-store responses; proxy deployments need a deliberately configured trusted-client strategy before scaling.

References: [Google embedding documentation](https://ai.google.dev/gemini-api/docs/embeddings), [pgvector](https://github.com/pgvector/pgvector), [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence), [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts).
