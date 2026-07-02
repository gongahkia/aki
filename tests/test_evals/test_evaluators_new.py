import math

import pytest

from src.evals.evaluators import EVALUATORS, EvaluatorContext
from src.evals.models import EvalCase


def _case(*, expected_output=None, metadata=None) -> EvalCase:
    return EvalCase(
        name="case",
        inputs={},
        expected_output=expected_output or {},
        metadata={"jurisdiction": "SG", **(metadata or {})},
    )


@pytest.mark.asyncio
async def test_retrieval_evaluators_score_gold_hits():
    case = _case(
        expected_output={"relevant_corpus_ids": ["c1", "c3"], "recall_k": 3},
        metadata={"retrieved_ids": ["c0", "c1", "c2", "c3"]},
    )
    ctx = EvaluatorContext(case=case, output="")

    recall = await EVALUATORS["retrieval_recall_at_k"].evaluate(ctx)
    mrr = await EVALUATORS["retrieval_mrr"].evaluate(ctx)
    ndcg = await EVALUATORS["retrieval_ndcg"].evaluate(ctx)

    expected_ndcg = (1 / math.log2(3)) / (1 + 1 / math.log2(3))
    assert recall.score == 0.5
    assert mrr.score == 0.5
    assert ndcg.score == pytest.approx(expected_ndcg)
    assert recall.details["retrieved_top_k"] == ["c0", "c1", "c2"]


@pytest.mark.asyncio
async def test_report_based_evaluators_apply_thresholds():
    case = _case(
        metadata={
            "faithfulness_report": {
                "faithfulness_score": 0.75,
                "total_claims": 4,
                "unverifiable": 1,
            },
            "citation_report": {"citation_accuracy": 0.6},
        }
    )
    ctx = EvaluatorContext(case=case, output="")

    faithfulness = await EVALUATORS["ragas_faithfulness"].evaluate(ctx)
    citation = await EVALUATORS["citation_accuracy"].evaluate(ctx)
    hallucination = await EVALUATORS["hallucination_profile"].evaluate(ctx)

    assert faithfulness.score == 0.75
    assert faithfulness.passed is True
    assert citation.score == 0.6
    assert citation.passed is True
    assert hallucination.score == 0.75
    assert hallucination.passed is True


@pytest.mark.asyncio
async def test_irac_completeness_requires_all_step_fields_and_citation():
    case = _case(
        metadata={
            "model_answer": {
                "steps": [
                    {
                        "issue": "Duty",
                        "rule": "Spandeck",
                        "application": "Apply rule",
                        "conclusion": "Duty owed",
                        "citations": [{"corpus_id": "c1"}],
                    },
                    {
                        "issue": "Breach",
                        "rule": "Reasonable care",
                        "application": "",
                        "conclusion": "No breach",
                        "citations": [{"corpus_id": "c2"}],
                    },
                ]
            }
        }
    )
    result = await EVALUATORS["irac_completeness"].evaluate(
        EvaluatorContext(case=case, output="")
    )

    assert result.score == 0.5
    assert result.passed is False
    assert result.details == {"complete_steps": 1, "total_steps": 2}


def test_new_evaluators_are_registered():
    assert {
        "retrieval_recall_at_k",
        "retrieval_mrr",
        "retrieval_ndcg",
        "ragas_faithfulness",
        "citation_accuracy",
        "hallucination_profile",
        "irac_completeness",
    } <= set(EVALUATORS)
