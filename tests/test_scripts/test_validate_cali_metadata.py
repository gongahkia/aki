import json

from script.validate_cali_metadata import DEFAULT_PATH, validate_cali_metadata


def test_validate_cali_metadata_accepts_link_only_records():
    assert validate_cali_metadata(DEFAULT_PATH) == []


def test_validate_cali_metadata_rejects_committed_text(tmp_path):
    records = json.loads(DEFAULT_PATH.read_text(encoding="utf-8"))
    records[0]["text"] = "copied CALI text"
    path = tmp_path / "metadata.json"
    path.write_text(json.dumps(records), encoding="utf-8")

    errors = validate_cali_metadata(path)

    assert any("must not commit CALI text" in error for error in errors)
