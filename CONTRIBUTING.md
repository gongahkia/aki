# Contributing

Junas is backend-first. Contributions should preserve the deterministic local
runtime and keep adapter claims tied to documented evidence.

## Setup

Use `uv` from the repo root:

```sh
uv sync --extra dev
uv run python -m spacy download en_core_web_sm
uv run python scripts/preflight.py --strict
```

Run the one-command deterministic demo:

```sh
./scripts/demo.sh
```

Start the backend when you need an interactive local API:

```sh
./scripts/launch/run_backend_only.sh
curl http://127.0.0.1:8000/ready
```

## Verification

For docs-only changes, run the focused tests that cover the touched surface plus
format checks:

```sh
uv run ruff check
git diff --check
```

For runtime changes, run the standard gate:

```sh
./scripts/verify_runtime.sh
uv run pytest
```

CI runs changed-file whitespace, Ruff format/lint, grouped pytest suites, the
one-command demo, redaction smoke tests, Docker smoke, and benchmark gates.

For accuracy, corpus, or detector work, also run the relevant generated-doc and
recall gates:

```sh
uv run python scripts/recall_gate.py
uv run python scripts/generate_accuracy_doc.py --check
```

## Invariants

- The default local runtime is deterministic and offline. Do not add provider keys,
  external HTTP calls, LLM calls, or cloud dependencies to `review_profile=strict`.
- The local SKU must not require `torch`, `transformers`, `sentence-transformers`,
  `redis`, `xgboost`, `scikit-learn`, `pandas`, `accelerate`, or external HTTP.
- The FastAPI backend remains the trust boundary. Adapters collect workflow context
  and display backend decisions; they must not become separate detection or policy
  engines.
- Deterministic-high findings must stay visible in the review and policy path.
  Optional public-evidence or LLM helpers may add context for eligible audit-grade
  cases, but must not erase deterministic-high evidence.
- Logs, telemetry, SIEM events, docs examples, and issue bodies must not include
  real secrets, customer text, live personal data, reversible mappings, or auth
  headers.
- README/product claims need local evidence: docs, tests, eval reports, screenshots,
  generated artifacts, or vendor docs where platform behavior is involved.

## Rule Packs

Community secret rule-pack changes must follow `docs/community-rule-packs.md`.
Each contribution needs one regex or detector-equivalent rule plus one synthetic
matching fixture. Add a non-matching or allowlisted fixture when false positives
are likely, and run `uv run junas rules test` against the touched pack before review.

## Good First Issues

Prefer docs and small tests before changing detector, auth, persistence, or adapter
runtime code. Current scoped issues:

- [#16: Add built-in fake-secret demo](https://github.com/gongahkia/junas/issues/16)

These are intentionally small scoped entry points drawn from the GitHub issue backlog.

## Pull Request Notes

- Keep changes scoped to the issue or task.
- Update tests when changing behavior, contracts, or user-visible docs.
- Do not broaden maturity, security, or accuracy claims without adding evidence in
  the same change.
- Include the commands you ran in the PR description.
