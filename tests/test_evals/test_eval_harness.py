import pytest

from src.evals import EvalRequest, run_eval
from src.evals.evaluators import EVALUATORS
from src.evals.runner import load_dataset
from src.evals.tasks import TASKS


def test_task_and_evaluator_registry_meets_sg_legalbench_floor():
    assert len(TASKS) >= 3
    assert len(EVALUATORS) >= 6
    assert "sg_tort_hypothetical" in TASKS
    assert "tort_element_coverage" in EVALUATORS


def test_yaml_dataset_schema_requires_jurisdiction():
    cases = load_dataset("sg_tort.yaml")

    assert cases
    assert cases[0].name
    assert cases[0].inputs
    assert cases[0].expected_output
    assert cases[0].metadata["jurisdiction"] == "SG"


@pytest.mark.asyncio
async def test_run_eval_returns_stable_report_schema():
    report = await run_eval(
        EvalRequest(
            workflow="sg_factual_reasoning",
            dataset="sg_factual_reasoning.yaml",
            evaluators=["contains", "tort_element_coverage"],
            max_concurrency=2,
            batch_id="test-batch",
        )
    )

    assert report.schema_version == "jikai.eval.v1"
    assert report.batch_id == "test-batch"
    assert report.summary.total_cases == 2
    assert report.summary.passed_cases == 2
    assert set(report.summary.evaluator_means) == {"contains", "tort_element_coverage"}
    assert report.cases[0].evaluator_results[0].name == "contains"


@pytest.mark.asyncio
async def test_statute_eval_runs_sg_specific_evaluator():
    report = await run_eval(
        EvalRequest(
            workflow="sg_statute_interpretation_mcq",
            dataset="sg_statute_interpretation.yaml",
            evaluators=["contains", "cites_sg_statute"],
            max_concurrency=1,
            batch_id="statute-test",
        )
    )

    assert report.summary.passed_cases == report.summary.total_cases
    assert report.summary.evaluator_means["cites_sg_statute"] == 1.0
