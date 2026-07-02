# Frontend

Static browser surfaces live here. FastAPI serves them; there is no Node build step.

## Layout

| Path | Served At | Purpose |
|------|-----------|---------|
| `demo/index.html` | `/demo` and `/demo/generate` | Primary chat-style demo |
| `demo/app.css` | `/demo/static/app.css` | Demo styling |
| `demo/app.js` | `/demo/static/app.js` | Demo interactions and API calls |

## Backend Boundary

`src/api/main.py` mounts static assets at `/demo/static`.
`src/api/routes/demo.py` serves HTML files and owns JSON trace endpoints.

The frontend should call public API routes only:

- `/workflow/generate`
- `/demo/pipeline/trace`
- `/health`
- browser IndexedDB for local run history

Keep provider routing, corpus access, validation, persistence, and model orchestration in `src/`.
