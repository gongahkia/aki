import pytest

from src.services.entity_validator import EntityConsistencyValidator


def test_entity_validator_extracts_structured_entities():
    text = (
        "Ms Tan Li sued Bright Services Pte Ltd in the High Court on 3 March 2026. "
        "The claim cited Spandeck Engineering v Defence Science [2007] SGCA 37, "
        "s 3 of the Civil Law Act 1909, and S$25,000 in losses near Orchard Road."
    )
    result = EntityConsistencyValidator(current_year=2026).validate(text)

    assert result.passed
    assert any(p.name == "Bright Services Pte Ltd" for p in result.entities.parties)
    assert any(c.citation == "[2007] SGCA 37" for c in result.entities.citations)
    assert any(s.normalized_title == "civil law act" for s in result.entities.statutes)
    assert result.entities.monetary_amounts[0].raw == "S$25,000"
    assert result.entities.dates[0].raw == "3 March 2026"
    assert any(loc.name == "Orchard Road" for loc in result.entities.locations)


def test_entity_validator_flags_future_and_implausible_citation():
    text = "The answer relies on Made Up v Example [2099] SGCA 9999."
    result = EntityConsistencyValidator(current_year=2026).validate(text)

    codes = {issue.code for issue in result.issues}
    assert not result.passed
    assert "future_case_citation" in codes
    assert "implausible_case_number" in codes


def test_entity_validator_flags_unknown_sg_statute():
    text = "The defendant refers to s 12 of the Imaginary Torts Act 2099."
    result = EntityConsistencyValidator(current_year=2026).validate(text)

    assert not result.passed
    assert any(issue.code == "unknown_sg_statute" for issue in result.issues)


@pytest.mark.parametrize(
    "text",
    [
        "A relies on [2099] SGCA 9999.",
        "B cites [2024] SGZZ 12.",
        "C invokes s 1 of the Imaginary Torts Act.",
        "D relies on [2025] SGHC ABC.",
        "E cites [2030] SGDC 44.",
        "F cites [2022] ABCD 99.",
        "G invokes section 9 of the Fake Safety Act.",
        "H relies on [2027] SGCA 1.",
        "I cites [2020] SGHC 1201.",
        "J invokes s 88 of the Nonexistent Liability Act.",
    ],
)
def test_seeded_inconsistencies_are_flagged(text):
    result = EntityConsistencyValidator(current_year=2026).validate(text)

    assert result.issue_count >= 1


def test_seeded_inconsistency_recall_exceeds_90_percent():
    seeded = [
        "A relies on [2099] SGCA 9999.",
        "B cites [2024] SGZZ 12.",
        "C invokes s 1 of the Imaginary Torts Act.",
        "D relies on [2025] SGHC ABC.",
        "E cites [2030] SGDC 44.",
        "F cites [2022] ABCD 99.",
        "G invokes section 9 of the Fake Safety Act.",
        "H relies on [2027] SGCA 1.",
        "I cites [2020] SGHC 1201.",
        "J invokes s 88 of the Nonexistent Liability Act.",
    ]
    validator = EntityConsistencyValidator(current_year=2026)
    flagged = sum(1 for text in seeded if validator.validate(text).issue_count)

    assert flagged / len(seeded) >= 0.9
