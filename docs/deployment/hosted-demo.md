# Hosted Demo Deployment

Status: public fixture demo ready; server-backed provider demo is repo-hardened but not advertised as the public URL.
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

Keep only the GitHub Pages no-secret fixture demo as the advertised public link. The server-backed provider demo may be deployed for controlled review or approved public use after the deployment owner sets provider credentials, route/body limits, and cost monitoring.

`render.yaml` targets a Docker web service, uses `/health`, enables hosted mode, enables the in-process rate limiter, and keeps provider credentials server-side.

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
| `API_ADMIN_KEY` | optional for private admin access | If unset in hosted mode, admin routes are disabled instead of public. |
| `ANTHROPIC_API_KEY` | optional | Enables Anthropic provider if selected. |
| `GOOGLE_API_KEY` | optional | Enables Gemini provider for API use. |
| `LOCAL_LLM_HOST` | optional | Only for a reachable OpenAI-compatible host. |

## Render Steps

Use these steps for private review or a controlled hardened deployment.

1. Connect this GitHub repo to Render.
2. Create the web service from `render.yaml`.
3. Set `OPENAI_API_KEY` in Render env vars.
4. Set `API_ADMIN_KEY` only if authenticated admin/API access is needed.
5. Keep `LLM_PROVIDER=openai`, `DEFAULT_PROVIDER=openai`, and `DEFAULT_MODEL=gpt-4o-mini` unless another server-side model is approved.
6. Deploy.
7. Verify `/health`.
8. Verify `/demo` can generate an SG Tort hypothetical with model answer.
9. Run `python3 script/validate_hosted_demo.py https://YOUR_HOST --generate`.
10. Verify `/jobs/cleanup` and `/corpus/add` return `401` with a wrong key or `403` when `API_ADMIN_KEY` is unset.

## Local Container Smoke

```console
$ docker build -t jikai-demo .
$ docker run --rm -p 8000:8000 -e PORT=8000 -e ENVIRONMENT=production -e API_HOSTED_MODE=true -e API_DEBUG=false -e API_RATE_LIMIT=30 -e OPENAI_API_KEY="$OPENAI_API_KEY" jikai-demo
$ curl -sf http://127.0.0.1:8000/health | python3 -m json.tool
$ python3 script/validate_hosted_demo.py http://127.0.0.1:8000
```

## Abuse Controls

- IP bucket limiter: `API_RATE_LIMIT` per `API_RATE_LIMITER_BUCKET_TTL_SECONDS`.
- Route buckets: `API_DEMO_RATE_LIMIT`, `API_GENERATE_RATE_LIMIT`, and `API_ADMIN_RATE_LIMIT`.
- Body limits: `API_MAX_BODY_BYTES`, `API_GENERATE_MAX_BODY_BYTES`, and `API_ADMIN_MAX_BODY_BYTES`.
- Hosted admin gate: `API_HOSTED_MODE=true` or `ENVIRONMENT=production` requires `API_ADMIN_KEY` for non-public routes.
- Browser abort: 95 seconds.
- Provider timeout: `LLM_TIMEOUT`.
- Provider circuit breaker and mapped JSON errors are handled in the LLM/API service layer.

Hosted public routes are `/health`, `/version`, `/demo/*`, and `POST /workflow/generate`. Mutating/admin routes such as `/jobs/*`, `/corpus/add`, `/llm/select-provider`, and `/llm/select-model` require `x-api-key: $API_ADMIN_KEY` or `Authorization: Bearer $API_ADMIN_KEY`; if no key is configured, they are disabled.

## Cost And Privacy Copy

`/demo` tells users that prompts and outputs are processed by the host's server-side provider and not to enter personal, privileged, or exam-confidential material.

## Close Criteria For #13

Close #13 when the public fixture demo criteria below are true. Keep Render work as the optional server-backed path.

- Stable public URL is live.
- The public page can generate SG Tort hypotheticals and model answers end-to-end at that URL.
- Failure states are visible in browser.
- README links to the actual public URL near the top.
- Required secrets and deployment steps are documented here.
