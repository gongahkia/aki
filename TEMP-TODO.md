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

## Task 12 — JSONL loader + jikai_eval_v1 task (upgrade #4b)

**Goal.** Make `src/evals/runner.py` load `corpus/eval/sg_tort_v1.jsonl`
and add a `jikai_eval_v1` task in `src/evals/tasks.py` that runs the full
generation pipeline (retrieval + generation + validation + faithfulness +
citation) and populates `case.metadata` for the new evaluators.

### Files to edit

- **EDIT** `src/evals/runner.py::resolve_dataset_path` and `load_dataset` —
  accept `.jsonl`. For JSONL, iterate lines with `json.loads`; for YAML keep
  existing path.
- **EDIT** `src/evals/tasks.py` — add `jikai_eval_v1_task`.
- **EDIT** `src/evals/tasks.py::TASKS` — register.
- **NEW** `tests/test_evals/test_jikai_eval_v1.py`.

### Loader patch

```python
def load_dataset(dataset: str) -> list[EvalCase]:
    path = resolve_dataset_path(dataset)
    if path.suffix == ".jsonl":
        cases = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                cases.append(EvalCase.model_validate(json.loads(line)))
        return cases
    # existing YAML path
    ...
```

Also extend `resolve_dataset_path` candidates with `.jsonl` and search
`corpus/eval/` as a candidate root.

### `jikai_eval_v1_task`

```python
async def jikai_eval_v1_task(case: EvalCase) -> str:
    from src.services.corpus_service import corpus_service
    from src.services.vector_service import vector_service
    from src.services.hypothetical_service import hypothetical_service
    from src.services.verification.nli_verifier import nli_verifier
    from src.services.verification.citation_verifier import citation_verifier
    from src.services.llm_service import llm_service

    topics = _topics(case)
    query = str(case.inputs.get("query", " ".join(topics)))

    # 1. retrieval
    retrieved = await vector_service.hybrid_search(
        query=query,
        corpus_pack=case.metadata.get("corpus_pack", "sg_tort"),
        n_results=int(case.inputs.get("top_k", 5)),
    )
    case.metadata["retrieved_ids"] = [r.get("id") for r in retrieved if r.get("id")]

    # 2. generation
    async with _HYPO_GENERATOR_LOCK:
        result = await hypothetical_service.generate_hypothetical(
            _build_request_from_case(case)
        )
    case.metadata["model_answer"] = (result.model_answer.model_dump()
                                     if getattr(result, "model_answer", None) else None)

    # 3. NLI faithfulness
    contexts = [{"corpus_id": r.get("id",""), "text": r.get("text","")} for r in retrieved]
    claims = await nli_verifier.extract_claims(result.hypothetical, llm_service)
    case.metadata["faithfulness_report"] = nli_verifier.verify(claims, contexts).model_dump()

    # 4. citation
    if result.model_answer:
        case.metadata["citation_report"] = (
            await citation_verifier.verify_model_answer(result.model_answer)
        ).model_dump()

    return result.hypothetical
```

Add `TASKS["jikai_eval_v1"] = jikai_eval_v1_task`.

### Verification

```
pytest -q tests/test_evals/test_jikai_eval_v1.py
python -m src.evals.run --workflow jikai_eval_v1 --dataset corpus/eval/sg_tort_v1.jsonl \
  --evaluator retrieval_recall_at_k --evaluator retrieval_mrr \
  --evaluator ragas_faithfulness --evaluator citation_accuracy \
  --evaluator hallucination_profile --evaluator irac_completeness \
  --output docs/evals/results_v1.json
```

### Dependencies

- Tasks 7, 8, 9, 10, 11.

---

## Task 13 — Benchmark runner + ablation script (upgrade #4c)

**Goal.** Two CLI scripts that produce publishable numbers.

### Files to create

- **NEW** `script/run_jikai_eval.py`
- **NEW** `script/run_ablations.py`
- **NEW** `docs/evals/leaderboard.md` (generated markdown)
- **NEW** `docs/evals/results_v1.json` (generated)
- **NEW** `docs/evals/ablations_v1.json` (generated)

### `script/run_jikai_eval.py`

CLI shape:

```
python script/run_jikai_eval.py \
  --providers ollama,openai,anthropic \
  --retrieval hybrid,dense,bm25 \
  --backends baseline,structured,refine \
  --output docs/evals/results_v1.json
```

Behaviour:

1. For each combination `(provider, retrieval, backend)`:
   - Set `settings.llm.provider = provider`, `settings.retrieval_mode = retrieval`,
     `settings.structured_generation_enabled = (backend != "baseline")`,
     `settings.refine_max_iterations = (2 if backend == "refine" else 0)`.
   - Run `src.evals.run_eval(EvalRequest(workflow="jikai_eval_v1",
     dataset="corpus/eval/sg_tort_v1.jsonl", evaluators=<all seven>))`.
   - Collect `EvalReport.summary.evaluator_means` under a `(provider, retrieval, backend)` key.
2. Merge all reports into `results_v1.json` with shape:

```json
{
  "schema_version": "jikai.results.v1",
  "generated_at": "2026-07-02T...",
  "corpus_pack": "sg_tort",
  "eval_dataset": "corpus/eval/sg_tort_v1.jsonl",
  "runs": [
    {
      "provider": "openai",
      "retrieval": "hybrid",
      "backend": "refine",
      "n_cases": 50,
      "metrics": {
        "retrieval_recall_at_k": 0.86,
        "retrieval_mrr": 0.72,
        "ragas_faithfulness": 0.81,
        ...
      }
    }, ...
  ]
}
```

3. Emit `docs/evals/leaderboard.md` — a table sorted by faithfulness
   descending, with columns `Provider | Retrieval | Backend | R@5 | MRR |
   Faithfulness | Citation | IRAC | Hallucination`.

### `script/run_ablations.py`

Runs `baseline` vs `+structured` vs `+refine` vs `+setfit` vs `+all`, using a
fixed provider (default `ollama` for cheap iteration), and writes per-metric
deltas to `docs/evals/ablations_v1.json`. Also emits a markdown appendix
`docs/evals/ablations.md`.

### Verification

```
python script/run_jikai_eval.py --providers ollama --backends baseline
cat docs/evals/results_v1.json | jq '.runs[0].metrics'
cat docs/evals/leaderboard.md
```

Expected: `metrics` dict with 7 keys, all floats in [0,1]. Leaderboard renders.

For CI, add a `--dry-run` flag that stubs the LLM calls with fixed strings so
the pipeline exercises without cost.

### Dependencies

- Task 12 (needs the `jikai_eval_v1` task registered and the JSONL loader).
- Tasks 7–11 (metrics have to be real).

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

- Task 13 (needs `docs/evals/results_v1.json` to exist).

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

1. **Task 12** — JSONL loader + `jikai_eval_v1` task.
2. **Task 13** — benchmark runner + ablation script.
3. **Task 14** — research writeup + README rewrite.
4. **CI/reqs** — cross-cutting; last (after real deps are settled).

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
