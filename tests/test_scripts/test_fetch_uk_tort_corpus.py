import pytest

from script.fetch_uk_tort_corpus import clean_text, fetch_tna_xml, record_from_tna_xml


MINIMAL_TNA_XML = """\
<akomaNtoso xmlns="http://docs.oasis-open.org/legaldocml/ns/akn/3.0"
  xmlns:uk="https://caselaw.nationalarchives.gov.uk/akn">
  <judgment name="judgment">
    <meta>
      <identification source="#tna">
        <FRBRWork>
          <FRBRuri value="https://caselaw.nationalarchives.gov.uk/id/uksc/2018/4"/>
          <FRBRdate date="2018-02-08" name="judgment"/>
          <FRBRname value="Robinson v Chief Constable of West Yorkshire Police"/>
        </FRBRWork>
        <FRBRManifestation>
          <FRBRdate date="2024-11-10T00:00:00" name="transform"/>
        </FRBRManifestation>
      </identification>
      <proprietary source="#">
        <uk:court>UKSC</uk:court>
        <uk:cite>[2018] UKSC 4</uk:cite>
        <uk:hash>abc123</uk:hash>
      </proprietary>
    </meta>
    <header>
      <neutralCitation>[2018] UKSC 4</neutralCitation>
    </header>
    <judgmentBody>
      <p>Lord Reed gives the judgment.</p>
      <p>The claim concerns negligence and a duty of care.</p>
    </judgmentBody>
  </judgment>
</akomaNtoso>
"""


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
        assert url == "https://caselaw.nationalarchives.gov.uk/example/data.xml"
        return _FakeStreamResponse(self.body)


def test_clean_text_compacts_xml_text_spacing():
    assert clean_text("Alpha   beta\r\n\r\n\r\nGamma") == "Alpha beta\n\nGamma"


def test_record_from_tna_xml_tags_source_license_and_metadata():
    record = record_from_tna_xml(
        MINIMAL_TNA_XML,
        source_url="https://caselaw.nationalarchives.gov.uk/uksc/2018/4/data.xml",
        topics=["duty_of_care", "negligence"],
        subtopics=["public_authority"],
        retrieved_at="2026-07-01",
        max_text_chars=1000,
    )

    assert record["id"] == "uk_tort:tna:id:uksc:2018:4"
    assert record["corpus_pack_key"] == "uk_tort"
    assert record["jurisdiction"] == "uk"
    assert record["source"]["name"] == "The National Archives Find Case Law"
    assert record["source"]["data_url"].endswith("/uksc/2018/4/data.xml")
    assert record["license"]["name"] == "Open Justice Licence v2.0"
    assert record["license"]["redistribution_status"] == "restricted"
    assert record["metadata"]["neutral_citation"] == "[2018] UKSC 4"
    assert record["metadata"]["content_hash"] == "abc123"
    assert record["metadata"]["text_scope"] == "full_text"
    assert "duty of care" in record["text"]


def test_record_from_tna_xml_marks_capped_excerpt():
    record = record_from_tna_xml(
        MINIMAL_TNA_XML,
        source_url="https://caselaw.nationalarchives.gov.uk/uksc/2018/4/data.xml",
        topics=["negligence"],
        retrieved_at="2026-07-01",
        max_text_chars=80,
    )

    assert record["metadata"]["text_scope"] == "capped_excerpt"
    assert record["text"].endswith("[truncated from source]")


def test_record_from_tna_xml_fails_for_invalid_xml():
    with pytest.raises(Exception):
        record_from_tna_xml(
            "<not-xml",
            source_url="https://caselaw.nationalarchives.gov.uk/example/data.xml",
            topics=["negligence"],
            retrieved_at="2026-07-01",
        )


def test_fetch_tna_xml_uses_streaming_retry_helper(tmp_path):
    client = _StreamOnlyClient(MINIMAL_TNA_XML.encode("utf-8"))

    xml_text = fetch_tna_xml(
        client,
        "https://caselaw.nationalarchives.gov.uk/example/data.xml",
        events_path=tmp_path / "events.jsonl",
        health_path=tmp_path / "health.json",
    )

    assert "judgmentBody" in xml_text
    assert client.get_called is False
