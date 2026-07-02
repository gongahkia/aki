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

## Task 8 — NLI faithfulness verifier (upgrade #3a)

**Goal.** For each generated hypothetical, extract discrete factual claims,
NLI-check each claim against retrieved corpus passages, produce a
`FaithfulnessReport`. Wire into `hypothetical_service` so the report lands in
`response.validation_results.faithfulness` and the refine loop (task 10) can
consume it.

### Files to create/edit

- **NEW** `src/services/verification/__init__.py` — `from .nli_verifier import
  NLIFaithfulnessVerifier`.
- **NEW** `src/services/verification/nli_verifier.py` — the verifier.
- **EDIT** `src/services/hypothetical_service.py` — call the verifier during
  validation, attach `faithfulness` field to the response.
- **NEW** `tests/test_services/test_nli_verifier.py` — mock the LLM claim
  extraction, use a real cross-encoder on toy inputs.

### Reference APIs

- **Claim extraction** (LLM call, gated by `settings.nli_verifier_enabled`):
  ```python
  from ..prompt_engineering.schemas import Claim
  from ..llm_service import llm_service, LLMRequest

  CLAIM_EXTRACTION_PROMPT = (
      "Extract discrete factual claims from the following legal hypothetical. "
      "Return a JSON list of {\"text\": str} objects. Only assertions about "
      "the world (parties, actions, causation, timing, location) are claims — "
      "not questions, headings, or restatements of the prompt.\n\nText:\n{text}"
  )

  async def _extract_claims(self, text: str) -> list[Claim]:
      response = await llm_service.generate(LLMRequest(
          prompt=CLAIM_EXTRACTION_PROMPT.format(text=text),
          temperature=0.0,
          max_tokens=1024,
          response_format="json",
      ))
      raw = json.loads(response.content)
      return [Claim(text=item["text"]) for item in raw if item.get("text")]
  ```

  If the provider does not support `response_format="json"`, fall back to
  regex-splitting sentences (`re.split(r"(?<=[.!?])\s+", text)`) — noisier but
  never throws.

- **NLI check** using sentence-transformers CrossEncoder:
  ```python
  from sentence_transformers import CrossEncoder

  self.model = CrossEncoder(settings.nli_verifier_model)
  # Label mapping is fixed by cross-encoder/nli-deberta-v3-base:
  LABELS = ["contradiction", "entailment", "neutral"]

  def score_pair(premise: str, hypothesis: str) -> tuple[str, float]:
      scores = self.model.predict([(premise, hypothesis)])[0]  # shape (3,)
      idx = int(scores.argmax())
      return LABELS[idx], float(scores[idx])
  ```

### Module skeleton

```python
# src/services/verification/nli_verifier.py
from __future__ import annotations

import json
import re
from typing import Any

import structlog

from ..prompt_engineering.schemas import (
    Claim, ClaimVerdict, FaithfulnessReport,
)
from ...config import settings

logger = structlog.get_logger(__name__)
_NLI_LABELS = ["contradiction", "entailment", "neutral"]


class NLIFaithfulnessVerifier:
    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.nli_verifier_model
        self._model: Any = None

    def _load(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
                self._model = CrossEncoder(self.model_name)
            except Exception as exc:
                logger.warning("NLI model unavailable; verifier will noop", error=str(exc))
                self._model = False
        return self._model

    async def extract_claims(self, text: str, llm_service_ref) -> list[Claim]:
        # LLM-based extraction with regex fallback
        try:
            from ..llm_service import LLMRequest
            resp = await llm_service_ref.generate(LLMRequest(
                prompt=self._extraction_prompt(text),
                temperature=0.0,
                max_tokens=1024,
            ))
            raw = json.loads(_strip_code_fence(resp.content))
            return [Claim(text=str(item.get("text", ""))) for item in raw
                    if isinstance(item, dict) and item.get("text")]
        except Exception as exc:
            logger.info("Falling back to sentence-splitting for claim extraction",
                        error=str(exc))
            return [Claim(text=s.strip())
                    for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]

    def _extraction_prompt(self, text: str) -> str:
        return (
            'Extract discrete factual claims from the following legal '
            'hypothetical. Return ONLY a JSON list of {"text": str} objects. '
            'Only assertions about the world (parties, actions, causation, '
            'timing, location) are claims. No questions, headings, or '
            'restatements.\n\nText:\n' + text
        )

    def verify(
        self, claims: list[Claim], contexts: list[dict[str, str]]
    ) -> FaithfulnessReport:
        # contexts: [{"corpus_id": str, "text": str}, ...]
        model = self._load()
        if not model or not claims:
            return FaithfulnessReport(
                faithfulness_score=1.0 if not claims else 0.0,
                total_claims=len(claims), entailed=0,
                contradicted=0, unverifiable=len(claims),
            )
        verdicts: list[ClaimVerdict] = []
        entailed = contradicted = unverifiable = 0
        for claim in claims:
            best_verdict = "unverifiable"
            best_conf = 0.0
            best_source: str | None = None
            for ctx in contexts:
                scores = model.predict([(ctx["text"], claim.text)])[0]
                idx = int(scores.argmax())
                label = _NLI_LABELS[idx]
                conf = float(scores[idx])
                if label == "entailment" and conf > best_conf:
                    best_verdict, best_conf, best_source = (
                        "entailment", conf, ctx["corpus_id"]
                    )
                elif label == "contradiction" and best_verdict != "entailment":
                    if conf > best_conf:
                        best_verdict, best_conf, best_source = (
                            "contradiction", conf, ctx["corpus_id"]
                        )
            if best_verdict == "entailment":
                entailed += 1
            elif best_verdict == "contradiction":
                contradicted += 1
            else:
                unverifiable += 1
            verdicts.append(ClaimVerdict(
                claim=claim, verdict=best_verdict,
                confidence=best_conf, supporting_corpus_id=best_source,
            ))
        total = len(claims)
        return FaithfulnessReport(
            faithfulness_score=entailed / total if total else 1.0,
            total_claims=total, entailed=entailed,
            contradicted=contradicted, unverifiable=unverifiable,
            verdicts=verdicts,
        )


def _strip_code_fence(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s


nli_verifier = NLIFaithfulnessVerifier()
__all__ = ["NLIFaithfulnessVerifier", "nli_verifier"]
```

### Integration in `hypothetical_service.py`

After `_validate_hypothetical` returns `validation_results`, add:

```python
faithfulness_report = None
if settings.nli_verifier_enabled:
    try:
        from .verification.nli_verifier import nli_verifier
        claims = await nli_verifier.extract_claims(hypothetical, llm_service)
        contexts = [
            {"corpus_id": e.id or e.text[:32], "text": e.text}
            for e in (context_entries or [])
        ]
        faithfulness_report = nli_verifier.verify(claims, contexts).model_dump()
    except Exception as exc:
        logger.warning("NLI verifier failed (non-fatal)", error=str(exc))
```

Attach as `response.validation_results["faithfulness"] = faithfulness_report`
(via a dict merge — `ValidationResult.dict()` already produces a dict).

### Verification

```
pytest -q tests/test_services/test_nli_verifier.py
```

Manual smoke:

```
python -c "
from src.services.verification.nli_verifier import NLIFaithfulnessVerifier
from src.services.prompt_engineering.schemas import Claim
v = NLIFaithfulnessVerifier()
claims = [Claim(text='The delivery rider hit a pedestrian at Marina Bay.')]
ctx = [{'corpus_id':'t1','text':'A rider collided with a pedestrian in Marina Bay.'}]
print(v.verify(claims, ctx).model_dump_json(indent=2))
"
```

Expected: `entailed >= 1`, `faithfulness_score == 1.0`.

---

## Task 9 — Citation verifier (upgrade #3b)

**Goal.** Given a `ModelAnswer`, check every `IRACStep.citations[].corpus_id`
exists in the corpus and its topic tags overlap the step's issue. Produce a
`CitationReport`.

### Files to create/edit

- **NEW** `src/services/verification/citation_verifier.py`
- **EDIT** `src/services/verification/__init__.py` — export
  `CitationVerifier`, `citation_verifier`.
- **EDIT** `src/services/hypothetical_service.py::_generate_model_answer` — when
  the model answer is structured (`ModelAnswer`), call the verifier and attach
  the result to `response.validation_results["citation"]`.
- **NEW** `tests/test_services/test_citation_verifier.py`.

### Module skeleton

```python
# src/services/verification/citation_verifier.py
from __future__ import annotations

from typing import Any, Iterable

import structlog

from ..prompt_engineering.schemas import (
    CitationReport, CorpusRef, IRACStep, ModelAnswer,
)

logger = structlog.get_logger(__name__)


class CitationVerifier:
    def __init__(self) -> None:
        self._corpus_index: dict[str, dict[str, Any]] | None = None
        self._authorities_index: dict[str, dict[str, Any]] | None = None

    async def _ensure_index(self, corpus_pack: str = "sg_tort") -> None:
        if self._corpus_index is not None:
            return
        from ..corpus_service import corpus_service
        entries = await corpus_service.load_corpus(corpus_pack=corpus_pack)
        self._corpus_index = {
            e.id: {"topics": set(e.topics), "text": e.text}
            for e in entries if e.id
        }
        import json, pathlib
        auth_path = pathlib.Path(
            f"corpus/packs/{corpus_pack}/authorities.json"
        )
        if auth_path.exists():
            data = json.loads(auth_path.read_text(encoding="utf-8"))
            self._authorities_index = {
                a["id"]: {"topics": set(a.get("topics", [])),
                          "citation": a.get("citation", "")}
                for a in data.get("authorities", [])
            }
        else:
            self._authorities_index = {}

    async def verify_model_answer(
        self, answer: ModelAnswer, corpus_pack: str = "sg_tort"
    ) -> CitationReport:
        await self._ensure_index(corpus_pack)
        total = verified = 0
        unknown: list[str] = []
        topic_mismatch: list[dict[str, Any]] = []
        for step in answer.steps:
            step_topic = _issue_to_topic(step.issue)
            for ref in step.citations:
                total += 1
                if ref.corpus_id in (self._corpus_index or {}):
                    entry_topics = self._corpus_index[ref.corpus_id]["topics"]
                    if not step_topic or step_topic in entry_topics:
                        verified += 1
                    else:
                        topic_mismatch.append({
                            "corpus_id": ref.corpus_id,
                            "step_topic": step_topic,
                            "corpus_topics": sorted(entry_topics),
                        })
                elif ref.authority_id and ref.authority_id in (
                    self._authorities_index or {}
                ):
                    verified += 1
                else:
                    unknown.append(ref.corpus_id)
        accuracy = verified / total if total else 1.0
        return CitationReport(
            citation_accuracy=accuracy,
            total_citations=total,
            verified=verified,
            unknown_corpus_ids=unknown,
            topic_mismatch=topic_mismatch,
        )


def _issue_to_topic(issue: str) -> str | None:
    # Heuristic: match against the SG-tort taxonomy topic keys.
    from ...domain import get_topic_keys
    topics = get_topic_keys("sg_tort")
    lowered = issue.lower()
    for topic in topics:
        alias = topic.replace("_", " ")
        if alias in lowered or topic in lowered:
            return topic
    return None


citation_verifier = CitationVerifier()
__all__ = ["CitationVerifier", "citation_verifier"]
```

(If `src.domain.get_topic_keys` doesn't exist, resolve topics via
`corpus/packs/{pack}/manifest.json['taxonomy']['topics'][*].key`.)

### Verification

```
pytest -q tests/test_services/test_citation_verifier.py
```

Manual:

```
python -c "
import asyncio, json
from src.services.verification.citation_verifier import citation_verifier
from src.services.prompt_engineering.schemas import (
    ModelAnswer, IRACStep, CorpusRef)

async def main():
    answer = ModelAnswer(
        steps=[IRACStep(
            issue='Did the defendant owe a duty of care?',
            rule='Applying Spandeck two-stage test...',
            application='Facts show foreseeability and proximity...',
            conclusion='A duty of care was owed.',
            citations=[CorpusRef(corpus_id='sg_tort_neg_001',
                                 authority_id='spandeck_2007')],
        )],
        overall_conclusion='The defendant is liable in negligence.',
    )
    report = await citation_verifier.verify_model_answer(answer)
    print(report.model_dump_json(indent=2))

asyncio.run(main())
"
```

Expected: `citation_accuracy >= 0.5` (depends on corpus_id presence — the
`sg_tort_neg_001` etc. ids are placeholders in the eval JSONL; use real corpus
ids from `corpus/labelled/sg_tort/corpus.json` for the test).

### Dependencies

- Structured `ModelAnswer` shape from the completed structured decoding adapter.
- Existing `corpus_service.load_corpus()` returns `HypotheticalEntry` with
  `.id` and `.topics` — no changes needed there.

---

## Task 10 — Self-refine loop (upgrade #3c)

**Goal.** Bounded (default 2 iterations) refine loop that consumes rule-based
validation, ML gate, faithfulness report, and citation report; if any
`RefineCritique.is_blocking()` returns True, feed a structured critique back to
the LLM under a `revise` template. Persist every iteration to
`data/generated/refine_traces/<generation_id>.jsonl`.

### Files to create/edit

- **NEW** `src/services/refine_loop.py`
- **EDIT** `src/services/hypothetical_service.py` — replace the ad-hoc
  "auto_regeneration" block (~line 583) with a call to `RefineLoop.run(...)`.
  The ML-gate retry (already shipped) becomes iteration 0 of this loop.
- **NEW** `src/services/prompt_engineering/templates.py` — add
  `format_revise_prompt(context, prior_draft, critique) -> str`.
- **NEW** `tests/test_services/test_refine_loop.py`.

### Module skeleton

```python
# src/services/refine_loop.py
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

import structlog

from ..config import settings
from .prompt_engineering.schemas import (
    FaithfulnessReport, CitationReport, RefineCritique,
)

logger = structlog.get_logger(__name__)


@dataclass
class RefineResult:
    hypothetical: str
    iterations: int
    final_critique: RefineCritique
    trace: list[dict[str, Any]]


class RefineLoop:
    def __init__(
        self,
        generate: Callable[[str], Awaitable[str]],
        rule_based_validate: Callable[[str], Awaitable[dict[str, Any]]],
        nli_verify: Callable[[str], Awaitable[FaithfulnessReport | None]] | None = None,
        citation_verify: Callable[[str], Awaitable[CitationReport | None]] | None = None,
        ml_gate_check: Callable[[str], dict[str, Any]] | None = None,
        max_iterations: int | None = None,
        trace_path: Path | None = None,
    ) -> None:
        self.generate = generate
        self.rule_based_validate = rule_based_validate
        self.nli_verify = nli_verify
        self.citation_verify = citation_verify
        self.ml_gate_check = ml_gate_check
        self.max_iterations = max_iterations or settings.refine_max_iterations
        self.trace_path = trace_path

    async def run(self, initial_draft: str, revise_prompt_builder) -> RefineResult:
        trace: list[dict[str, Any]] = []
        current = initial_draft
        final_critique: RefineCritique | None = None
        for iteration in range(self.max_iterations + 1):  # 0 = initial
            rb = await self.rule_based_validate(current)
            faith = await self.nli_verify(current) if self.nli_verify else None
            cite = await self.citation_verify(current) if self.citation_verify else None
            gate = self.ml_gate_check(current) if self.ml_gate_check else {}
            critique = RefineCritique(
                iteration=iteration,
                missing_topics=list(rb.get("missing_topics", [])),
                ml_gate=gate,
                faithfulness=faith,
                citation=cite,
                rule_based=rb,
            )
            trace.append({
                "iteration": iteration,
                "draft_prefix": current[:200],
                "critique": critique.model_dump(),
                "timestamp": time.time(),
            })
            final_critique = critique
            if not critique.is_blocking() or iteration >= self.max_iterations:
                break
            revise_prompt = revise_prompt_builder(current, critique)
            current = await self.generate(revise_prompt)
        if self.trace_path:
            self.trace_path.parent.mkdir(parents=True, exist_ok=True)
            with self.trace_path.open("w", encoding="utf-8") as f:
                for row in trace:
                    f.write(json.dumps(row) + "\n")
        return RefineResult(
            hypothetical=current,
            iterations=len(trace) - 1,
            final_critique=final_critique or RefineCritique(iteration=0),
            trace=trace,
        )
```

### Revise prompt template

Add to `src/services/prompt_engineering/templates.py`:

```python
def format_revise_prompt(
    context: PromptContext,
    prior_draft: str,
    critique: "RefineCritique",
) -> str:
    fb: list[str] = []
    if critique.missing_topics:
        fb.append("Ensure the following topics are explicitly addressed: "
                  + ", ".join(critique.missing_topics) + ".")
    if critique.faithfulness and critique.faithfulness.faithfulness_score < 0.7:
        unverif = [
            v.claim.text for v in critique.faithfulness.verdicts
            if v.verdict != "entailment"
        ][:5]
        fb.append("Remove or ground the following unsupported claims: "
                  + " | ".join(unverif))
    if critique.citation and critique.citation.citation_accuracy < 0.6:
        fb.append("Fix invalid citations: unknown corpus IDs "
                  + str(critique.citation.unknown_corpus_ids))
    if critique.ml_gate and not critique.ml_gate.get("passed", True):
        low = [
            t for t, c in (critique.ml_gate.get("per_topic") or {}).items()
            if float(c) < critique.ml_gate.get("threshold", 0.4)
        ]
        fb.append("Increase explicit treatment of: " + ", ".join(low))
    base = format_prompt(context)  # existing method
    return (
        base
        + "\n\n---\nPrior draft:\n" + prior_draft
        + "\n\n---\nCritique to address:\n"
        + "\n".join(f"- {line}" for line in fb)
        + "\n\nProduce a revised hypothetical that addresses every point above."
    )
```

### Integration

Replace the existing `_should_retry_for_realism_gate` block in
`hypothetical_service.py:583-618` with:

```python
from .refine_loop import RefineLoop
from pathlib import Path

loop = RefineLoop(
    generate=lambda p: self._generate_hypothetical_text_from_prompt(request, p),
    rule_based_validate=lambda t: self._rule_based_validate_dict(request, t, context_entries),
    nli_verify=lambda t: self._nli_verify(t, context_entries) if settings.nli_verifier_enabled else None,
    citation_verify=None,  # only relevant for model_answer; hypothetical has no citations yet
    ml_gate_check=lambda t: self._ml_gate_check(request, t),
    max_iterations=settings.refine_max_iterations,
    trace_path=Path(settings.refine_trace_dir) / f"{correlation_id}.jsonl",
)
refine_result = await loop.run(
    initial_draft=hypothetical,
    revise_prompt_builder=lambda draft, crit: (
        prompt_manager.format_revise_prompt(prompt_context, draft, crit)
    ),
)
hypothetical = refine_result.hypothetical
refine_metadata = {
    "iterations": refine_result.iterations,
    "final_critique": refine_result.final_critique.model_dump(),
}
```

Add helper methods:

- `_generate_hypothetical_text_from_prompt(request, prompt)` — thin wrapper that
  calls `llm_service.generate` with the caller-supplied prompt (bypasses
  `format_prompt`); needed so the refine loop can pass its own revise prompt.
- `_rule_based_validate_dict(request, text, context_entries)` — wraps the
  existing `_validate_hypothetical` and returns a plain dict shape the loop
  understands, plus a `missing_topics` list computed from
  `validation_service.get_missing_topics(text, request.topics)`.

Attach `refine_metadata` to `response.metadata["refine"]`.

### Verification

```
pytest -q tests/test_services/test_refine_loop.py
ls data/generated/refine_traces/
```

Expected: at least one `.jsonl` trace file per generated hypothetical when
gate/faithfulness fails.

### Dependencies

- Tasks 7, 8, 9. This is the last piece of upgrade #3.

---

## Task 11 — Extend evaluators (upgrade #4a)

**Goal.** Add 7 new evaluators to `src/evals/evaluators.py`. Keep existing
evaluators (`contains`, `has_citation`, `min_length`, `is_string`,
`has_sg_citation`, `cites_sg_statute`, `uses_sal_style`,
`tort_element_coverage`) unchanged.

### New evaluators to add

Every new evaluator lives in `src/evals/evaluators.py` and is registered in
the `EVALUATORS` dict at the bottom of that file. Each subclasses
`BaseEvaluator` and implements `async def evaluate(ctx: EvaluatorContext) -> EvaluatorResult`.

1. `RetrievalRecallAtK` — name = `"retrieval_recall_at_k"`.
   - `ctx.case.expected_output["relevant_corpus_ids"]` = gold list
   - `ctx.case.metadata["retrieved_ids"]` (populated by task runner) = top-k retrieved
   - `k = ctx.case.expected_output.get("recall_k", 5)`
   - score = `|gold ∩ top_k| / |gold|`

2. `RetrievalMRR` — name = `"retrieval_mrr"`.
   - Reciprocal rank of first gold id in retrieved list, or 0 if none.

3. `RetrievalNDCG` — name = `"retrieval_ndcg"`.
   - Binary relevance: `rel[i] = 1 if retrieved[i] in gold else 0`
   - `DCG = Σ rel[i] / log2(i+2)` for i in [0, k)
   - `IDCG` = same formula with `min(k, len(gold))` ones at the top
   - `nDCG = DCG / IDCG` (0.0 if IDCG == 0)

4. `RAGASFaithfulness` — name = `"ragas_faithfulness"`.
   - Consumes `ctx.case.metadata["faithfulness_report"]` (populated by the
     runner via the NLI verifier).
   - `score = faithfulness_score` from the report; passed at ≥ 0.7.

5. `CitationAccuracy` — name = `"citation_accuracy"`.
   - Consumes `ctx.case.metadata["citation_report"]`.
   - `score = citation_accuracy`; passed at ≥ 0.6.

6. `HallucinationProfile` — name = `"hallucination_profile"`.
   - Dahl-style: from the faithfulness report, compute
     `unverifiable_fraction = unverifiable / total_claims`. Score is
     `1.0 - unverifiable_fraction`. Passed at ≥ 0.7.

7. `IRACCompleteness` — name = `"irac_completeness"`.
   - Consumes `ctx.case.metadata["model_answer"]` (structured `ModelAnswer`
     dict).
   - `score = fraction of steps that have non-empty issue+rule+application+
     conclusion AND at least one citation`. Passed at ≥ 0.8.

### Reference code excerpt

```python
class RetrievalRecallAtK(BaseEvaluator):
    name = "retrieval_recall_at_k"

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluatorResult:
        gold = set(ctx.case.expected_output.get("relevant_corpus_ids", []))
        retrieved = list(ctx.case.metadata.get("retrieved_ids", []))
        k = int(ctx.case.expected_output.get("recall_k", 5))
        if not gold:
            return self.result(1.0, details={"reason": "no_gold"})
        top_k = retrieved[:k]
        hit = len(gold & set(top_k))
        return self.result(
            hit / len(gold),
            details={"k": k, "hit": hit, "gold_size": len(gold),
                     "retrieved_top_k": top_k},
        )
```

### Register + export

At the bottom of `src/evals/evaluators.py`:

```python
EVALUATORS.update({
    "retrieval_recall_at_k": RetrievalRecallAtK(),
    "retrieval_mrr": RetrievalMRR(),
    "retrieval_ndcg": RetrievalNDCG(),
    "ragas_faithfulness": RAGASFaithfulness(),
    "citation_accuracy": CitationAccuracy(),
    "hallucination_profile": HallucinationProfile(),
    "irac_completeness": IRACCompleteness(),
})
__all__ = list(EVALUATORS.keys()) + ["BaseEvaluator", "EvaluatorContext"]
```

### Runner side-channel

The evaluator loop in `src/evals/runner.py` currently only sees
`(case, output)`. To feed retrieval/faithfulness/citation info into evaluators,
extend `_run_case` to populate `case.metadata` **in place** before evaluators
run, based on task-produced side-channel data. The task functions in `tasks.py`
should be extended (task 12 below) to attach these to `case.metadata` when the
task type is `jikai_eval_v1`.

### Verification

```
pytest -q tests/test_evals/
```

Add fixture cases in `tests/test_evals/test_evaluators_new.py` that provide
canned retrieved_ids / faithfulness_report / citation_report and assert
expected scores.

### Dependencies

- Tasks 8, 9 for the runtime hooks that populate metadata.

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

1. **Task 8** — NLI faithfulness verifier.
2. **Task 9** — citation verifier.
3. **Task 10** — refine loop (composes structured drafts + 8 + 9).
4. **Task 11** — extend evaluators.
5. **Task 12** — JSONL loader + `jikai_eval_v1` task.
6. **Task 13** — benchmark runner + ablation script.
7. **Task 14** — research writeup + README rewrite.
8. **CI/reqs** — cross-cutting; last (after real deps are settled).

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
