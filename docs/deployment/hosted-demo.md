# Hosted Demo Deployment

Status: public fixture demo ready; server-backed provider demo remains private/repo-ready until API hardening is complete.
Decision issue: #32.

Public fixture URL: https://gabrielongzm.com/jikai/

## Public GitHub Pages Target

- `GET /jikai/`: browser-only SG Tort fixture generator.
- No provider secrets required.
- No prompts leave the browser.
- Failure states are shown for unsupported jurisdictions, empty topics, and unsupported fixture topics.

## Server-Backed Target

- `GET /demo`: browser form for SG Tort hypothetical generation.
- `GET /demo/pipeline`: fixture pipeline trace.
- `POST /workflow/generate`: generation API.
- `GET /health`: platform health check.

## Chosen Path

Keep only the GitHub Pages no-secret fixture demo public. The server-backed provider demo may be deployed for controlled review, but it must not be advertised or treated as a public student surface until mutating/admin endpoints, provider selection, corpus writes, job/export paths, request size, and route-level rate limits are locked down.

`render.yaml` targets a Docker web service, uses `/health`, enables the in-process rate limiter, and keeps provider credentials server-side.

## GitHub Pages Steps

1. Keep the static demo at `docs/index.html`.
2. Enable Pages from `main` and `/docs`.
3. Verify `https://gabrielongzm.com/jikai/`.
4. Run `python3 script/validate_hosted_demo.py https://gabrielongzm.com/jikai/ --static`.
5. Keep the README public demo link pointed at `https://gabrielongzm.com/jikai/`.

## Required Secrets

| Secret | Required | Notes |
|---|---:|---|
| `OPENAI_API_KEY` | yes for current Render default | Visitors do not provide keys. |
| `ANTHROPIC_API_KEY` | optional | Enables Anthropic provider if selected. |
| `GOOGLE_API_KEY` | optional | Enables Gemini provider for API use. |
| `LOCAL_LLM_HOST` | optional | Only for a reachable OpenAI-compatible host. |

## Render Steps

Do this only for private review until the hosted API hardening issue closes.

1. Connect this GitHub repo to Render.
2. Create the web service from `render.yaml`.
3. Set `OPENAI_API_KEY` in Render env vars.
4. Keep `LLM_PROVIDER=openai`, `DEFAULT_PROVIDER=openai`, and `DEFAULT_MODEL=gpt-4o-mini` unless another server-side model is approved.
5. Deploy.
6. Verify `/health`.
7. Verify `/demo` can generate an SG Tort hypothetical with model answer.
8. Run `python3 script/validate_hosted_demo.py https://YOUR_HOST --generate`.
9. Do not replace the README public demo URL with a server-backed `/demo` URL until hardening is complete.

## Local Container Smoke

```console
$ docker build -t jikai-demo .
$ docker run --rm -p 8000:8000 -e PORT=8000 -e ENVIRONMENT=production -e API_DEBUG=false -e API_RATE_LIMIT=30 -e OPENAI_API_KEY="$OPENAI_API_KEY" jikai-demo
$ curl -sf http://127.0.0.1:8000/health | python3 -m json.tool
$ python3 script/validate_hosted_demo.py http://127.0.0.1:8000
```

## Abuse Controls

- IP bucket limiter: `API_RATE_LIMIT` per `API_RATE_LIMITER_BUCKET_TTL_SECONDS`.
- Browser abort: 95 seconds.
- Provider timeout: `LLM_TIMEOUT`.
- Provider circuit breaker and mapped JSON errors are handled in the LLM/API service layer.

These controls are necessary but not sufficient for a public server-backed student demo. Public server-backed exposure requires authenticated or disabled mutating/admin routes, request-scoped or admin-only provider selection, locked export paths, and route/body limits.

## Cost And Privacy Copy

`/demo` tells users that prompts and outputs are processed by the host's server-side provider and not to enter personal, privileged, or exam-confidential material.

## Close Criteria For #13

Close #13 when the public fixture demo criteria below are true. Keep Render work as the optional server-backed path.

- Stable public URL is live.
- The public page can generate SG Tort hypotheticals and model answers end-to-end at that URL.
- Failure states are visible in browser.
- README links to the actual public URL near the top.
- Required secrets and deployment steps are documented here.
