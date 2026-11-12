# Gemini structured candidate extraction

Phase 3 uses the [official Google GenAI Python SDK](https://googleapis.github.io/python-genai/) (`google-genai==3.2.0`) with [Gemini structured output](https://ai.google.dev/gemini-api/docs/structured-output). Dependencies are pinned in `pyproject.toml` and both hash-locked requirements files. The model is configured through environment variables; the default `gemini-3.6-flash` was checked against the official [model catalog](https://ai.google.dev/gemini-api/docs/models). Availability and account quotas must be verified with your own project.

```dotenv
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.6-flash
GEMINI_TIMEOUT=20
GEMINI_MAX_RETRIES=2
GEMINI_MAX_REQUESTS=6
GEMINI_MAX_INPUT_CHARS=20000
```

Set the key in ignored `.env`, then recreate the API service to apply it:

```bash
docker compose up -d --force-recreate api
```

Never prefix a key with `NEXT_PUBLIC_`, send it to Next.js, include it in URLs, or commit it. The workspace exposes only whether credentials are configured, never their value. No live key was available during Phase 3 verification; the real API path was tested for missing credentials and all provider behavior was tested with mocks.

## Provider boundary

`LLMProvider` defines async structured extraction. `GeminiProvider` uses `Client.aio.models.generate_content`, JSON response MIME type, and `CandidateBatch.model_json_schema()`. Automatic function calling, tools and automatic response continuation are disabled. The system prompt treats document text as untrusted data, requires exact excerpts, and prohibits invented policy, decisions and publication. Prompt wording is defense in depth: the real trust boundary is validation plus pending-only storage and isolation from executable rules.

The SDK transport retries are set to one attempt; the adapter owns bounded exponential backoff for timeouts, HTTP 429 and selected 5xx failures. Default backoffs are 0.5 and 1 second for two retries. Each attempt has an async timeout; the complete processing job has an outer deadline. Invalid/empty/oversized structured responses are rejected without retries. Responses are bounded to 200,000 characters/8,000 configured output tokens; requests are capped by input text and batch count. Maximum extraction calls are `GEMINI_MAX_REQUESTS × (1 + GEMINI_MAX_RETRIES)`, bounded further by the job deadline. Logs contain safe exception classes/codes only.

Source context contains the scheme ID, exact document version, page count, batch number and page/section/chunk text. It contains no applicant profiles, session cookies or other application credentials. Only official public policy content should be supplied. The persisted job input manifest identifies the exact stored chunks selected for provider extraction, including attempted extraction when the provider subsequently fails. This is an input manifest, not proof of successful network transmission. Budget omissions and truncation are recorded for manual review.

## Candidate contract and engine mapping

The model returns one bounded `CandidateBatch` with matching scheme/document UUIDs, an AND/OR/unspecified relationship, candidate conditions and limitations. Each condition contains a stable identifier, label, a flat node graph, source-page/excerpt references and extraction uncertainties. Nodes contain a kind, field, supported operator, expected typed value, units and logical references. Flat nodes avoid an unbounded recursive provider schema; they map into the **existing** engine expression schema.

Supported operators remain `==`, `!=`, `>`, `<`, `>=`, `<=`, `IN`, `NOT IN`. AND/OR groups, exclusions and IF/THEN/optional ELSE map to existing typed engine nodes. No eval/exec, new operator or model eligibility decision is used. The human-maintained field vocabulary covers age, annual INR income, disability percentage, gender, category, state, course level, study mode, enrollment date and receipt of other scholarship support. This is vocabulary only; it contains no government thresholds.

Pydantic rejects extra keys, invalid types/operators, excessive output and non-finite numbers. Graph validation rejects cycles, repeated/unreachable nodes, unsupported fields, missing literals, malformed logic, invalid dates and mismatched units. Unsupported interpretations remain pending with issues. Grounding requires located source pages and normalized verbatim excerpts for every comparison. Numeric thresholds must occur in their excerpts; annual currency needs explicit currency/annual language, and date normalization must match a recognized explicit calendar representation. Boolean semantics require manual review. These conservative checks do not prove legal correctness or fully understand a policy.

Simple contradictions in mandatory AND conditions (incompatible equalities, membership or number/date bounds) are flagged CONFLICT. OR alternatives and conditional/exclusion branches are not assumed jointly mandatory. Per-batch AND/OR scope is preserved; relationships across separate batches remain unspecified and require review. This is not a general theorem prover: indirect multi-clause conflicts and policy precedence still need human review. An unspecified relationship, provider limitation or ambiguity produces NEEDS_REVIEW. Unlocated/missing evidence produces INVALID and removes the expression preview. All candidates, including VALIDATED ones, have `review_status=PENDING`.

Candidate/evidence writes are transactional after all provider batches pass schema/provenance checks. A wrong document/scheme response or failed later batch commits no partial candidates. Parsed source pages and original versions survive failed generation. Candidate proposals never enter RuleSet/RuleCondition/RuleEvidence. The approved-version eligibility repository is unchanged; metadata-only government schemes continue to return UNKNOWN with no evaluated rule version.

## Deterministic tests and supervised demonstration

```bash
docker compose exec -T api python -m tests.run
```

Tests mock provider responses and failures; they never require a real key or spend API quota. The historical AICTE Saksham demonstration uses a separately labeled operator-only fixture. It verifies the exact source URL and scheme slug, searches the actual chunk for its reviewed quote, and produces one pending historical candidate. It is disabled in production and cannot be selected through any HTTP API or automatic fallback.

After registering the reviewed official PDF as an administrator:

```bash
docker compose exec api python -m app.ingestion.demo \
  --document-id DOCUMENT_VERSION_UUID --admin-username reviewer --acknowledge-mock
```

Use real Gemini only after configuring an authorized key and reviewing its provider data handling. Live response quality, model-account availability, billing/quota behavior and provider schema compatibility have not been verified without real credentials. A mock success is not a claim that a live model call succeeded.
