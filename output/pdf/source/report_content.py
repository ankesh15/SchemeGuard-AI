# SchemeGuard report content. All numerical findings are attributed to recorded
# repository artifacts; this report generation does not rerun application tests.

new(('1','Introduction'))
h('1.1','Background')
add('Indian government programmes span education, agriculture, healthcare, employment, housing and social protection. Information is published through national portals, state directories, ministry pages and policy PDFs. A citizen may find a scheme name without finding the complete, current conditions that apply to an individual application. Scheme discovery and eligibility verification are therefore different engineering problems.')
add('Official services such as myScheme support personalized discovery [1], while departmental guidelines remain the source of policy detail. SchemeGuard is an academic implementation that studies how discovery, document evidence, deterministic evaluation and policy history can be connected responsibly. It does not replace an official application portal or issue government approval.')
h('1.2','Motivation')
add('The project is motivated by three practical needs: reduce manual catalog searching, explain every supported assessment, and preserve what changed when a policy is updated. A useful system must also say when information is missing. Returning UNKNOWN is safer and more accurate than presenting an unsupported positive decision.')

new();h('1.3','Problem Statement')
add('Given a partially specified citizen profile and a catalog of government scheme metadata, identify schemes worth exploring and explain their relevance. Where an applicable human-approved policy exists, evaluate the supplied information deterministically, retain its supporting evidence and rule version, and identify missing inputs. When an authorized policy document changes, propose and review the change before publishing a new policy and reassessing affected consenting users.')
add('The problem includes uncertainty at several levels: incomplete user information, unknown geographic coverage, inaccessible or image-only documents, ambiguous policy wording, missing effective dates and conflicting versions. None of these uncertainties may be silently converted into a verified eligibility condition.')
h('1.4','Objectives')
tbl('1','Project objectives and measurable completion evidence',['Objective','Implementation / verification evidence'],[
('Personalized discovery','Profile-first questionnaire and shared deterministic recommendation service over PostgreSQL.'),
('Explainable assessment','Typed PASS/FAIL/UNKNOWN evaluation with condition traces and missing fields.'),
('Evidence preservation','Immutable document versions, page-aware chunks, located excerpts and source checksums.'),
('Controlled AI processing','Structured Gemini candidates, LangGraph checkpoints and mandatory human publication review.'),
('Policy continuity','Approved-only policy changes, historical replay, consent-aware reassessment and deduplicated notifications.'),
('Reliable engineering','Docker services, incremental migrations, regression tests, isolated demonstration and recovery records.')],[1,2.5])
add('These objectives describe implemented capabilities; their verification scope and remaining operational gaps are separated in Chapter 5. Broad catalog coverage does not imply equally broad executable policy coverage.')

new();h('1.5','Scope and Limitations')
add('SchemeGuard supports guest discovery, citizen accounts, optional encrypted profiles, saved approved-policy assessments, an administrator document workspace and selected-source monitoring. The primary journey begins with user preferences rather than a grid of hundreds of records. Manual browsing remains available as a secondary route.')
tbl('2','Recorded dataset and executable-policy scope',['Item','Recorded status'],[
('Government discovery records','282 identities in 23 category manifests; metadata provenance reviewed.'),
('All database scheme records','283, including one separate legacy development scheme.'),
('Approved government rule sets','0; no claim of verified eligibility coverage for 282 schemes.'),
('Approved development rule sets','1, retained for reproducible demonstrations and historical tests.'),
('Illustrative assessment coverage','9 project-authored templates cover 225 government metadata records in 14 categories; 57 remain unsupported.'),
('Preserved documents','2 versions; 1 historical official PDF processed into 4 pages and 26 chunks.'),
('Live monitoring enrollment','0 sources in the recorded working database; enrollment is deliberate and opt-in.')],[1.1,2.3])
add('The illustrative path is explicitly separated from approved government policy. It reuses typed evaluation, but has no government rule citations, is not saved as an approved-policy assessment and cannot trigger policy reassessment. Income and age values from such templates never influence recommendation ranking.')
add('The MVP does not include Aadhaar collection, identity-document processing, payment disbursement, submission to government portals, a large OCR subsystem, email delivery, verified password recovery or production identity verification. Live Gemini accuracy and cloud deployment have not been established.')

new();h('1.6','Organisation of the Report')
add('Chapter 2 reviews relevant official platforms, retrieval-augmented generation, agent orchestration, structured output and decision/provenance approaches. It identifies the design gap that motivates the project. Chapter 3 formulates discovery and eligibility separately and describes the implemented methodology from metadata intake through policy-change reassessment.')
add('Chapter 4 explains the technology stack, modules, database, API contracts, user interface, security and operational configuration. Chapter 5 reports recorded tests, synthetic workflow outcomes, evaluation counts and local measurements with their limits. Chapter 6 summarizes the contribution and identifies concrete future work. References document external sources and repository evidence. Appendix A records the status of academic integrity reports; Appendix B provides only known author information.')
sub('Engineering principles')
add('The application is a modular monolith with independently running background workers. One canonical document and rule representation is reused across ingestion, human review, monitoring and evaluation. New features append history rather than resetting PostgreSQL or rewriting old decisions. API contracts remain versioned and backward compatible.')
add('Four invariants govern the implementation: only approved applicable policies support strict eligibility decisions; every executable condition requires located evidence; missing information remains UNKNOWN; and an LLM cannot approve a policy or override deterministic output. The demonstration environment labels project-authored material and preserves the distinction between technical tests and genuine government policy approval.')
sub('Report evidence boundary')
add('Counts and test results in this report come from the repository verification snapshot dated 14 November 2026 [14]-[19]. Older phase measurements are identified separately. Preparing this document did not rerun backend tests, publish rules, change user records or deploy services. This boundary makes the report auditable without presenting historical evidence as a new execution.')

new(('2','Literature Survey'))
add('The survey focuses on approaches relevant to scheme discovery, evidence-grounded document processing and controlled decision automation. It reviews official platforms, research papers and primary technical specifications. Published methods are used as design context; SchemeGuard does not claim to reproduce their benchmark results.')
h('2.1','Government Scheme Discovery Platforms')
add('The Government of India\'s myScheme initiative describes a service for finding programmes using citizen information and understanding eligibility and application steps [1]. It demonstrates the value of starting with a user\'s needs. SchemeGuard adopts that interaction direction, while retaining a smaller curated catalog and an explicit academic demonstration scope.')
add('DBT Bharat and the Government of Goa directories provide official scheme identities used in the project\'s static dataset [2], [3]. Their listings establish traceable discovery metadata, not a complete machine-readable policy. SchemeGuard therefore does not interpret directory presence as an active application window or assume universal state coverage. The National Scholarship Portal is also a provenance source for preserved scholarship records [4].')

new();h('2.2','Retrieval-Augmented Generation')
add('Lewis et al. introduced retrieval-augmented generation for knowledge-intensive NLP tasks by combining a parametric language model with access to external passages [5]. The work is relevant because policy explanations require identifiable source material rather than reliance on a model\'s internal memory. Its general retrieval-generation architecture motivates evidence-aware assistance, but it does not by itself establish whether a government clause is current, complete or approved.')
add('SchemeGuard applies a stricter domain boundary: retrieval is scoped to an approved scheme, rule version and exact source document before ranking. Returned passages carry page and checksum references. Similarity can help locate explanatory text, but is never used as a personal eligibility decision. The project does not reproduce the paper\'s training procedure or its open-domain question-answering benchmarks.')
h('2.3','Agent Reasoning and Controlled Workflows')
add('Yao et al.\'s ReAct method interleaves reasoning and actions so that a language model can gather information and revise task execution [6]. It illustrates the usefulness of explicit stages and tool interaction. However, an unrestricted agent is unsuitable for policy activation: a plausible reasoning trace is not proof that a clause has an official source or that a reviewer approved it.')
add('The implementation uses a fixed LangGraph state graph with persisted checkpoints and a human-review interrupt [7]. Its nodes prepare the document, reuse extraction, verify evidence, validate the complete proposal, wait for review, publish or reject, and complete. The graph orchestrates existing services rather than allowing model-generated code or arbitrary actions. LangGraph provides the persistence mechanism; SchemeGuard supplies the authorization and publication invariants.')

new();h('2.4','Structured Document Extraction')
add('Gemini structured output supports schema-constrained responses and Pydantic-based definitions through the Google GenAI SDK [8]. This reduces formatting ambiguity when requesting candidate fields, typed values, operators and evidence references. A well-formed response can still contain a wrong interpretation, so schema conformance is treated as a technical gate rather than proof of policy truth.')
add('PyMuPDF supports page-level text and block extraction and can assist with table discovery [9]. These capabilities suit digitally generated government PDFs, but reading order and table semantics still require review. SchemeGuard preserves page numbers and source locations; blank, corrupted or image-only pages are marked incomplete instead of filled by the model. A large OCR subsystem is outside the present scope.')
h('2.5','Decision Models and Data Provenance')
add('The Object Management Group\'s Decision Model and Notation specification formalizes decision descriptions and their inputs [10]. It provides relevant context for separating explicit policy logic from application code. SchemeGuard uses its own bounded typed expression schema; it does not claim DMN or FEEL conformance. Its three-valued outcomes handle missing inputs directly and are independently testable.')
add('The W3C PROV data model distinguishes entities, activities and agents involved in producing information [11]. That perspective is useful for tracing a PDF through extraction, review, publication and assessment. SchemeGuard implements relational provenance with document IDs, page excerpts, revision digests and reviewer references rather than claiming a PROV serialization. The combined design makes evidence lineage and authorized transitions inspectable.')

new();h('2.6','Comparative Summary')
tbl('3','Related approaches and their relevance to SchemeGuard',['Source / approach','Useful contribution','Boundary / design response'],[
('myScheme [1]','Citizen-oriented scheme discovery and application guidance.','External official platform; SchemeGuard is a separate academic system with a smaller reviewed catalog.'),
('DBT Bharat / Goa [2], [3]','Official, traceable catalog identities and departments.','Directory metadata is not executable eligibility or proof of current enrollment.'),
('Lewis et al., RAG [5]','Retrieve source passages to support language generation.','Scope retrieval to approved versions; citations do not themselves prove policy completeness.'),
('Yao et al., ReAct [6]','Explicit interaction between model reasoning and actions.','Use a bounded graph and authenticated review; models cannot activate policy.'),
('Gemini structured output [8]','Machine-validatable response structures.','Validate semantics, evidence, units and conflicts; candidates stay pending.'),
('DMN / W3C PROV [10], [11]','Explicit decisions and inspectable information lineage.','Custom typed rules and relational provenance; no standards-conformance claim.')],[1.1,1.5,2])
add('The comparison concerns architectural suitability, not a benchmark leaderboard. The reviewed methods solve different tasks and use different datasets, so a single accuracy comparison would be misleading. The project evaluates its own guards, typed decisions and workflow transitions separately in Chapter 5.')

new();h('2.7','Research Gap')
add('The central gap is the connection between discovery, evidence and change history. A catalog can explain what a programme is without encoding every condition. A generative model can suggest conditions without proving that they are supported. A rule engine can calculate a result while losing the source context or selecting an ambiguous policy version. A monitoring service can detect new bytes without knowing whether eligibility actually changed.')
add('SchemeGuard addresses these gaps through a sequence of accountable boundaries. Relevance matching narrows the catalog using optional profile signals. Official documents remain immutable. Candidate expressions are mapped to a fixed typed language, evidence is located on stored pages, and a reviewer approves an exact saved revision. Eligibility evaluation then uses only the applicable approved version. Later changes append new documents and rules, preserve old reports and trigger authorized reassessment.')
sub('Position of the contribution')
add('The contribution is an integrated engineering design and a reproducible implementation, rather than a newly trained language model or a claim to improve national benefit allocation. The project combines a transparent recommendation heuristic, conservative three-valued logic, version-aware provenance and reliable background execution in one deployable system.')
add('The current limits remain material. No real government rule set has been approved in the working database, broad discovery depends on static metadata, and real Gemini extraction accuracy is unmeasured. The resulting system demonstrates how verified policy support can be added safely; it does not claim completed machine-verifiable coverage for every catalog entry.')

new(('3','Problem Formulation and Proposed Methodology'))
h('3.1','Problem Formulation')
add('Let S be the catalog of schemes, P a partially specified profile, D the immutable document versions and R the reviewed rule versions. Discovery computes an ordered subset Rec(P, S). Strict eligibility computes E(P, r, t) only when rule r is approved and applicable on assessment date t. A saved assessment retains the exact r, t, minimal inputs and evidence needed to reproduce E.')
add('The outputs belong to different domains: recommendation relevance is HIGH, POTENTIAL or MORE_INFORMATION, while a deterministic condition result is PASS, FAIL or UNKNOWN. A high relevance score does not establish eligibility. If no approved policy is available, the strict service returns UNKNOWN with no evaluated rule version. Unsupported illustrative assessment requests are also refused rather than fabricated.')
add('A policy change is a reviewed relationship between old and new document/rule versions, not merely a different PDF checksum. Publication and reassessment are separate, auditable activities.')

new();h('3.2','Overview of the Proposed System')
fig('3.1','Overall architecture of SchemeGuard','architecture',285)
add('The frontend provides guest, citizen and administrator experiences. FastAPI exposes versioned contracts and delegates to reusable services. PostgreSQL stores authoritative scheme metadata, immutable policy history, encrypted private records, durable jobs and graph checkpoints. Workers run the same ingestion and evaluation services independently from request handling.')
add('The document path and the citizen path meet only at approved policy versions and source-grounded reports. Applicant profiles are not sent to Gemini or embedded for RAG. Redis is a delivery mechanism for job identifiers, while original documents live in persistent storage with checksummed references. This separation prevents a model response or broker message from becoming the authoritative policy record.')

new();h('3.3','Data Collection and Pre-processing')
add('The static catalog is organized as 23 category JSON manifests. The expansion preserved the original five scholarship records and added 277 distinct government identities: 224 central directory records and 53 Goa state records [14]. Every record has a stable slug, source provenance and a verification date. Unverified geography, benefits, thresholds and deadlines remain unknown.')
tbl('4','Catalog provenance and verification scope',['Source group','Records','What was verified'],[
('Original official scholarship sources','5','Preserved metadata and original source relationships; review date 11 November 2026.'),
('DBT Bharat central directory','224 new','Named entries and departmental context, reviewed 12 November 2026.'),
('Government of Goa directory','53 new','Distinct state-programme identities and listed source references, reviewed 12 November 2026.'),
('Government catalog total','282','Identity and discovery metadata; not complete current policy eligibility.')],[1.4,.55,2.5])
add('The loader validates every manifest before importing. It rejects unsupported properties, category mismatches, duplicate slugs, normalized duplicate names, unsafe official URLs and inconsistent state applicability. A transaction-scoped advisory lock serializes insertion. Existing slugs are skipped without rewriting their UUIDs, sources or historical rules; a failure rolls back the import.')
sub('Document pre-processing')
add('Authorized originals are hashed and registered before extraction. Text normalization is conservative: it supports locating excerpts and comparing content but does not invent a missing clause. Page text, blocks, extraction issues and chunk identities are retained so that reviewers can return to the source. Policy publication dates are not inferred from download timestamps or PDF metadata.')

new();h('3.4','Explainable Profile-based Recommendations')
add('Recommendation inputs reuse the existing optional ProfileData schema. Interests map to the catalog taxonomy; occupation, employment and explicit student status add broad relevance signals. Verified geography can refine a result, while unknown coverage remains included with an explanation. Only an explicitly verified state mismatch can exclude a geographically incompatible record.')
tbl('5','Implemented additive relevance factors',['Signal','Points','Interpretation'],[
('Selected interest matches category','+60','Project-authored relevance heuristic.'),
('Occupation / employment category match','+20 once','Explicit input signal, not inferred demographics.'),
('Current student and education category','+20','Broad educational relevance.'),
('Verified national / matching-state coverage','+8','Catalog provenance supports applicability.'),
('Safely loadable approved assessment','+5','Reviewed policy is available.'),
('Positive direct approved education match','+15','Conservative typed approved-condition comparison.'),
('All known approved conditions pass','+12','Existing deterministic engine result.'),
('Known approved conditions fail','-20','Visible warning; never hidden as a score alone.')],[2,.6,2.2])
add('Ranking uses the sum of applicable factors, with a HIGH label at 75 points or above. Other matches are POTENTIAL; a reviewed-condition failure is labeled MORE_INFORMATION with a warning. At least one substantive profile/category or approved-condition signal is required. Geography and assessment availability alone cannot recommend an unrelated scheme.')
add('Tie-breaking is deterministic by case-insensitive scheme name and UUID. Category filters apply to the matched set before pagination. Scores are ordering heuristics, not confidence percentages. Illustrative income/age thresholds never enter this ranking function.')

new();h('3.5','Deterministic Eligibility Evaluation')
add('The engine evaluates a validated abstract syntax tree. Comparisons support ==, !=, &gt;, &lt;, &gt;=, &lt;=, IN and NOT IN over declared number, string, boolean and ISO-date values. Decimal normalization avoids inconsistent financial boundary comparisons. No stored expression is executed as Python code; eval() and exec() are not used.')
tbl('6','Three-valued AND and OR semantics',['A','B','AND(A, B)','OR(A, B)'],[
('PASS','PASS','PASS','PASS'),('PASS','FAIL','FAIL','PASS'),('PASS','UNKNOWN','UNKNOWN','PASS'),('FAIL','FAIL','FAIL','FAIL'),('FAIL','UNKNOWN','FAIL','UNKNOWN'),('UNKNOWN','UNKNOWN','UNKNOWN','UNKNOWN')],[1,1,1.25,1.25])
add('For groups of any supported size, AND returns FAIL if any child fails; otherwise UNKNOWN if any child is unknown; otherwise PASS. OR returns PASS if any child passes; otherwise UNKNOWN if any child is unknown; otherwise FAIL. These rules preserve incomplete information instead of treating absence as success.')
add('Exclusions invert established truth: a matching exclusion produces FAIL, a nonmatching exclusion produces PASS, and an unknown exclusion stays UNKNOWN. A conditional evaluates its guard first. An unknown prerequisite keeps the conditional UNKNOWN; a known guard selects only the applicable branch. Missing fields in irrelevant branches are not demanded as established requirements.')
add('Every node produces a stable key, label, result, explanation, missing fields and child traces. The report presents these as known conditions satisfied, requirements not satisfied or more information required. None of the labels constitutes government approval.')

new();sub('Typed example and version gate')
add('The following expression is a <b>fictional test clause</b>, used only to explain the data shape. The value is not asserted as the threshold of any real government scheme.')
code('''{
  "kind": "comparison",
  "key": "income_ceiling",
  "field": "annual_family_income_inr",
  "operator": "<=",
  "value_type": "number",
  "value": 250000
}''')
add('For this test clause, an input of 250000 passes the inclusive boundary; 250001 fails; an absent or null income produces UNKNOWN. The boundary is fixed by the stored operator and typed value. A language model is not called during evaluation.')
add('Before the engine runs, the eligibility service loads a policy through the approved-version repository. Draft, rejected, future or expired policies cannot support the current decision. Unrelated overlapping applicable versions raise a conflict instead of silently choosing the largest number. A reviewed replacement relationship can resolve an overlap while preserving prior content.')
add('Program validation rejects duplicate expression keys, references to undeclared fields, incompatible operators and types, non-finite numbers, malformed dates and oversized trees. The implementation bounds depth to 12, total nodes to 128 and program inputs to 32 fields. These limits constrain both accidental complexity and malicious stored input.')
add('The strict policy service remains distinct from the opt-in illustrative assessment path. A server-selected criteria token prevents a stale questionnaire from silently evaluating against a changed basis. Illustrative output includes its template version and fingerprint, no approved RuleSet and no supporting government rule citations. Such output is transient and is not written into policy assessment history.')

new();h('3.6','Secure PDF Ingestion and Chunking')
fig('3.2','Document-to-policy workflow with a human publication gate','pipeline',300)
add('An active administrator authorizes an exact official source URL associated with the correct scheme. An upload requires source linkage and attestation; a registered download uses the authorized URL rather than accepting an arbitrary target. SHA-256 duplicate detection is per source and content, so new bytes create a new immutable document version without replacing older originals.')
add('The parser preserves page numbers, text blocks, identifiable headings, best-effort table text, bounding boxes and extraction methods. Chunks never cross a page or document and use stable identifiers derived from source identity, offsets, content hash and algorithm version. Image-only or damaged pages are marked incomplete for review.')

new();sub('Acquisition and processing safeguards')
tbl('7','Configured PDF and extraction limits',['Control','Development default','Failure behavior'],[
('Maximum original bytes','10 MiB','Reject oversized upload/download.'),
('Maximum pages','50','Reject unsupported document size.'),
('Maximum extracted text','200000 characters','Bound parser output; record safe failure.'),
('Native parse deadline','25 seconds','Terminate bounded subprocess.'),
('Official download deadline','15 seconds','Timeout; no partial policy publication.'),
('Chunk size / overlap','1800 / 160 characters','Configurable, page-aware partitioning.'),
('Processing deadline','90 seconds','Persist failed job and safe error details.'),
('Local expensive operations','2 concurrent slots','Bound parser / credential work.')],[1.5,1,1.6])
add('Source validation requires HTTPS, an accepted official host, no URL credentials or unusual ports, and an exact authorized URL hash. Every resolved address must be public. TLS connects to the vetted destination while preserving hostname verification. Redirects are rejected and require separate authorization of the final official URL. Request timeouts, byte bounds and disabled implicit proxy use constrain SSRF exposure [12].')
add('File content is checked beyond its extension, including PDF recognition and complete-file structure. User filenames never become storage paths. Originals use source UUID/content-hash keys and private permissions; reads verify the stored checksum. Attachments and scripts are not executed. Native parsing runs outside the event loop with resource limits, but is not a complete kernel sandbox against parser exploits.')
add('A parser or provider error does not erase previous documents or successful jobs. Failed SQL registration may leave an unreferenced private blob; automated orphan reconciliation remains future work. Scanned content is not invented and table extraction is always subject to visual human comparison.')

new();h('3.7','Candidate Extraction and Human Verification')
add('The provider abstraction requests bounded structured candidate responses using the official Google GenAI SDK. Environment settings define the model, timeout, retries and request/input limits. Missing credentials produce an explicit unavailable state. Transient rate limits and timeouts receive bounded exponential backoff; raw provider errors and secrets are not written to logs.')
add('Each candidate carries the scheme and source document, condition identifier, supported field/operator, typed expected value, units, logical context, exclusion/conditional information, source page, excerpt, uncertainty and technical validation status. Candidate expressions map to the existing engine language; no new arbitrary operator or executable expression is accepted.')
sub('Validation and review sequence')
add('Technical checks validate field vocabulary, numeric and date formats, annual INR or percentage units, logical structure, page existence and excerpt location in normalized stored text. Conflicting clauses, missing evidence or incomplete semantics produce findings and remain pending. A candidate marked VALIDATED is technically acceptable for review; it is still not an approved rule.')
add('LangGraph persists stage state and interrupts for a human decision. The reviewer checks every page, resolves exclusions and applicability, provides a complete policy, saves an immutable revision and references its SHA-256 digest in the decision. Effective dates must be evidenced or explicitly labeled administrative activation, never inferred from retrieval time.')
add('Publication rechecks source authorization, original checksum, current administrator activity, the exact revision, all evidence and version overlap. Draft RuleSet, ordered RuleConditions, RuleEvidence, approval metadata and publication ledger commit together. Re-entry returns the existing publication instead of allocating another rule version. Rejection creates no executable policy.')

new();h('3.8','Source-grounded Retrieval and Explanation')
add('The retrieval module stores embeddings for stable document chunks in pgvector. Embeddings are namespaced by provider and model, with the content hash retained to prevent using a vector for changed text. The implemented schema uses 768 dimensions. The MVP performs exact cosine retrieval over a bounded, authorized set rather than introducing a separate vector service.')
add('Before ranking, SQL scope restricts candidates to the requested scheme, applicable approved rule and its exact document version. Pending or unrelated policy material cannot be returned as supporting evidence. A bounded lexical fallback can locate passages when embeddings are unavailable. Local development hash embeddings are marked as such and are disallowed by production configuration.')
sub('Answer contract')
add('Public questions are mapped to fixed document intents. Answers quote located passages and include document ID, checksum, page number, locator, source URL and approved rule reference. Unsupported questions or absent evidence receive an explicit lack-of-evidence response. Applicant profiles and private reports are not sent into this retrieval path.')
add('A deterministic trace and a retrieval response serve different purposes. The trace states which typed conditions pass, fail or remain unknown. Retrieval helps a reader inspect source material relevant to an explanation. Neither a high similarity score nor a fluent answer can create a policy condition, replace evidence validation or turn UNKNOWN into PASS.')
add('The existing isolated demonstration indexed synthetic chunks and retrieved page-level citations. It proves integration and provenance for those fixtures, not broad retrieval accuracy over the real government corpus. The live database has no approved government RuleSet, so source-grounded executable government coverage remains an onboarding and human-review task.')

new();h('3.9','Policy Change Detection and Comparison')
fig('3.3','Approved-source monitoring through reassessment','monitor',315)
add('Administrators opt selected authorized URLs into daily or weekly schedules with access-permission notes and minimum intervals. Celery Beat dispatches durable PostgreSQL jobs; Redis carries their identifiers to bounded workers. ETag and Last-Modified are hints, supplemented by periodic unconditional checksums. An unchanged original does not trigger another model extraction.')
add('Changed bytes create a new DocumentVersion through the existing ingestion service. Normalized text can identify obvious formatting-only changes and avoid a paid call, but cannot prove visual/table equivalence. The source remains inspectable and potentially outdated until the policy situation is resolved.')

new();sub('Structured policy differences')
add('The comparison engine normalizes typed leaves and compares stable condition identifiers together with their logical context. It detects threshold changes, categorical/state/education changes, exclusions, added or removed conditions and altered expression relationships. Missing proposal clauses are inconclusive until a reviewer establishes completeness. Supported deadline and required-document labels may be compared as source facts without inventing executable operators.')
tbl('8','Change classification and activation behavior',['Observation','Classification / action'],[
('Same original checksum','Unchanged; retain version and skip AI processing.'),
('Different bytes, identical normalized text','Potential formatting change; retain original and allow inspection.'),
('Same typed value, different decimal spelling','Normalized equivalence; do not invent a material threshold change.'),
('Evidence-backed income or age threshold differs','Proposed material change requiring human review.'),
('Missing clause / uncertain table or date','Inconclusive; request clarification, keep prior approved version.'),
('Approved exact revision and valid publication','Publish immutable replacement and queue authorized impact processing.')],[1.5,2.5])
add('For example, a <b>fictional test policy</b> changing an income ceiling from INR 250000 to INR 300000 is recorded as a proposed threshold increase with old/new evidence. The numbers are not assigned to any government scheme. Human approval, not the diff classification, activates a new rule.')
add('A failed fetch, unverified document or ambiguous candidate never removes the last approved policy. Currency warnings communicate potential staleness. Public policy-update responses expose only changes linked to verified published rules, while pending proposals stay in the protected administrator workspace.')

new();h('3.10','Reassessment, Notifications and Privacy')
add('When a material policy change is approved, the publication transaction also records a durable reassessment job. The worker rechecks approval, effective date and whether a later publication already supersedes the queued version. Future-effective changes wait until the applicable date in Asia/Kolkata. Rollback publishes neither a policy nor its reassessment request.')
add('The worker identifies affected saved assessments and locks each active citizen account before reading authorized data. It respects reassessment consent and current notification preferences. Necessary fields come from the current encrypted profile; missing or deleted profile data yields UNKNOWN. The original assessment is never modified.')
add('A new encrypted assessment pins the new approved rule, input snapshot and trace, with links to its parent and policy change. The impact record compares condition-level outcomes. Per-account transactions commit the report, event and notification together. Deterministic identifiers, account locks and unique event keys prevent duplicate effects after a crash or redelivery.')
sub('Notification semantics')
add('In-app messages identify verified policy updates, affected prior assessments, changed conditions, new information requirements or deadline changes. Notifications are owner-scoped, readable/unreadable by the recipient only, and preference-aware. Generic titles avoid exposing sensitive profile details; detailed reports require an authorized session. The application does not send email in the current MVP.')
add('Guest recommendation inputs remain in per-tab React memory and are cleared on reload or session changes. Registered citizens explicitly consent to profile persistence through the existing encrypted store. Historical encrypted assessment snapshots are retained for reproducibility unless the account is deleted through the authorized purge process. Encryption protects sensitive payloads, but operators still control database access, key custody and backup retention.')

new(('4','System Design and Implementation'))
h('4.1','Technology Stack')
add('SchemeGuard uses a modular Python backend and a typed React frontend. Dependencies are pinned in the repository. The table records the implementation families rather than claiming compatibility with every future release.')
tbl('9','Implemented technology stack',['Layer','Technologies','Role'],[
('Interface','Next.js 16, React 19, TypeScript, Tailwind CSS 4','Responsive pages, forms and server-side API proxies.'),
('API / validation','Python 3.12, FastAPI, Pydantic, pydantic-settings','Typed routes, dependency injection and environment validation.'),
('Persistence','PostgreSQL 16, SQLAlchemy, asyncpg, Alembic, pgvector','Relational history, async sessions, migrations and vectors.'),
('Document / AI','PyMuPDF, Google GenAI SDK, LangGraph','Bounded parsing, candidates and checkpointed review.'),
('Background work','Celery, Redis, Celery Beat','Durable-job delivery, bounded workers and scheduling.'),
('Security / verification','Argon2id, Fernet, pytest, HTTPX, Vitest, Playwright','Credentials, private payloads and regression coverage.')],[.9,1.8,2.1])

new();h('4.2','Module Description')
add('The repository separates HTTP contracts, application services, repositories, schemas and models. Background tasks call existing services rather than duplicating policy processing or decision logic. The frontend reuses the same backend recommendation contract for guests, the saved-profile endpoint and the dashboard.')
tbl('10','Backend modules and responsibility boundaries',['Module / package','Responsibility'],[
('api/v1 + schemas','Versioned endpoints, request/response validation and authorization dependencies.'),
('models + repositories','Canonical relational entities, scoped queries, version selection and transaction boundaries.'),
('services/recommendations','Catalog relevance, explainable factors, filtering and stable pagination.'),
('eligibility','Typed expression validation, normalization, three-valued evaluation and traces.'),
('assessment','Separate project-authored template loading and explicit assessment basis.'),
('ingestion + ai','Official acquisition, parser/storage/chunks, structured extraction and candidate validation.'),
('agents + rag','Checkpointed graph, review/publication orchestration and approved-source retrieval.'),
('services/monitoring + policy_diff','Opt-in source checks, document comparison and reviewed changes.'),
('workers + services/jobs','Outbox dispatch, leases, retries, locks and durable task execution.'),
('auth + citizen services','Shared role/session infrastructure, encrypted profiles, history and notifications.')],[1.45,2.65])
add('Core services depend on typed schemas and repositories; routes remain thin. PostgreSQL is authoritative for policy approval and job state. The same RuleSet, RuleCondition, RuleEvidence and DocumentVersion concepts are retained across all phases, avoiding a parallel AI policy store.')

new();h('4.3','Individual Contributions')
add('The supplied material identifies Ankesh as the project contact, but does not establish a complete team roster or a verified division of authorship. The report therefore records implemented work packages without assigning unsupported individual credit. Team members should confirm their actual allocations before an assessed submission; the sample report\'s unrelated author names have not been copied.')
tbl('11','Implemented work packages for contribution review',['Work package','Deliverables recorded in the repository'],[
('Backend and database','FastAPI services, SQLAlchemy models, migrations, transactional seeding and typed APIs.'),
('Eligibility and recommendations','Typed rule engine, version-aware selection, relevance scoring, traces and missing-information behavior.'),
('Document intelligence','Official PDF acquisition, extraction, candidate validation, LangGraph review and source-grounded retrieval.'),
('Citizen and administrator interface','Profile-first discovery, responsive reports, protected workspaces and review/monitoring pages.'),
('Automation and security','Celery/Beat/Redis, reassessment, sessions, encryption, audit and deployment guards.'),
('Quality and documentation','PostgreSQL integration tests, browser journeys, evaluation fixtures, recovery drill and phase reports.')],[1.2,2.9])
sub('Development process')
add('The implementation was extended incrementally across seven phases and later profile-first refinements. Each phase preserved existing migrations and records, added focused tests and kept the application runnable through Docker. The later recommendation redesign reused encrypted profiles and strict eligibility rather than replacing either subsystem.')
add('Authorship, supervision and academic approval are institutional facts, not values inferable from code. Signature pages remain unsigned. No project guide name, roll number, institutional logo or degree certification is fabricated from the reference template.')

new();h('4.4','User Interface and Primary Journey')
fig('4.1','Profile-first citizen journey','journey',295)
add('The landing page prioritizes Find My Schemes and does not load a catalog grid. The five-step questionnaire collects optional age/state, education/student/course information, occupation/employment, family income and interests. Users can skip unknown answers. Names, Aadhaar numbers and identity documents are unnecessary for recommendation.')
add('Personalized results show relevance labels, reasons, missing information, category filters and pagination. Scheme details present verified metadata and an official source link before offering a supported assessment. The report groups passed, failed and unknown requirements and explains its policy basis. Users can return to edit details without repeating unrelated questions.')

new();sub('Implemented result cards and responsive presentation')
imagefig('4.2','Cropped desktop recommendation cards from the recorded browser verification','desktop-cards.png')
add('The captured cards show the name, category, department, explanation and assessment availability of real catalog records. The source images are archived UI evidence, cropped to the working content area for print; they are not a new browser execution. Matching reasons are explicit rather than a confidence percentage. The displayed illustrative basis must not be mistaken for an approved government policy.')
new();sub('Mobile card detail')
imagefig('4.3','Mobile recommendation card, cropped from the archived 390-pixel browser view','mobile-card.png',230)
add('Mobile testing recorded no horizontal overflow at a 390-pixel viewport. The same recommendation contract powers both layouts. Captured catalog descriptions and historical UI content may change independently of the report\'s verified snapshot. The measured sample counts in Chapter 5 come from the final stored API responses, not from counting screenshot cards.','small')

new();h('4.5','Frontend State, Routing and Session Boundaries')
add('Next.js App Router pages use reusable questionnaire, scheme-card, report, citizen and administrator components. The DiscoveryProvider stores transient answers and explanations only in per-tab memory. Public POST requests go through a fixed same-origin proxy that does not forward account cookies. Personal inputs are not placed in query strings, localStorage, sessionStorage or browser logs.')
add('The routes /find-schemes and /schemes/recommended form the primary discovery experience. /schemes resolves to the questionnaire or personalized results depending on available input; /schemes/all retains manual search and filters. Existing /eligibility routes and saved reports continue to work. Protected layouts check sessions, and backend authorization remains authoritative.')
sub('Guests and registered citizens')
add('Guests can complete discovery and a supported transient assessment without registration. Reloading clears their answers. Registration may carry in-memory answers to an explicit save-consent step, but does not silently store them. Logged-in citizens securely load only their own encrypted profile, can update details and explicitly save changes. Logout, a new login and account deletion clear transient private state.')
add('The dashboard calls the shared recommendation engine and retains profile completeness, saved assessments, notifications and verified policy updates. It no longer relies on geographic suggestions alone. Recently viewed tracking has not been introduced. Incomplete profiles receive a useful prompt; an empty profile produces no unrelated scheme grid.')
sub('Interface feedback')
add('Forms use accessible labels, bounded inputs, clear validation, back/next controls and unknown answers. Pages include loading, error and empty states. Assessment actions are offered only when the server identifies an approved policy or explicit illustrative template. Unsupported schemes display that detailed criteria are not yet available. No public screen can publish extracted policy candidates.')

new();h('4.6','Database Design and Canonical Relationships')
fig('4.4','Core entity relationships and evidence lineage','erd',335)
add('UUID domain identifiers and timezone-aware timestamps support stable relationships. A scheme has multiple sources; a source has immutable document versions; a rule set references the exact source document for that scheme. Conditions carry typed expression JSONB, and their evidence refers to the same document and page. Composite constraints and provenance triggers reject cross-document or cross-scheme bindings.')
add('Private profile and assessment payloads are encrypted, while relational references support owner-scoped querying and reproducible rule selection. Operational tables track mutable job/session state; historical documents, reviewed revisions, decisions and policy contents are append-only. Database-owner privileges remain outside the application\'s normal protection boundary.')

new();sub('Database table inventory')
tbl('12','Tables grouped by implemented responsibility',['Group','Tables'],[
('Catalog / canonical policy (6)','schemes; scheme_sources; document_versions; rule_sets; rule_conditions; rule_evidence.'),
('Authentication / audit (4)','users; login_sessions; rate_limits; audit_events.'),
('Document processing (8)','source_authorizations; document_assets; document_pages; document_chunks; document_processing_jobs; extracted_rule_candidates; candidate_evidence; extraction_errors.'),
('Workflow / review / retrieval (7)','agent_workflows; workflow_events; policy_reviews; review_revisions; review_decisions; rule_publications; chunk_embeddings.'),
('Monitoring / durable jobs (6)','background_jobs; source_monitoring_config; monitoring_runs; policy_changes; policy_change_details; policy_change_review_events.'),
('Citizen private system (5)','profiles; assessments; reassessment_events; notifications; notification_preferences.'),
('Migration bookkeeping (1)','public.alembic_version.'),
('LangGraph checkpoints (4)','sg_checkpoints.checkpoint_migrations; checkpoints; checkpoint_blobs; checkpoint_writes.')],[1.25,2.85])
add('The recorded database has 41 tables including migration/checkpoint bookkeeping [15]. No separate assessment_conditions table is needed: immutable condition traces and evidence references are stored inside the encrypted saved report, while the exact RuleSet remains relationally linked. Likewise, AI candidates are previews rather than another executable policy representation.')
add('Important constraints include unique scheme slugs, scheme/version uniqueness, deduplicated source document content, stable candidate/page lineage, one active extraction per document, unique publication binding, job deduplication and notification event keys. History triggers prohibit rewriting published content. Indexes support category/state discovery, approved version selection, owner history, unread notifications and dispatch of due jobs.')

new();h('4.7','Incremental Migrations and Data Preservation')
tbl('13','Applied Alembic revisions and their purpose',['Revision','Change introduced'],[
('0001_initial_metadata','Scheme/source/document tables, UUIDs, constraints and immutable document history.'),
('0002_eligibility_rules','Versioned RuleSet, RuleCondition and RuleEvidence; approval/history guards.'),
('0003_ai_ingestion','Shared authentication, source authorization, PDF assets/pages/chunks/jobs/candidates/errors.'),
('0004_least_privilege','Default new-account role changed to citizen; existing administrators retained.'),
('0005_workflow_rag','Review workflow, revisions, decisions, publications, embeddings and pgvector.'),
('0006_graph_checkpoints','Versioned PostgreSQL checkpoint schema owned by Alembic.'),
('0007_workflow_provenance','Cross-entity integrity and immutable workflow/publication bindings.'),
('0008_policy_monitoring','Durable background jobs, source schedules, runs and change history.'),
('0009_citizen_system','Encrypted profiles, assessments, preferences, reassessment and notifications.')],[1.1,3])
add('The recommendation redesign adds optional fields inside the existing encrypted profile JSON and requires no new migration. Older profiles remain valid. The latest recorded Alembic head is 0009_citizen_system with no schema drift. New metadata insertion does not overwrite existing slugs or rewrite their source/rule/document history.')
add('Downgrades are tested only in disposable databases. Routine development and releases use forward migrations, retain database/document volumes and back up the encryption key separately. No volume deletion or database reset is part of the documented user journey.')

new();h('4.8','API Design and Integration')
add('FastAPI provides versioned /api/v1 contracts with Pydantic request and response models. /health reports process liveness; /ready checks PostgreSQL connectivity. UUID parsing, query bounds, controlled error envelopes and request correlation IDs make failures observable without exposing private input. The latest recorded OpenAPI snapshot contains 75 operations [16].')
tbl('14','Representative public and private API contracts',['Method / route','Purpose / boundary'],[
('POST /api/v1/recommendations','Transient profile body, relevance ranking, category filter, stable pagination.'),
('GET /api/v1/recommendations/options','Actual catalog category/interest and state choices.'),
('POST /api/v1/me/recommendations','Citizen\'s own encrypted saved profile; paging options only in body.'),
('GET /api/v1/schemes and /{id}','Catalog search, filters, pagination, details and official sources.'),
('POST /api/v1/eligibility/check','Strict approved-policy evaluation; no approved policy means UNKNOWN.'),
('POST /api/v1/assessment/check','Explicit server-selected approved/illustrative/unsupported basis.'),
('GET /api/v1/profiles/me; PUT; DELETE','Owner-only profile management through shared citizen auth.'),
('POST /api/v1/assessments; GET /{id}','Save/retrieve private approved-policy reports; reproduce route pins history.'),
('GET /api/v1/notifications','Owner notifications, read actions and preferences on related routes.'),
('POST /api/v1/admin/documents','Administrator-only authorized PDF acquisition and immutable version registration.')],[1.65,2.5])
add('The full route inventory is maintained in docs/api.md. Additional administrator groups manage sources, extraction jobs, workflows, review revisions/decisions, indexing, monitors, runs, policy comparisons and audit events. Public policy-updates returns only approved published changes.')

new();sub('Recommendation request and response example')
add('The request below contains <b>synthetic demonstration inputs</b>. Optional values belong in a POST body, never in a personal-data query string. A guest request does not create a profile or saved assessment.')
code('''POST /api/v1/recommendations
{
  "age_years": 21,
  "state": "Assam",
  "course_level": "undergraduate",
  "current_student": true,
  "occupation": "student",
  "annual_family_income_inr": 240000,
  "interests": ["education"],
  "page": 1,
  "page_size": 9,
  "sort_by": "relevance"
}''')
add('The recorded request matched 78 schemes, with Ishan Uday Special Scholarship for the North Eastern Region first. Its explanatory factors include the selected education interest, student occupation/status and verified matching geography. Age and income add no ranking points because there is no approved government policy for this record. Assessment availability refers to a separate illustrative basis, not verified government eligibility.')
code('''{
  "relevance": "HIGH",
  "matching_reasons": [
    "Matches your interest in education",
    "Relevant to your student status"
  ],
  "approved_rule_version": null,
  "assessment_mode": "ILLUSTRATIVE"
}''')
add('This is an abbreviated shape; actual responses also retain scheme ID, source URL, description, category, missing information and ranking factors. Page size is limited to 30; interests to 24 and free course text to 80 characters. The proxy bounds JSON requests to 16 KB and responses use no-store.')

new();h('4.9','Authentication, Authorization and Private Data')
add('Citizens and administrators share users, login_sessions, rate_limits and audit_events. Registration always creates a citizen and rejects injected role fields. Administrators are provisioned through an interactive operator command; there is no public admin-registration endpoint. Every private or administrative API checks the active account and required role independently of the frontend.')
add('Passwords use Argon2id with bounded hashing slots. Random opaque session tokens are sent in HttpOnly, SameSite=Strict cookies; only token digests are stored. Production enables Secure cookies. Sessions expire, logout revokes the current token and password changes revoke all sessions. Current-password confirmation protects account changes and deletion. Exact allowed Origin checks and CSRF tokens protect authenticated mutations.')
sub('Owner isolation and encryption')
add('Every private query is scoped to the authenticated owner. Profiles, minimal saved inputs, complete assessment traces and reassessment impacts use authenticated Fernet encryption with owner/purpose binding. Swapped, corrupted or wrong-key payloads fail closed. This is application payload encryption, not whole-database encryption: scheme links, account IDs and overall assessment results remain relational metadata.')
add('PROFILE_ENCRYPTION_KEY must remain stable and be shared privately by API and worker. It is not exposed to the frontend or placed in Git. Key rotation requires a deliberate decrypt/re-encrypt migration; simply replacing the key loses access to existing private payloads. Database backups and the separately protected key are both necessary for recovery.')
add('Account deletion purges private profiles, reports, impacts, preferences and notifications, revokes sessions and anonymizes/disables the retained account reference. Policy history and audit integrity remain intact. Profile deletion alone preserves saved historical snapshots for replay. Backup retention/erasure remains an operator responsibility. Email recovery, MFA and verified identity proofing are outside the current implementation.')

new();h('4.10','Application and AI Security Controls')
tbl('15','Threats, implemented controls and residual limits',['Threat','Implemented control','Residual limit'],[
('Cross-user access','Role and owner checks in backend queries; private no-store routes.','A privileged DB operator remains trusted.'),
('Session / CSRF abuse','Hashed revocable sessions, exact Origin, CSRF token, Strict/HttpOnly cookies.','Trusted-edge configuration and MFA remain deployment work.'),
('SSRF / unsafe fetch','Exact official URL authorization, public-IP checks, TLS pinning, no redirects.','Official reachability varies by network.'),
('Malicious PDF','Actual content, size/page/output limits and resource-bounded subprocess.','Not a complete OS sandbox for native parser exploits.'),
('Prompt injection / false rules','Untrusted text, bounded schemas, located evidence and human publication gate.','Reviewers must still resolve semantic ambiguity.'),
('XSS / secret leakage','Escaped text, fixed proxies, production nonce CSP and sanitized logs.','No formal penetration-test certification.'),
('Task duplication / replay','Durable job IDs, locks, leases, terminal checks and uniqueness.','Finite retry exhaustion requires operator intervention.'),
('Historical tampering','Immutable versions, provenance FKs/triggers, revision digests.','Migration owner can bypass database guards.')],[.9,1.9,1.5])
add('Request bodies, pagination, expression complexity and costly operations are bounded. SQLAlchemy queries use parameter binding. Request logs retain route, timing, status and correlation ID rather than decrypted applicant inputs or provider keys. Broker tasks contain identifiers only; documents and citizen data are retrieved under service authorization.')
add('The recorded dependency audit reported no known advisories for the checked lockfiles at that time, with no ignore list [19]. This is a dated advisory result, not proof against unknown vulnerabilities or an OS-image scan. Base images, native PDF libraries and SDKs require continued patching and renewed audits before release.')

new();h('4.11','Background Job Reliability and Monitoring')
add('The backend image serves API, worker and scheduler as separate processes. PostgreSQL background_jobs is the durable job/outbox authority. Celery uses Redis for JSON-only delivery of job UUIDs. Dispatcher replay can resend a task after a crash; the consumer\'s database lock, row claim, lease and terminal-state check prevent duplicate business effects. This complements Celery\'s idempotency guidance [13].')
add('The configured worker concurrency is two, prefetch is one, acknowledgements are late and children recycle after 50 jobs. Soft/hard limits are 420/480 seconds; the durable lease is 600 seconds and broker visibility timeout 900 seconds. Warm shutdown has a nine-minute grace period. Retries are bounded and exponentially delayed rather than infinite.')
sub('Scheduling and failure recovery')
add('Beat dispatches due schedules/outbox work every 30 seconds. A process-lifetime PostgreSQL advisory lock permits one logical scheduler leader. Loss of that connection stops leadership. Per-source daily/weekly UTC schedules and minimum intervals live in PostgreSQL, so changes do not require hardcoded Beat entries.')
add('Transient fetch and provider failures retain durable status and safe error codes. Unsafe destinations and malformed content fail without repeated external access. Expired jobs can be dispatched again, but an active execution lock prevents concurrent processing. A broker outage leaves outbox records available for later delivery. Terminal failures remain visible for investigation.')
add('Monitoring reuses the same secure fetcher, parser, document storage, LangGraph graph and review workflow. A document change does not directly approve policy. Verification failure retains the last approved version and raises a currency warning. Workers do not hot reload backend code; operators restart them after changes while preserving volumes and queued job history.')

new();h('4.12','Docker, Deployment and Observability')
fig('4.5','Production topology and private data services','deploy',310)
add('The six-service development configuration is retained. Frontend and API bind loopback ports 3000 and 8000, with database and Redis internal. Named volumes preserve PostgreSQL, originals and broker data. API/frontend hot reload supports development. Production configuration uses separate image targets and Next.js standalone output, non-root application users, health checks, restart/resource/log settings and restricted container permissions.')
add('Production requires a real HTTPS edge, exact frontend origins, stable private keys and reviewed storage/network configuration. The S3 adapter supports private content-addressed originals, but live bucket/IAM connectivity has not been verified. Local production-profile checks used an isolated stack and trusted test certificate; no cloud deployment is claimed.')

new();sub('Service operation and local run commands')
tbl('16','Docker services and durable responsibilities',['Service','Function','Readiness / persistence'],[
('frontend','Next.js UI and same-origin proxies.','HTTP health; source/dependency volumes in development.'),
('api','FastAPI, shared services and protected contracts.','/ready checks PostgreSQL; persistent document access.'),
('db','PostgreSQL 16 + pgvector.','pg_isready; named PostgreSQL volume.'),
('redis','Private Celery broker.','Redis health; broker persistence; no host port.'),
('worker','Bounded document/monitor/comparison/reassessment jobs.','Worker liveness and durable PostgreSQL job states.'),
('scheduler','Singleton Beat dispatcher.','Recent heartbeat and PostgreSQL leader lock.')],[.75,1.55,2.1])
code('''# Repository root; keep an existing .env and its keys.
python3 scripts/init_env.py
docker compose up --build -d --wait --wait-timeout 120
docker compose exec api alembic upgrade head
docker compose exec api python -m app.seed
docker compose ps
# Provision an administrator with a hidden password prompt:
docker compose exec api python -m app.auth.provision \
  --username reviewer''')
add('Open the frontend at http://localhost:3000 and API documentation at http://localhost:8000/docs. The government metadata seed is insert-only and repeatable. Demonstration policy seeding is a separate local-development action and must not be treated as government policy onboarding. Never remove persistent volumes to fix an application problem.')
add('Structured logs carry safe request correlation IDs; health/readiness, workflow events, monitoring history, background job failures and audit records provide operational visibility. Logs omit secrets and applicant payloads. GitHub Actions defines lint, type, backend/frontend tests, builds and security checks, but does not automatically deploy production.')

new();h('4.13','Backup, Recovery and Release Procedure')
add('A complete recovery set includes PostgreSQL public and checkpoint schemas, every referenced original document and the separately retained profile encryption key. Docker volumes provide persistence, not an independent backup. Restricted encrypted backups and explicit retention policies are required. Redis is recoverable delivery state because PostgreSQL retains authoritative jobs.')
add('The repository recovery drill restored a snapshot into a newly generated non-production database, compared table row hashes, verified original PDF checksums and decrypted private sample profiles using the retained key. It did not restore over the working database. A cloud regional failover or managed-storage recovery has not been demonstrated.')
sub('Release sequence')
add('Build immutable reviewed images; execute regression/security checks; back up database, originals and key; validate exact origins and secrets; run one owner-only Alembic upgrade; grant the runtime role only required privileges; start services; verify readiness, sessions, rule history and worker delivery. Enable each source monitor only after access and policy review.')
add('The runtime database role is separate from the migration owner and cannot create schemas, roles or databases. API replicas do not race migrations in the production configuration. A rollback must first confirm schema/job compatibility with the prior image. Prefer a forward corrective migration; do not reverse a publication or rewrite saved reports merely to make an old release start.')
sub('Deployment status')
add('Production Docker images and a local HTTPS production profile were verified in the recorded Phase 7 run. The optional Vercel frontend path is documented but unexecuted. Real DNS/certificates, cloud IAM/storage, managed PostgreSQL/Redis connectivity, secret-manager custody and a reviewed retention policy remain deployment responsibilities. No live cloud resource was created or modified for the report.')

new(('5','Results and Discussion'))
h('5.1','Experimental Setup')
add('The evaluation uses stored repository verification records rather than a new execution during report preparation. The latest profile-first regression snapshot is dated 14 November 2026 [16]. Backend integration tests use disposable real PostgreSQL databases; frontend tests use Vitest and Testing Library; browser journeys use the project-pinned Playwright runner with isolated installed Chrome.')
add('External government responses and Gemini output are deterministic fixtures in automated AI/monitoring tests. Synthetic citizen profiles and clearly identified fictional policy changes avoid claiming government approval. The A/B/C demonstration executes the actual application services in a disposable database. Human review is simulated against an exact saved revision, not performed by an official authority.')
add('Performance data is local sequential HTTP timing, with warmup excluded and 20 samples per endpoint [18]. Workflow timings are one isolated smoke run, not a load benchmark. No real-model extraction accuracy, independent reviewer agreement, cloud capacity or production SLA is inferred from these tests.')

new();h('5.2','Automated Test Results')
tbl('17','Latest recorded regression and static verification',['Check','Recorded result','Scope'],[
('Backend PostgreSQL regression','491 passed; 66.61 s','Migrations, engine, API, AI guards, review, monitoring, auth, private data and recommendations.'),
('Frontend unit/component','84 passed in 13 files; 2.33 s','Forms, result cards, profile/session, admin and error states.'),
('Full browser regression','9 passed; 35.7 s','Citizen and guest flows, historical reports, manual discovery and authorization.'),
('Final desktop/mobile rerun','4 passed; 22.8 s','Profile-first journeys at 1280 and 390 pixels.'),
('Python / frontend checks','Passed','Ruff; strict mypy for 109 modules; TypeScript; frontend formatting lint.'),
('Migration drift','None recorded','Head 0009_citizen_system; no redesign migration required.'),
('Development / production images','Built','Six development services recorded healthy; production build is not deployment.')],[1.2,1.3,2])
add('The 33 new backend recommendation cases cover category/occupation/student signals, optional income, incomplete inputs, multiple interests, verified and unknown geography, duplicates, ranking, paging, empty results, approved-condition precedence and separation from illustrative thresholds. Guest requests do not write profiles or assessments. Authenticated saved-profile tests verify ownership and CSRF.')
add('Existing regression coverage remains in place for typed comparisons, nested logic, malformed PDFs, unsafe sources, evidence validation, workflow replay, human approval/rejection, policy versions, sessions, cross-user isolation, reassessment and notification deduplication. These are recorded passing runs, not a claim that every possible real-world policy was tested.')

new();sub('Browser journey and privacy observations')
add('The full primary journey was recorded from the homepage through the optional questionnaire to PostgreSQL-backed recommendations, scheme details, a prefilled supported assessment, report and edit-details return. A citizen run verified saved-profile prefill, explicit encrypted saving, dashboard reuse and logout clearing. Manual browsing, unsupported assessment states and historical report replay remained available.')
add('Browser checks used 1280-pixel desktop and 390-pixel mobile viewports. The final guest run observed zero runtime page errors and zero browser-storage entries. Mobile layout checks found no horizontal overflow in the exercised journey. These are scoped observations, not full assistive-technology certification or every-browser coverage.')
sub('Test environment constraints')
add('The container browser installation encountered mirror/DNS limitations, so the executed local runs used the pinned runner with an isolated installed Chrome. Repeated registration testing reached the existing five-per-hour live throttle. It was preserved rather than disabled. Final repeated citizen checks used a separate temporary QA stack and database; cleanup removed only generated test data through authorized application behavior.')
add('The recorded persistent application remained at 283 schemes, two document versions and the original policy history. Closed generated QA account tombstones were retained by the account deletion design. Such tombstones are audit references, not active citizens. The report avoids presenting mutable personal account counts as a project achievement.')
sub('Interpretation')
add('The browser results substantiate end-to-end wiring and the tested privacy boundaries. They do not prove that all catalog descriptions are current, that a government department will accept an application, or that real model output will always be correct. Those questions require separate policy review and model evaluation.')

new();h('5.3','Recommendation Samples and Ranking Behavior')
tbl('18','Recorded profile-first API sample outcomes',['Synthetic input','Matched count','Top recorded result / interpretation'],[
('Age 21, Assam, undergraduate student, income INR 240000, education interest','78','Ishan Uday Special Scholarship for the North Eastern Region; metadata relevance, not verified eligibility.'),
('Assam and agriculture interest; other inputs unknown','21','Agri Clinics and Agri Business Centres ACABC; interest-based relevance.'),
('Unemployed and employment interest','12','Capacity Building for Service Providers; employment/skills relevance.'),
('All details unknown','0','Useful request for interests or profile details; no unrelated catalog grid.')],[1.65,.5,2.3])
add('The student example receives 108 points from the interest, occupation/student and verified geography factors. Age and income contribute zero because no approved government rule exists for the scheme. Missing scheme-specific eligibility conditions remain visible. This demonstrates why relevance and eligibility must not share a label.')
add('The agriculture example confirms that an interest can produce useful discovery without requiring financial or demographic details. The empty-profile case confirms that an unknown profile is not treated as a universal match. State coverage that is unverified remains discoverable, whereas verified incompatibility is filtered explicitly.')
add('These results are captured in profile-first-recommendations-samples.json [16]. They reflect a particular static catalog and input set, not a universal recommendation-quality score. The ranking heuristic has not been validated against independently labeled citizen preferences or real application outcomes. Category metadata may also include institution-oriented programmes; users must inspect official guidance.')

new();h('5.4','End-to-end Policy Workflow Demonstration')
tbl('19','Isolated synthetic A/B/C integration results',['Workflow','Recorded result','Evidence preserved'],[
('A: document -> extraction -> review -> publication','PASS using PDF and mocked AI; exact-revision human decision simulated.','Original PDF, chunks, candidate evidence, saved review and published version.'),
('B: profile -> discovery -> strict evaluation -> save','PASS in disposable PostgreSQL.','Owner-linked encrypted minimal input, typed trace and original RuleSet.'),
('C: changed PDF -> diff -> new approval -> reassessment','PASS; one deduplicated notification.','Both documents, both approved fixture versions, parent report and impact lineage.')],[1.4,1.55,1.7])
add('The run preserved two synthetic document versions and two approved fixture rule versions. It confirmed that publication can append new history, the original assessment can still be replayed and duplicate task delivery does not produce duplicate notifications. The database and private fixture data were disposable and rolled back [17].')
sub('Real official-document demonstration')
add('The repository also preserves a historical official Saksham PDF obtained from the National Scholarship Portal. Its previously verified SHA-256 is 06ebed9e50a47ae76cba985ddde78cd65f19f2193b0e4c9c164fff529580474c. Four pages and 26 chunks were recorded, and the original bytes were rechecked in the recovery drill [15].')
add('That document remains pending genuine human policy review and current-guideline reconciliation. It has not produced an approved government RuleSet. A live Gemini run was unavailable in the recorded verification. Therefore the demonstration proves real PDF preservation/parsing and fixture-backed pipeline integration, while live extraction quality and current policy publication remain unverified.')

new();h('5.5','Performance Measurements')
tbl('20','Recorded local sequential API latency in milliseconds',['Endpoint / operation','Samples','Median','p95','Maximum'],[
('Health','20','2.009','2.165','2.299'),
('Database readiness','20','4.742','5.267','5.318'),
('Scheme search','20','16.924','18.789','20.787'),
('Deterministic assessment','20','18.025','19.777','19.846')],[1.8,.6,.7,.7,.8])
add('The measurements used local development Docker services and one sequential client after warmup [18]. They establish responsive behavior for the tested small catalog, not high-concurrency capacity or a service-level objective. Hardware characteristics were not recorded as a controlled benchmark configuration, so cross-machine comparisons would be inappropriate.')
sub('Observed query plan')
add('EXPLAIN ANALYZE recorded a scholarship-name search using a sequential scan followed by a top-N sort. The database query execution was approximately 0.646 ms at the 283-record scale. This is not an observed bottleneck requiring a speculative index. Category/state, approved-version, owner-history, unread-notification and dispatch indexes were reviewed against actual access paths.')
sub('Single-run pipeline timings')
add('The isolated demonstration recorded PDF processing at 426.927 ms, RAG retrieval at 37.561 ms, evaluation-and-save at 39.084 ms, and combined monitor/parse/graph/compare/review at 1255.566 ms. Reassessment was 39.895 ms. Each is one smoke sample, not a percentile or capacity measurement.')
add('Mock extraction took 0.058 ms because no model/network request occurred. It is deliberately excluded from any claim about Gemini speed. Real Gemini, S3, public-government-network latency and heavy PDF concurrency remain unmeasured. Future optimization should be driven by production-like load traces rather than extrapolation from these local samples.')

new();h('5.6','AI Reliability and Decision Evaluation')
add('A small manually inspected, project-authored reference dataset contains three fictional clauses and 11 boundary/missing-input profiles [17]. The conditions cover an age minimum, an annual income ceiling and a disability-percentage boundary. These values test the engine and evidence guards; they are not government rules. Gold fixture validation is not a measurement of model extraction accuracy.')
tbl('21','Measured fixture evaluation counts and unavailable metrics',['Metric','Actual result','Interpretation'],[
('Located evidence excerpts','3 / 3 located','Source-location checks on three authored clauses.'),
('Deterministic decisions','11 / 11 correct','Expected boundary and missing-input outcomes.'),
('False positive eligibility','0 false PASS among 6 negative cases','Small fixture guard check, not population error rate.'),
('Missing information','3 / 3 correct','Absent/null fields retained UNKNOWN.'),
('Material change detection','3 true positives; 0 false positives; 0 false negatives','Precision and recall both 1.0 on this small authored comparison set only.'),
('Live Gemini extraction accuracy','Not measured','No real-model evaluation run available.'),
('Independent human-review agreement','Not measured','No independent annotated reviewer dataset available.')],[1.2,1.25,1.9])
add('These counts support the correctness of the tested deterministic and evidence checks. They do not justify a claim of 100% government-policy understanding or universal hallucination resistance. The input set is tiny, hand-authored and not representative of diverse languages, complex exceptions, scanned tables or conflicting departmental amendments.')
add('A future real-model evaluation must use authorized source PDFs, independently annotated complete policies, held-out documents and disagreement analysis. Extraction correctness, evidence correctness, decision correctness and reviewer agreement should be measured separately. No model accuracy percentage is invented in this report.')

new();h('5.7','Security, Persistence and Recovery Results')
add('The Phase 7 record contains a local HTTPS production-profile smoke test: Secure/HttpOnly cookies, exact CSRF/origin checks, citizen ownership, admin denial and production script nonces were exercised. A runtime database role was verified without superuser, create-database or create-role privileges, and schema DDL was denied. The production worker probe crossed PostgreSQL outbox, singleton Beat, Redis and Celery once; duplicate delivery was skipped [19].')
add('The dependency audit checked 85 pinned Python runtime packages and reported zero known advisories; npm audit reported zero vulnerabilities at that recorded point. Thirty-five browser JavaScript artifacts were scanned for backend-only secret-variable references. These results are dated scope-specific checks, not a current penetration-test certificate or proof against unknown vulnerabilities.')
sub('Recovery drill')
add('The isolated restore recovered 41 tables and 757 snapshot rows into a UUID-named non-production database. Row hashes matched, original PDF checksums were verified and private profiles decrypted with the separately retained key. Only the generated recovery database was removed. This demonstrates the documented local snapshot procedure, not managed-cloud failover or a guaranteed recovery time.')
add('Container recreation checks preserved original documents and public/checkpoint row hashes. The profile-first redesign required no schema migration and retained scheme, source, approved rule and document counts. These checks support data continuity across the tested changes. Backup scheduling, retention, operator access and off-site disaster recovery remain deployment responsibilities.')
sub('CI and deployment boundary')
add('GitHub Actions configuration exists for Python/frontend lint, types, tests, production builds, dependency checks and integration verification. The recorded checks were executed locally; a remote GitHub workflow run and production deployment were not performed. No production credentials are committed and no automatic deployment job is configured.')

new();h('5.8','Discussion and Acceptance Status')
tbl('22','Completed, demonstrated and unverified functionality',['Area','Status','Practical meaning'],[
('Profile-first discovery','Implemented and regression-tested','282 government metadata records power explainable results.'),
('Strict eligibility engine','Implemented and fixture-tested','Only approved applicable policies execute; government coverage is currently zero.'),
('Official PDF preservation','Real historical PDF processed','Four pages/26 chunks preserved; policy review pending.'),
('Gemini / LangGraph pipeline','Implemented; mocked extraction demonstrated','Live Gemini quality unavailable; approval gate and replay tested.'),
('RAG / review / publication','Fixture integration verified','Approved-version-scoped citations; no broad real-policy benchmark.'),
('Monitoring / reassessment / notifications','Fixture-tested plus real broker probe','No live official sources enrolled in recorded working database.'),
('Docker / security / recovery','Local verification recorded','Production profile tested locally, with no live cloud deployment.'),
('Operational release','Partially prepared','Real credentials, policy onboarding, load tests and cloud controls remain.')],[1.15,1.25,1.95])
add('The strongest contribution is the controlled connection between modules: recommendations remain separate from policy decisions; AI output stays pending; approved versions retain page evidence; changes append history; saved reports reproduce against their original rule; and task retries cannot silently duplicate effects.')
add('The largest limitation is policy coverage rather than interface breadth. A broad metadata catalog improves discovery but cannot substitute for complete reviewed conditions. The next improvement should prioritize a small, carefully reconciled set of genuine approved policies and independent extraction evaluation before scaling automated processing or claiming real-world benefit outcomes.')

new(('6','Conclusion and Future Work'))
h('6.1','Conclusion')
add('SchemeGuard implements an integrated academic system for personalized government scheme discovery, evidence-preserving document processing, deterministic eligibility evaluation and reviewed policy change management. It shifts the primary experience from searching a large catalog to providing optional profile information and receiving explainable recommendations.')
add('The architecture keeps three distinct concepts explicit: metadata relevance, project-authored illustrative assessments and human-approved policy execution. The rule engine preserves PASS/FAIL/UNKNOWN semantics, evidence and version-aware reproducibility. Gemini proposes candidates, LangGraph coordinates verification and review, and Celery-based monitoring/reassessment preserves historical originals and reports.')
add('The latest recorded suite passed 491 backend tests, 84 frontend tests and nine browser tests. The catalog contains 282 government discovery records; no government rule set is yet approved. Synthetic workflows demonstrate complete publication, historical replay, change comparison and deduplicated impact notification. These results establish an implemented and tested engineering foundation without claiming official eligibility authority, live model accuracy or production deployment.')

new();h('6.2','Future Work')
sub('Policy coverage and independent evaluation')
add('Onboard a small set of current official policies with complete page-level evidence, reconciled amendments and genuine reviewer approval. Build an independently annotated, held-out document dataset to measure extraction completeness, citation correctness, false-positive decisions and reviewer agreement. Include complex exceptions, tables and multilingual text before expanding claimed coverage.')
sub('Document and monitoring robustness')
add('Add carefully scoped OCR for selected image-only documents, stronger parser isolation and orphan-blob reconciliation. Evaluate larger PDF collections and realistic network failures. Extend monitoring only to explicitly permitted sources, and add an operator dashboard for exhausted jobs, source-access changes and uncertain policy comparisons.')
sub('Privacy and citizen support')
add('Implement a reviewed retention policy and encryption-key rotation procedure. Add MFA and password recovery only with a verified delivery mechanism. Conduct accessibility testing with assistive technologies and evaluate local-language explanations. Any email notifications must be consent-based and avoid sensitive content.')
sub('Deployment and scale')
add('Verify real HTTPS/cloud storage/IAM, managed database and broker connectivity, off-site backups and restore exercises. Measure realistic concurrent API, parser and reassessment workloads before introducing batch loading, sharding or approximate vector indexes. Preserve explicit publication review and historical replay under every optimization.')
add('Future work should deepen verified policy support and operational confidence rather than turning model fluency or catalog size into an unsupported eligibility claim.')

# References follow the six chapters, as in the supplied report format.
new();pages[-1].chapter='References';pages[-1].number='';h('','References')
headings[-1]=(0,'References',len(pages))
refs=[
('[1]','Ministry of Electronics and Information Technology, Government of India. "myScheme." Digital India initiative.','https://www.digitalindia.gov.in/initiative/myscheme/'),
('[2]','Direct Benefit Transfer Mission, Government of India. "Central Scheme List." DBT Bharat. Catalog provenance source; source review recorded 12 November 2026.','https://dbtbharat.gov.in/central-scheme/list'),
('[3]','Government of Goa. "Schemes." Official state government directory. Catalog provenance source; source review recorded 12 November 2026.','https://www.goa.gov.in/government/schemes/'),
('[4]','Government of India. National Scholarship Portal. Official scholarship information and historical scheme guideline source.','https://scholarships.gov.in/'),
('[5]','P. Lewis et al. "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks." Advances in Neural Information Processing Systems 33, 2020.','https://arxiv.org/abs/2005.11401'),
('[6]','S. Yao, J. Zhao, D. Yu, N. Du, I. Shafran, K. Narasimhan and Y. Cao. "ReAct: Synergizing Reasoning and Acting in Language Models." ICLR, 2023; arXiv preprint 2022.','https://arxiv.org/abs/2210.03629'),
('[7]','LangChain. LangGraph documentation: interrupts and persistence. Primary implementation reference. Accessed 14 November 2026.','https://docs.langchain.com/oss/python/langgraph/interrupts')]
for label,text,url in refs:add(f'{label} {esc(text)}<br/><link href="{url}" color="#245443">{esc(url)}</link>','ref')

new();pages[-1].chapter='References';pages[-1].number=''
refs2=[
('[8]','Google. "Structured outputs." Gemini API, Google AI for Developers. Accessed 14 November 2026.','https://ai.google.dev/gemini-api/docs/structured-output'),
('[9]','Artifex Software. "Text." PyMuPDF documentation. Accessed 14 November 2026.','https://pymupdf.readthedocs.io/en/latest/recipes-text.html'),
('[10]','Object Management Group. Decision Model and Notation, version 1.5. Formal specification, 2024.','https://www.omg.org/spec/DMN/1.5/About-DMN'),
('[11]','L. Moreau and P. Missier, editors. PROV-DM: The PROV Data Model. W3C Recommendation, 30 April 2013.','https://www.w3.org/TR/prov-dm/'),
('[12]','OWASP Foundation. "Server Side Request Forgery Prevention Cheat Sheet." OWASP Cheat Sheet Series. Accessed 14 November 2026.','https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html'),
('[13]','Celery Project. "Tasks" and periodic-task documentation. Primary references for acknowledgment, retries and scheduling. Accessed 14 November 2026.','https://docs.celeryq.dev/en/stable/userguide/tasks.html')]
for label,text,url in refs2:add(f'{label} {esc(text)}<br/><link href="{url}" color="#245443">{esc(url)}</link>','ref')
add('The cited methods and specifications provide context and implementation guidance. SchemeGuard does not claim DMN/PROV certification or reproduction of RAG/ReAct research benchmarks. Government-source citations establish catalog provenance only to the extent stated in the dataset review.','small')

new();pages[-1].chapter='References';pages[-1].number=''
add('Repository implementation and verification records','h1')
add('The following are project artifacts, not independent publications. Their recorded results are distinguished from new executions and from external policy authority. Repository: <link href="https://github.com/ankesh15/SchemeGuard-AI" color="#245443">https://github.com/ankesh15/SchemeGuard-AI</link>.','small')
for label,text in [
('[14]','SchemeGuard repository. docs/datasets.md; backend/app/schemas/seed.py; data/schemes/*.json. Static catalog organization, source review, deduplication and transactional import.'),
('[15]','SchemeGuard repository. docs/verification/project-facts.json; official-document.json. Recorded catalog/rule/document counts, database table inventory and historical official PDF status.'),
('[16]','SchemeGuard repository. docs/profile-first-recommendations.md; docs/verification/profile-first-verification.json; profile-first-recommendations-samples.json. Latest recorded user journey, API samples and regression snapshot, 14 November 2026.'),
('[17]','SchemeGuard repository. docs/verification/demonstration.json; evaluation.json; data/evaluation/phase7.json. Isolated synthetic A/B/C workflows and gold-reference guard/decision evaluation.'),
('[18]','SchemeGuard repository. docs/verification/performance.json. Local sequential endpoint samples and PostgreSQL query-plan observations.'),
('[19]','SchemeGuard repository. docs/testing.md; docs/security.md; docs/verification/production.json, production-worker.json, runtime-role.json, recovery.json, dependency-security.json and frontend-bundle.json. Recorded production-profile, security and recovery checks.')]:add(label+' '+esc(text),'ref')
add('Reproducibility note: Paths are relative to the project repository. The report\'s source package records the document-generation checks separately. Mutable working-database account counts are intentionally not treated as final project metrics.','small')

new(('A','Plagiarism and AI-Content Reports'))
add('No institutional plagiarism/similarity report or guide-issued AI-content report was supplied for this document. Consequently, no similarity index, detector score or compliance certificate is claimed. Such reports must be obtained through the institute\'s authorized process and attached by the submitting authors before final approval.')
add('The reference format includes this appendix. It is retained here as an honest status record rather than filled with a fabricated result. The source template\'s example threshold is not asserted as a verified requirement of the authors\' institute.')
sub('Tool-assistance disclosure')
add('AI assistance was used to organize and draft the report from the supplied reference format and repository records. Programmatic PDF layout and rendering checks were used for formatting. Authors remain responsible for reviewing every technical statement, confirming authorship and supervision details, citing external sources and meeting their institute\'s academic integrity policy.')

new(('B','Biographical sketch'))
sub('Ankesh')
add('Ankesh is the project contact identified in the supplied development context for SchemeGuard. The project concerns government scheme discovery, typed eligibility evaluation, document intelligence and policy change management in a full-stack web application.')
add('A verified full author roster, roll numbers, institute, supervisor details, email addresses and educational biography were not provided at report preparation. These personal and institutional facts have therefore not been copied from the unrelated sample report or inferred from a repository username. No CGPA, schooling history or contribution allocation is invented.')
add('This appendix records the available information only. Institutional submission pages require confirmation by the authors and authorized signatories. The editable submission metadata file accompanies the report so confirmed details can be incorporated without rewriting the technical chapters.')
