# TEMP-TODO — Jikai Portfolio Uplift Handoff

## About this doc

This document is a **standalone handoff spec** for the remaining work on the
Jikai portfolio uplift. An independent coding agent should be able to drop in,
read this file, and implement each task without needing to re-derive design
decisions from the audit or plan.

The audit + plan are at `/Users/gongahkia/.claude/plans/i-want-you-whimsical-wren.md`.
The overall goal is to bring Jikai to research-parity with LegalBench-RAG,
RAGAS, Stanford's Dahl/Magesh legal-hallucination work, and DSPy-style
compiled programs — grounded in code and numbers, framed marketing-first with
limits framed as roadmap.

**Already shipped (do not re-do):**

- `corpus/eval/sg_tort_v1.jsonl` — 50 held-out SG-tort eval cases (JSONL).
- `corpus/eval/README.md` — provenance and licensing for the eval set.
- `corpus/packs/sg_tort/authorities.json` — 15 authorities + 7 statutes index.
- `corpus/packs/sg_tort/manifest.json` — extended with new open-access sources + `authorities_path` + `eval_dataset_path`.
- `docs/sg-tort-corpus-source-decision.md` — mirrors the UK/US source-decision docs.
- `src/services/prompt_engineering/schemas.py` — Pydantic schemas
  (`HypotheticalDraft`, `ModelAnswer`, `IRACStep`, `CorpusRef`, `Party`, `Issue`,
  `FactPattern`, `Claim`, `ClaimVerdict`, `FaithfulnessReport`, `CitationReport`,
  `RefineCritique`). **Every new module below imports from here.**
- `src/ml/setfit_classifier.py` — SetFit backend with train/predict/save/load
  and `predict_confidence(text, requested_topics)` for the gate.
- `src/ml/legal_bert_scorer.py` — Legal-BERT regression scorer replacing the GBM.
- `src/ml/pipeline.py` — dispatch flag `classifier_backend={"tfidf","setfit"}`;
  new method `MLPipeline.gate_confidence(text, requested_topics)` returns
  `{per_topic, min_confidence, mean_confidence, backend}`.
- `src/services/hypothetical_service.py` — added `_ml_gate_check` and
  `_build_ml_gate_retry_request`; wired a blocking ML-gate retry pass before
  validation. `response.metadata.ml_gate` now surfaces the report.
- `src/config/settings.py` — added `ml_gate_threshold`, `ml_gate_blocking`,
  `nli_verifier_enabled`, `nli_verifier_model`, `faithfulness_min_score`,
  `citation_min_accuracy`, `refine_max_iterations`,
  `structured_generation_enabled`, `refine_trace_dir`.
- `notebooks/train_setfit.ipynb`, `notebooks/train_legal_bert_scorer.ipynb`
  (Colab one-off training).

## Prerequisites for the agent

Add to `requirements.txt` (already the venv-managed file for this repo):

```
instructor>=1.6.0        # multi-provider structured output
outlines>=0.1.0          # local-LLM constrained decoding
ragas>=0.2.0             # optional, only for reference; we implement the metric ourselves
setfit>=1.1.0            # already used by upgrade #1
```

Runtime deps already present (do not re-add): `sentence-transformers`,
`transformers`, `torch`, `pydantic`, `structlog`, `httpx`, `chromadb`,
`fastapi`, `uvicorn`.

Optional model checkpoints — expected on disk if the user has run the notebooks:

- `models/setfit_sg_tort/` — SetFit classifier
- `models/legal_bert_scorer/` — Legal-BERT scorer
- HF cache pull on first run: `cross-encoder/nli-deberta-v3-base` (~440 MB)

All new code MUST degrade gracefully when a dep or checkpoint is missing —
the smoke E2E must run on a clean checkout with only the base `requirements.txt`
installed.

---

## Task 14 — Research writeup + README rewrite (upgrade #5)

**Goal.** Ship a marketing-first research section that turns Jikai from
"another RAG demo" into "an ML-gated legal generation pipeline with published
numbers." Every claim must cite a specific file, function, or number in
`docs/evals/results_v1.json`.

### Files to create/edit

- **NEW** `research/README.md` — executive summary. Lead with the strongest
  metric across ablations. Cite exact numbers from `docs/evals/results_v1.json`.
- **NEW** `research/methodology.md` — describes the ML gate (SetFit + gate
  threshold), NLI-based faithfulness (RAGAS-derived), citation grounding
  against `authorities.json`, LegalBench-RAG-style retrieval metrics
  (`R@5`, `MRR`, `nDCG`), and the IRAC-chain model-answer generation. Include
  a Mermaid diagram of the refine loop.
- **NEW** `research/results.md` — the published numbers. Charts optional
  (matplotlib or markdown tables). Lead with `refine + structured` win over
  `baseline`.
- **NEW** `research/related_work.md` — one-paragraph summaries of:
  LegalBench-RAG (arXiv 2408.10343), LexRAG (SIGIR 2025), LRAGE (arXiv
  2504.01840), Dahl 2024 "Large Legal Fictions" (58–88% hallucination), Magesh
  2025 "Hallucination-Free?" (17–33% citation fabrication on Lexis/Westlaw),
  RAGAS, TruLens, DeepEval, DSPy, SetFit, Instructor, Outlines.
- **NEW** `research/roadmap.md` — future work: UK/US pack ingestion, blind-eval
  pilot execution (rubric v1 exists, needs 3+ raters), DPO from feedback,
  larger training corpus, jurisdiction-parametric authorities index.
- **EDIT** `README.md` — rewrite the `## Research`, `## So where's the ML`, and
  `## So where's the LLM` sections to reference `research/` and cite the
  specific numbers. Add benchmark badges backed by `docs/evals/results_v1.json`
  values (e.g. `![faithfulness](https://img.shields.io/badge/faithfulness-0.81-4CAF50)`).

### Voice & framing rules

1. Every metric claim links to `research/results.md`.
2. Every architectural claim links to a file:line in `src/`.
3. Limitations are framed under `research/roadmap.md`, not in the main
   README (user preference: marketing-first).
4. No unlabelled inferences — follow the user's `[Inference] / [Unverified]`
   convention when a claim can't be sourced to code or numbers.

### Verification

```
markdown-link-check research/README.md  # if the tool is available
grep -n "Faithfulness\|IRAC\|SetFit\|LegalBench-RAG" README.md  # ≥ 4 hits
python -c "import json; d=json.load(open('docs/evals/results_v1.json'));
print(d['runs'][0]['metrics']['ragas_faithfulness'])"
# use that value in README badge
```

### Dependencies

- `docs/evals/results_v1.json` exists.

---

## Cross-cutting: CI + requirements

- **EDIT** `requirements.txt` — add pinned versions:
  ```
  instructor>=1.6.0
  outlines>=0.1.0
  setfit>=1.1.0
  ```
- **EDIT** `.github/workflows/ci.yml` — add job
  ```
  benchmarks-dry-run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install -r requirements.txt
      - run: python script/run_jikai_eval.py --dry-run --providers ollama
      - run: cat docs/evals/results_v1.json | jq '.schema_version'
  ```
- **NEW** `.github/workflows/benchmarks.yml` — weekly cron running the real
  eval sweep on OpenAI+Anthropic with a small subset (`--n-cases 5`) using
  encrypted API keys. Uploads `results_v1.json` as artifact.

---

## Build order (for the agent)

1. **Task 14** — research writeup + README rewrite.
2. **CI/reqs** — cross-cutting; last (after real deps are settled).

Each task's `Verification` section is intentionally executable. When a task's
verification fails, do not proceed to the next task.

---

## Anti-patterns to avoid

- **Do not** replace the existing TF-IDF/LinearSVC classifier — keep it as
  fallback when SetFit weights aren't present. `MLPipeline.classifier_backend`
  already handles this.
- **Do not** silently return the drafted hypothetical when a verifier fails.
  The refine loop is authoritative; if it exhausts iterations, expose the
  final critique in `response.metadata.refine.final_critique` and set the
  response's `validation_results.passed = False`.
- **Do not** add fields to `EvalCase` without also updating
  `src/evals/models.py`. The model has a `require_jurisdiction` validator.
- **Do not** break the existing YAML eval datasets under
  `src/evals/datasets/*.yaml`. The runner must load both YAML and JSONL.
- **Do not** commit large model weights. Keep `models/setfit_sg_tort/` and
  `models/legal_bert_scorer/` gitignored; prefer HF Hub push and lazy load.
- **Do not** add UK/US corpus data — those stay as manifests (see plan
  non-goals). Only the eval set and authorities index for SG grow.

## References

- Plan: `/Users/gongahkia/.claude/plans/i-want-you-whimsical-wren.md`
- Corpus pack ADR: `docs/adr/0001-jurisdiction-and-corpus-packs.md`
- Blind-eval rubric v1: `docs/evals/blind-eval-rubric-v1.md`
- LLM gateway policy: `agent_docs/llm-gateway-policy.md`
- LegalBench-RAG: arXiv 2408.10343
- RAGAS docs: https://docs.ragas.io
- Instructor docs: https://python.useinstructor.com
- Outlines docs: https://dottxt-ai.github.io/outlines/
- DSPy docs: https://dspy.ai
- SetFit paper: arXiv 2209.11055
- Dahl et al. 2024 "Large Legal Fictions": 16 J. Legal Analysis 64
- Magesh et al. 2025 "Hallucination-Free?": 22 J. Empirical Legal Stud. 216
- cross-encoder/nli-deberta-v3-base: https://huggingface.co/cross-encoder/nli-deberta-v3-base
