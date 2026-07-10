import json

from script.validate_contrib_corpus import (
    DEFAULT_PATH,
    MIN_RECORDS,
    validate_contrib_corpus,
)


def test_validate_contrib_corpus_accepts_authored_sg_tort_pack():
    assert validate_contrib_corpus(DEFAULT_PATH) == []


def test_validate_contrib_corpus_rejects_missing_certification(tmp_path):
    records = json.loads(DEFAULT_PATH.read_text(encoding="utf-8"))[:MIN_RECORDS]
    records[0]["source_exam_context"]["certification"]["no_real_exam_text"] = False
    path = tmp_path / "corpus.json"
    path.write_text(json.dumps(records), encoding="utf-8")

    errors = validate_contrib_corpus(path)

    assert any("no_real_exam_text" in error for error in errors)
