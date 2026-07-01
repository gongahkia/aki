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
