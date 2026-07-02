import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.evals.models import EvalCase
from src.evals.runner import load_dataset, resolve_dataset_path
from src.evals.tasks import TASKS, jikai_eval_v1_task


def _case() -> EvalCase:
    return EvalCase(
        name="eval-case",
        inputs={
            "topics": ["negligence"],
            "num_parties": 2,
            "complexity": 2,
            "query": "delivery rider pedestrian",
            "top_k": 2,
            "retrieval_mode": "hybrid",
        },
        expected_output={"relevant_corpus_ids": ["c1"], "recall_k": 2},
        metadata={"jurisdiction": "sg"},
    )


def test_jsonl_loader_resolves_corpus_eval_dataset():
    path = resolve_dataset_path("sg_tort_v1.jsonl")
    cases = load_dataset("sg_tort_v1.jsonl")

    assert path.name == "sg_tort_v1.jsonl"
    assert cases
    assert cases[0].metadata["jurisdiction"] == "sg"


@pytest.mark.asyncio
async def test_jikai_eval_v1_task_populates_metadata(monkeypatch):
    corpus_module = importlib.import_module("src.services.corpus_service")
    hypo_module = importlib.import_module("src.services.hypothetical_service")
    vector_module = importlib.import_module("src.services.vector_service")

    case = _case()
    corpus_entry = SimpleNamespace(
        id="c1",
        text="A rider collided with a pedestrian.",
        topics=["negligence"],
        corpus_pack_key="sg_tort",
        jurisdiction="sg",
        subject="tort",
        subtopics=[],
        metadata={},
    )
    monkeypatch.setattr(
        corpus_module.corpus_service,
        "load_corpus",
        AsyncMock(return_value=[corpus_entry]),
    )
    monkeypatch.setattr(
        vector_module.vector_service,
        "hybrid_search",
        AsyncMock(
            return_value=[
                {
                    "id": "c1",
                    "text": "A rider collided with a pedestrian.",
                    "topics": ["negligence"],
                }
            ]
        ),
    )
    response = SimpleNamespace(
        hypothetical="The rider hit a pedestrian.",
        model_answer=(
            "Issue 1: Negligence\n"
            "Rule: Duty and breach.\n"
            "Application: Apply facts.\n"
            "Conclusion: Claim succeeds.\n"
            "Citations: c1\n\n"
            "Overall conclusion: liable"
        ),
        validation_results={
            "faithfulness": {
                "faithfulness_score": 1.0,
                "total_claims": 1,
                "entailed": 1,
                "contradicted": 0,
                "unverifiable": 0,
            },
            "citation": {
                "citation_accuracy": 1.0,
                "total_citations": 1,
                "verified": 1,
                "unknown_corpus_ids": [],
                "topic_mismatch": [],
            },
        },
    )
    generate = AsyncMock(return_value=response)
    monkeypatch.setattr(
        hypo_module.hypothetical_service,
        "generate_hypothetical",
        generate,
    )

    output = await jikai_eval_v1_task(case)

    assert output == "The rider hit a pedestrian."
    assert case.metadata["retrieved_ids"] == ["c1"]
    assert case.metadata["faithfulness_report"]["faithfulness_score"] == 1.0
    assert case.metadata["citation_report"]["citation_accuracy"] == 1.0
    assert case.metadata["model_answer"]["steps"][0]["citations"] == [
        {"corpus_id": "c1"}
    ]
    request = generate.await_args.args[0]
    assert request.user_preferences["include_model_answer"] is True


def test_jikai_eval_v1_task_registered():
    assert TASKS["jikai_eval_v1"] is jikai_eval_v1_task
