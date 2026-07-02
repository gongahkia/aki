# Roadmap

## Limitations

- Current checked-in metrics are dry-run smoke outputs because [`docs/evals/results_v1.json`](../docs/evals/results_v1.json) and [`docs/evals/ablations_v1.json`](../docs/evals/ablations_v1.json) set `"dry_run": true`.
- No blind human evaluation artifact is linked from these research notes yet.
- No public LegalBench-RAG, LexRAG, or LRAGE comparison run is recorded for Jikai.
- The SG tort corpus remains the only documented reference pack in these results.
- [Inference] Citation accuracy depends on corpus and authority coverage, so higher coverage should improve the verifier's ceiling.
- [Inference] NLI faithfulness depends on verifier model availability and retrieved-context quality.

## Next Work

1. Replace dry-run fixture values with real benchmark runs from `script/run_jikai_eval.py`.
2. Add a blind human evaluation set for SG tort hypotheticals and model answers.
3. Add source-span labels for retrieval evaluation in the style of LegalBench-RAG.
4. Report confidence intervals or bootstrap variance for leaderboard metrics.
5. Expand corpus packs only after source rights and redistribution constraints are recorded.
6. Compare baseline, structured, refine, SetFit, and combined scenarios with the same provider/model seed policy.
7. Publish failure taxonomies for hallucinations, citation misses, and IRAC omissions.
