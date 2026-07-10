from fastapi.testclient import TestClient

from src.api.main import create_app


def test_corpus_packs_endpoint_lists_common_law_comparators():
    client = TestClient(create_app())

    response = client.get("/corpus/packs")

    assert response.status_code == 200
    packs = {pack["key"]: pack for pack in response.json()["packs"]}
    assert {"sg_tort", "us_tort", "uk_tort"} <= set(packs)
    assert packs["sg_tort"]["jurisdiction"] == "sg"
    assert packs["us_tort"]["jurisdiction"] == "us"
    assert packs["uk_tort"]["jurisdiction"] == "uk"
    assert packs["us_tort"]["corpus_path"] == "corpus/clean/us_tort/corpus.json"
    assert packs["uk_tort"]["corpus_path"] == "corpus/clean/uk_tort/corpus.json"
    assert "cap_static_case_json" in packs["us_tort"]["source_ids"]
    assert "tna_find_case_law_xml" in packs["uk_tort"]["source_ids"]


def test_corpus_topics_endpoint_honors_explicit_pack_scope():
    client = TestClient(create_app())

    response = client.get(
        "/corpus/topics",
        params={"corpus_pack": "uk_tort", "jurisdiction": "uk", "subject": "tort"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["corpus_pack"] == "uk_tort"
    assert payload["jurisdiction"] == "uk"
    assert "vicarious_liability" in payload["topics"]
