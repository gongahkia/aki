# Jikai Eval Leaderboard

**DRY-RUN ONLY.** These rows are automated smoke metrics, not human-rated student-utility results. They cannot support public quality, bar-prep, or product-comparison claims until replaced by the 30-item SG Tort blind evaluation with independent law-trained raters.

| Provider | Retrieval | Backend | R@5 | MRR | Faithfulness | Citation | IRAC | Hallucination |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ollama | hybrid | refine | 0.770 | 0.650 | 0.810 | 0.760 | 0.730 | 0.850 |
| ollama | dense | refine | 0.730 | 0.610 | 0.770 | 0.720 | 0.690 | 0.810 |
| ollama | hybrid | structured | 0.710 | 0.590 | 0.750 | 0.700 | 0.670 | 0.790 |
| ollama | bm25 | refine | 0.700 | 0.580 | 0.740 | 0.690 | 0.660 | 0.780 |
| ollama | dense | structured | 0.670 | 0.550 | 0.710 | 0.660 | 0.630 | 0.750 |
| ollama | hybrid | baseline | 0.650 | 0.530 | 0.690 | 0.640 | 0.610 | 0.730 |
| ollama | bm25 | structured | 0.640 | 0.520 | 0.680 | 0.630 | 0.600 | 0.720 |
| ollama | dense | baseline | 0.610 | 0.490 | 0.650 | 0.600 | 0.570 | 0.690 |
| ollama | bm25 | baseline | 0.580 | 0.460 | 0.620 | 0.570 | 0.540 | 0.660 |
