import json

import pytest

from script.fetch_us_tort_corpus import clean_text, fetch_cap_case, record_from_cap_case


class _FakeStreamResponse:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def raise_for_status(self):
        return None

    def iter_bytes(self):
        yield self.body


class _StreamOnlyClient:
    get_called = False

    def __init__(self, body: bytes):
        self.body = body

    def get(self, *_args, **_kwargs):
        self.get_called = True
        raise AssertionError("plain get should not be used")

    def stream(self, method, url):
        assert method == "GET"
        assert url == "https://static.case.law/example.json"
        return _FakeStreamResponse(self.body)


def test_clean_text_compacts_spaces_and_blank_lines():
    assert clean_text("Alpha   beta\r\n\r\n\r\nGamma") == "Alpha beta\n\nGamma"


def test_record_from_cap_case_tags_cap_source_and_license():
    payload = {
        "id": 1905144,
        "name": "Helen Palsgraf v. The Long Island Railroad Company",
        "name_abbreviation": "Palsgraf v. Long Island Railroad",
        "decision_date": "1928-05-29",
        "docket_number": "",
        "first_page": "339",
        "last_page": "356",
        "citations": [{"type": "official", "cite": "248 N.Y. 339"}],
        "court": {
            "id": 24653,
            "name": "New York Court of Appeals",
            "name_abbreviation": "N.Y.",
        },
        "jurisdiction": {"id": 1, "name": "N.Y.", "name_long": "New York"},
        "last_updated": "2024-02-27T16:54:33.063604+00:00",
        "provenance": {"source": "Harvard"},
        "casebody": {
            "opinions": [
                {"text": "Cardozo, Ch. J.\nNegligence requires duty to the plaintiff."}
            ]
        },
    }

    record = record_from_cap_case(
        payload,
        source_url="https://static.case.law/ny/248/cases/0339-01.json",
        topics=["duty_of_care", "negligence"],
        subtopics=["foreseeability"],
        retrieved_at="2026-07-01",
    )

    assert record["id"] == "us_tort:cap:1905144"
    assert record["corpus_pack_key"] == "us_tort"
    assert record["jurisdiction"] == "us"
    assert (
        record["source"]["url"] == "https://static.case.law/ny/248/cases/0339-01.json"
    )
    assert record["license"]["name"] == "CC0-1.0"
    assert record["license"]["redistribution_status"] == "allowed"
    assert record["metadata"]["citations"] == ["248 N.Y. 339"]
    assert record["metadata"]["court"]["name"] == "New York Court of Appeals"
    assert (
        record["text"] == "Cardozo, Ch. J.\nNegligence requires duty to the plaintiff."
    )


def test_record_from_cap_case_fails_without_opinion_text():
    with pytest.raises(ValueError, match="no opinion text"):
        record_from_cap_case(
            {"id": 1, "casebody": {"opinions": []}},
            source_url="https://static.case.law/example.json",
            topics=["negligence"],
            retrieved_at="2026-07-01",
        )


def test_fetch_cap_case_uses_streaming_retry_helper(tmp_path):
    client = _StreamOnlyClient(json.dumps({"id": 1}).encode("utf-8"))

    payload = fetch_cap_case(
        client,
        "https://static.case.law/example.json",
        events_path=tmp_path / "events.jsonl",
        health_path=tmp_path / "health.json",
    )

    assert payload == {"id": 1}
    assert client.get_called is False
