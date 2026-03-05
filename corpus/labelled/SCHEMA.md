# Labelled Corpus CSV Schema

## File: tort_labels.csv

| Column | Type | Description |
|--------|------|-------------|
| id | string | Corpus entry index from corpus.json |
| text | string | Full hypothetical text (quoted) |
| topics | string | Pipe-separated canonical topic names (e.g. `negligence\|duty_of_care`) |
| complexity | int | 1-5 (1=beginner, 5=expert) |
| quality_score | float | 0.0-1.0 overall quality rating |
| structural_elements | string | Pipe-separated elements (e.g. `parties\|scenario\|legal_issues\|analysis`) |
| num_parties | int | Number of distinct parties in the hypothetical |
| case_references | string | Pipe-separated SG case citations (optional) |
