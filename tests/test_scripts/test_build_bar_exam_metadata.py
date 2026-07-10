import hashlib

from script.build_bar_exam_metadata import (
    build_metadata,
    infer_component,
    infer_exam_date,
    infer_subject,
    validate_records,
)
from src.corpus_source_registry import (
    SourceRegistryError,
    assert_derived_metadata_allowed,
    assert_text_commit_allowed,
)


def test_build_metadata_indexes_pdf_links_without_text_fields():
    html = b"""
    <html>
      <a href="/files/july-2024-torts-essay.pdf">July 2024 Torts Essay Questions</a>
      <a href="/files/february-2023-selected-answers.pdf">February 2023 Selected Answers</a>
      <a href="/not-a-pdf">Ignore</a>
    </html>
    """
    pdf = b"pdf bytes"

    def fetch(url):
        if url == "https://www.calbar.ca.gov/admissions/applicant-resources/past-exams":
            return html
        return pdf

    records = build_metadata(
        source_ids=["california_bar_past_exams"],
        fetch=fetch,
        retrieved_at="2026-07-10T00:00:00+00:00",
    )

    assert len(records) == 2
    first = records[0]
    assert first["source_id"] == "california_bar_past_exams"
    assert first["jurisdiction"] == "us-ca"
    assert first["subject"] == "tort"
    assert first["component"] == "essay"
    assert first["exam_date"] == "2024-07"
    assert first["pdf_sha256"] == hashlib.sha256(pdf).hexdigest()
    assert first["full_text_commit_allowed"] is False
    assert first["text_fields_committed"] == []
    assert "text" not in first
    assert validate_records(records) == []


def test_build_metadata_skips_broken_pdf_links():
    html = b"""
    <html>
      <a href="/files/broken.pdf">Broken PDF</a>
      <a href="/files/july-2024-torts-essay.pdf">July 2024 Torts Essay Questions</a>
    </html>
    """

    def fetch(url):
        if url == "https://www.calbar.ca.gov/admissions/applicant-resources/past-exams":
            return html
        if url.endswith("broken.pdf"):
            raise RuntimeError("404")
        return b"ok"

    records = build_metadata(
        source_ids=["california_bar_past_exams"],
        fetch=fetch,
        retrieved_at="2026-07-10T00:00:00+00:00",
    )

    assert len(records) == 1
    assert records[0]["subject"] == "tort"


def test_infer_metadata_from_link_labels():
    assert infer_subject("Torts Essay") == "tort"
    assert infer_subject("Contracts Essay") == "unknown"
    assert infer_component("MPT performance test") == "performance_test"
    assert infer_component("selected answer July 2024") == "sample_answer"
    assert infer_exam_date("February 2025 essays") == "2025-02"
    assert infer_exam_date("archive 2024 questions") == "2024"


def test_validate_records_rejects_committed_text():
    record = {
        "id": "bar_exam:test",
        "source_id": "california_bar_past_exams",
        "jurisdiction": "us-ca",
        "component": "essay",
        "subject": "tort",
        "exam_date": "2024-07",
        "url": "https://example.test/a.pdf",
        "pdf_sha256": "a" * 64,
        "review_status": "needs_manual_subject_review",
        "full_text_commit_allowed": False,
        "text_fields_committed": [],
        "manual_review": {"tort_classification": "unreviewed"},
        "question_prompt": "copied prompt",
    }

    errors = validate_records([record])

    assert any("must not commit question_prompt" in error for error in errors)


def test_bar_exam_sources_are_metadata_only_in_registry():
    for source_id in (
        "california_bar_past_exams",
        "ny_bole_exam_questions",
        "texas_ble_selected_answers",
        "ncbe_study_aids",
    ):
        assert_derived_metadata_allowed(source_id)
        try:
            assert_text_commit_allowed(source_id)
        except SourceRegistryError:
            pass
        else:
            raise AssertionError(f"{source_id} unexpectedly allows text commits")
