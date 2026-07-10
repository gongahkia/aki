# Bar Exam Link Index

Date: 2026-07-10
Issue: #33
Status: metadata-only workflow

## Decision

California, New York, Texas, and NCBE bar exam sources are link-first only. Jikai may commit source metadata, URLs, exam date, jurisdiction, component, subject tags, and PDF hashes. It must not commit question text, selected-answer text, model-answer text, rubrics copied from the source, or PDF-derived excerpts unless `corpus/source_registry.json` changes that source to a full-text-allowed status.

Registered sources:

- `california_bar_past_exams`
- `ny_bole_exam_questions`
- `texas_ble_selected_answers`
- `ncbe_study_aids`

## Crawler

Use:

```console
$ PYTHONPATH=. uv run --python 3.13 python script/build_bar_exam_metadata.py --limit 20
```

The output path is `corpus/metadata/bar_exam_link_index/metadata.json`.

Each record contains:

- `source_id`
- `jurisdiction`
- `component`
- `subject`
- `exam_date`
- `url`
- `pdf_sha256`
- `review_status`
- `manual_review`
- `full_text_commit_allowed=false`
- `text_fields_committed=[]`

## Manual Review

Reviewers may classify records as tort candidates by reading the linked source outside the committed artifact and editing only metadata:

- Set `subject` to `tort` only when the linked PDF is confirmed to be a tort exam/question/answer component.
- Set `manual_review.tort_classification` to `tort` or `not_tort`.
- Fill `manual_review.reviewed_by`, `manual_review.reviewed_at`, and short notes without quoting source text.
- Leave `full_text_commit_allowed=false`.
- Leave `text_fields_committed=[]`.

## Validation

Use:

```console
$ PYTHONPATH=. uv run --python 3.13 python script/build_bar_exam_metadata.py --validate-only corpus/metadata/bar_exam_link_index/metadata.json
```

The validator rejects records that include copied prompt, question, answer, model-answer, selected-answer, rubric, content, or text fields.
