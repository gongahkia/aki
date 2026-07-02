# Product Surfaces

This project has multiple interfaces. They should not be treated as equal product entrypoints.

## Primary Surface

`/demo` is the main user-facing surface.

Audience: law students, educators, HN visitors, portfolio reviewers.

Use it to ask for an SG Tort hypothetical, watch Jikai pull grounding cases, and inspect the generated hypo/model answer. This should stay simple and chat-first. Users should not need to understand corpus packs, providers, jobs, or validators before they get value.

## Trust / Explanation Surface

Pipeline trace detail now appears inside `/demo`.

Audience: technical reviewers, legal-tech builders, educators assessing quality.

Use the chat run's trace details to show how a generation moves through topic scope, ML foundation, retrieval, prompt assembly, generation, validation, and study artifacts. The old `/demo/pipeline` page redirects to `/demo`; `/demo/pipeline/trace` remains a JSON data endpoint for the chat UI.

## Builder Surface

The REST API is the integration surface.

Audience: developers, researchers, automation users.

Key routes:

- `/workflow/generate`
- `/workflow/batch-generate`
- `/corpus/query`
- `/corpus/topics`
- `/jobs/export-anki`
- `/llm/health`
- `/validation/*`

`/llm/generate` is useful for debugging provider routing, but should not be the product lead. It makes Jikai look like a generic LLM wrapper instead of a constrained legal-practice pipeline.

## Power-User Surface

The Rust TUI is a local operator surface.

Audience: maintainers and terminal-first users.

Keep it as proof of depth and local-first ergonomics, but do not make it the first thing a new user sees. [Inference] Browser demo first, TUI second is the better portfolio/HN order.

## Contributor Surface

Docs and corpus tooling are the contributor surface.

Audience: people adding jurisdictions, subjects, or evals.

Start here:

- `docs/corpus-pack-manifest.md`
- `docs/adr/0001-jurisdiction-and-corpus-packs.md`
- `docs/pivot-sg-tort-assumption-audit.md`
- `src/domain/packs.py`
- `corpus/packs/*/manifest.json`
- `src/evals/README.md`

## Repo Approach By Audience

Law student: start at `/demo`. Ignore API docs unless exporting or automating.

Educator: start at `/demo`, inspect trace details in a saved run, then read the blind-eval docs under `docs/evals/`.

Legal-tech builder: read `README.md`, run `/demo`, open trace details in chat, then inspect `src/services/workflow_facade.py`, `src/services/hypothetical_service.py`, and `src/services/pipeline_trace_service.py`.

Corpus contributor: read `docs/corpus-pack-manifest.md`, then inspect `corpus/packs/sg_tort/manifest.json` and `src/domain/packs.py`.

Portfolio reviewer / HN visitor: open `/demo`, click `Load sample`, then inspect the README pipeline diagram and `docs/launch/blog-ml-foundation-before-llm.md`.

## Product Recommendation

Lead with one claim: Jikai is an open-source legal practice-question pipeline, not a chatbot wrapper.

Expose the surfaces in this order:

1. `/demo`
2. README architecture
3. REST API
4. TUI
5. corpus/eval contribution docs

Avoid leading with raw provider controls, direct LLM routes, database routes, or internal jobs. Those are useful, but they dilute the product story for non-maintainers.
