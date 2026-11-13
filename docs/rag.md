# Retrieval and evidence

pgvector stores model/provider-namespaced embeddings of stable page-aware chunks. Retrieval is SQL-scoped to the selected scheme, approved rule and its exact source document before ranking. Chunk hashes and page containment are checked; unrelated/pending versions cannot become supporting evidence. A bounded lexical fallback is available when embeddings are unavailable. Fictional local-hash vectors are forbidden by production configuration.

Public questions are classified into fixed document intents. Arbitrary applicant questions and profiles are not sent to embedding/LLM providers. Answers quote located source passages and include document ID/checksum/page/locator/source URL/approved rule ID. Unknown or unsupported questions return an explicit lack-of-evidence response. Similarity never determines eligibility. Private saved assessments use their original evidence-backed deterministic traces and do not send profiles to RAG.

The isolated Phase 7 demonstration indexed synthetic document chunks, retrieved page-1 citations and retained provenance through policy replacement. Exact source citation location was also evaluated on three hand-authored reference clauses. These checks are not a real Gemini retrieval-accuracy benchmark. See rag-architecture.md and verification/demonstration.json for the implementation and measured run.
