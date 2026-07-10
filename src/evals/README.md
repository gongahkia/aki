# Jikai Evals

Local SG-LegalBench harness using Elefant's dataset shape:

```yaml
cases:
  - name: unique_case_name
    inputs: {}
    expected_output: {}
    metadata:
      jurisdiction: SG
```

Run:

```bash
python -m src.evals.run --workflow sg_tort_hypothetical --dataset sg_tort.yaml
make eval DATASET=sg_tort.yaml
```

Registered workflows:

- `sg_tort_hypothetical`
- `sg_citation_retrieval`
- `sg_statute_interpretation_mcq`
- `sg_factual_reasoning`

Registered evaluators:

- `contains`
- `has_citation`
- `min_length`
- `is_string`
- `has_sg_citation`
- `cites_sg_statute`
- `uses_sal_style`
- `tort_element_coverage`

Results use `schema_version: jikai.eval.v1` for downstream leaderboard ingestion.

Current leaderboard and ablation artifacts are dry-run smoke metrics. They are not human-rated student-utility evidence and must stay labeled as dry-run until the 30-item SG Tort blind evaluation has at least two independent law-trained raters per item and reports inter-rater agreement.
