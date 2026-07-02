# Hosted Demo Deployment

Status: repo-ready; public URL not provisioned in this workspace.

## Target

- `GET /demo`: browser form for SG Tort hypothetical generation.
- `GET /demo/pipeline`: fixture pipeline trace.
- `POST /workflow/generate`: generation API.
- `GET /health`: platform health check.

## Chosen Path

Use the existing Dockerized FastAPI service on Render first. `render.yaml` targets a Docker web service, uses `/health`, enables the in-process rate limiter, and keeps provider credentials server-side.

## Required Secrets

| Secret | Required | Notes |
|---|---:|---|
| `OPENAI_API_KEY` | yes for current Render default | Visitors do not provide keys. |
| `ANTHROPIC_API_KEY` | optional | Enables Anthropic provider if selected. |
| `GOOGLE_API_KEY` | optional | Enables Gemini provider for API use. |
| `LOCAL_LLM_HOST` | optional | Only for a reachable OpenAI-compatible host. |

## Render Steps

1. Connect this GitHub repo to Render.
2. Create the web service from `render.yaml`.
3. Set `OPENAI_API_KEY` in Render env vars.
4. Keep `LLM_PROVIDER=openai`, `DEFAULT_PROVIDER=openai`, and `DEFAULT_MODEL=gpt-4o-mini` unless another server-side model is approved.
5. Deploy.
6. Verify `/health`.
7. Verify `/demo` can generate an SG Tort hypothetical with model answer.
8. Replace any placeholder URL in README with the live public `/demo` URL.

## Local Container Smoke

```console
$ docker build -t jikai-demo .
$ docker run --rm -p 8000:8000 -e PORT=8000 -e ENVIRONMENT=production -e API_DEBUG=false -e API_RATE_LIMIT=30 -e OPENAI_API_KEY="$OPENAI_API_KEY" jikai-demo
$ curl -sf http://127.0.0.1:8000/health | python3 -m json.tool
```

## Abuse Controls

- IP bucket limiter: `API_RATE_LIMIT` per `API_RATE_LIMITER_BUCKET_TTL_SECONDS`.
- Browser abort: 95 seconds.
- Provider timeout: `LLM_TIMEOUT`.
- Provider circuit breaker and mapped JSON errors are handled in the LLM/API service layer.

## Cost And Privacy Copy

`/demo` tells users that prompts and outputs are processed by the host's server-side provider and not to enter personal, privileged, or exam-confidential material.

## Close Criteria For #13

Do not close #13 until all are true:

- Stable public URL is live.
- `/demo` can generate SG Tort hypotheticals end-to-end at that URL.
- Failure states are visible in browser.
- README links to the actual public URL near the top.
- Required secrets and deployment steps are documented here.
