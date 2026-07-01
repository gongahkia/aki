# LLM Gateway Policy

## Source Comparison

Elefant `ai/gateway.py` is a Pydantic AI Gateway model registry. It normalizes bare model names into `gateway/provider:model`, enforces an allowlist, exposes capability tiers, and requires a gateway API key.

Jikai keeps direct provider clients behind `LLMService` and `llm_providers`. The public provider interface stays unchanged: `generate`, `stream_generate`, `list_models`, `health_check`, and `close`.

Elefant `ai/resilience.py` retries only `output_parse_failed` `ModelHTTPError`s, up to two retries, before failing. It does not define a provider circuit breaker, health-check cadence, cost tracking, or fallback order.

Jikai already has provider init, capability checks, token-cost accounting, request timeout bounds, circuit breaking, and fallback. The stricter Elefant behavior to preserve is narrow retry scope: no broad retry loop should re-run requests after partial streaming output.

## Runtime Policy

Fallback order is deterministic and local-first: `ollama`, `local`, `openai`, `google`, `anthropic`. Registry insertion order does not decide fallback priority.

Circuit breaker threshold remains 3 consecutive transient failures. Cooldown uses `CIRCUIT_BREAKER_COOLDOWN_SECONDS` with +/-20% jitter before provider retries during batch evals.

Transient failures trip the circuit: timeout, HTTP 5xx, rate limit, provider-down/network, and unknown provider exceptions. Permanent configuration failures do not trip it: auth/API key failures and missing model errors.

Streaming does not retry after token emission. Jikai may switch to a healthy fallback only before the stream starts, when the requested provider is already circuit-broken.

Health checks are on-demand through `LLMService.health_check()` with a 30s timeout per provider. There is no background cadence in this repo.

Cost tracking remains session-local through `TOKEN_COSTS` and response usage. Fallback ordering is configured policy, not live cost optimization.

## Test Contract

`tests/test_services/test_llm_service.py` covers timeout, HTTP 5xx, rate-limit, and provider-down classification; permanent auth/model errors; jittered circuit trips; and registry-order-independent fallback.
