# Results

All metrics below are dry-run smoke metrics because both source files set `"dry_run": true`: [`results_v1.json`](../docs/evals/results_v1.json), [`ablations_v1.json`](../docs/evals/ablations_v1.json). They are useful for schema, runner, and dashboard checks; they are not external benchmark evidence.

## Strongest Current Signal

The strongest checked-in dry-run signal is `ollama` + `hybrid` + `refine` with `0.81` RAGAS-style faithfulness, `0.76` citation accuracy, `0.73` IRAC completeness, and `0.85` hallucination-profile score from [`docs/evals/results_v1.json`](../docs/evals/results_v1.json).

## Leaderboard Dry Run

Source: [`docs/evals/results_v1.json`](../docs/evals/results_v1.json). Dataset: `corpus/eval/sg_tort_v1.jsonl`. Cases per run: `50`.

| Provider | Retrieval | Backend | R@K | MRR | NDCG | Faithfulness | Citation | Hallucination | IRAC |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| ollama | hybrid | baseline | 0.65 | 0.53 | 0.57 | 0.69 | 0.64 | 0.73 | 0.61 |
| ollama | hybrid | structured | 0.71 | 0.59 | 0.63 | 0.75 | 0.70 | 0.79 | 0.67 |
| ollama | hybrid | refine | 0.77 | 0.65 | 0.69 | 0.81 | 0.76 | 0.85 | 0.73 |
| ollama | dense | baseline | 0.61 | 0.49 | 0.53 | 0.65 | 0.60 | 0.69 | 0.57 |
| ollama | dense | structured | 0.67 | 0.55 | 0.59 | 0.71 | 0.66 | 0.75 | 0.63 |
| ollama | dense | refine | 0.73 | 0.61 | 0.65 | 0.77 | 0.72 | 0.81 | 0.69 |
| ollama | bm25 | baseline | 0.58 | 0.46 | 0.50 | 0.62 | 0.57 | 0.66 | 0.54 |
| ollama | bm25 | structured | 0.64 | 0.52 | 0.56 | 0.68 | 0.63 | 0.72 | 0.60 |
| ollama | bm25 | refine | 0.70 | 0.58 | 0.62 | 0.74 | 0.69 | 0.78 | 0.66 |

## Ablation Dry Run

Source: [`docs/evals/ablations_v1.json`](../docs/evals/ablations_v1.json). Provider: `ollama`. Retrieval: `hybrid`. Dataset: `corpus/eval/sg_tort_v1.jsonl`. Cases: `50`.

| Scenario | R@K | MRR | NDCG | Faithfulness | Citation | Hallucination | IRAC | Faithfulness Delta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 0.58 | 0.46 | 0.50 | 0.62 | 0.57 | 0.66 | 0.54 | 0.00 |
| +structured | 0.64 | 0.52 | 0.56 | 0.68 | 0.63 | 0.72 | 0.60 | +0.06 |
| +refine | 0.69 | 0.57 | 0.61 | 0.73 | 0.68 | 0.77 | 0.65 | +0.11 |
| +setfit | 0.63 | 0.51 | 0.55 | 0.67 | 0.62 | 0.71 | 0.59 | +0.05 |
| +all | 0.74 | 0.62 | 0.66 | 0.78 | 0.73 | 0.82 | 0.70 | +0.16 |

## Metric Definitions

- `retrieval_recall_at_k`, `retrieval_mrr`, and `retrieval_ndcg` are implemented in [`src/evals/evaluators.py`](../src/evals/evaluators.py#L228).
- `ragas_faithfulness`, `citation_accuracy`, `hallucination_profile`, and `irac_completeness` are implemented in [`src/evals/evaluators.py`](../src/evals/evaluators.py#L305).
- The eval task is [`jikai_eval_v1_task`](../src/evals/tasks.py#L173).
