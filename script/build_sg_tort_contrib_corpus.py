"""Build the repository-authored SG Tort contribution corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

OUTPUT_PATH = Path("corpus/contrib/sg_tort/corpus.json")
SOURCE_ID = "sg_tort_authored_contrib"
SOURCE_URL = "file://corpus/contrib/sg_tort/corpus.json"
AUTHORED_DATE = "2026-07-10"

TOPIC_SETS = [
    ["negligence", "duty_of_care", "standard_of_care", "causation"],
    ["negligence", "standard_of_care", "causation", "remoteness"],
    ["negligence", "contributory_negligence", "causation"],
    ["negligence", "consent_defence", "volenti_non_fit_injuria"],
    ["negligence", "illegality_defence", "causation"],
    ["vicarious_liability", "negligence", "standard_of_care"],
    ["private_nuisance", "trespass_to_land"],
    ["private_nuisance", "rylands_v_fletcher", "remoteness"],
    ["defamation", "harassment"],
    ["assault", "battery", "false_imprisonment"],
    ["intentional_infliction_of_mental_harm", "harassment"],
    ["occupiers_liability", "negligence", "duty_of_care"],
    ["employers_liability", "vicarious_liability", "negligence"],
    ["product_liability", "strict_liability", "causation"],
    ["psychiatric_harm", "negligence", "remoteness"],
    ["economic_loss", "negligence", "duty_of_care"],
]

SCENARIOS = [
    {
        "setting": "a community cycling event at East Coast Park",
        "claimant": "Nadia",
        "defendant": "Harbour Events Pte Ltd",
        "actor": "a route marshal",
        "injury": "a wrist fracture and two weeks of lost freelance income",
        "object": "temporary crowd-control barriers",
    },
    {
        "setting": "a robotics demo in a Jurong polytechnic hall",
        "claimant": "Ravi",
        "defendant": "BrightLab Robotics",
        "actor": "a technician",
        "injury": "cuts to the hand and damage to a borrowed laptop",
        "object": "a mobile demonstration robot",
    },
    {
        "setting": "a late-night food delivery route in Tampines",
        "claimant": "Mei Ling",
        "defendant": "SwiftBite Logistics",
        "actor": "a delivery supervisor",
        "injury": "a knee injury and cancelled tuition sessions",
        "object": "an electric delivery bicycle",
    },
    {
        "setting": "a condominium renovation at Bukit Timah",
        "claimant": "Farid",
        "defendant": "StonePeak Contractors",
        "actor": "a site foreman",
        "injury": "smoke inhalation and cracked balcony tiles",
        "object": "stacked renovation materials",
    },
    {
        "setting": "a school fundraising fair in Toa Payoh",
        "claimant": "Priya",
        "defendant": "Northbridge School",
        "actor": "a volunteer coordinator",
        "injury": "burns from spilled soup and counselling expenses",
        "object": "a portable soup warmer",
    },
    {
        "setting": "a mall pop-up clinic at Orchard Road",
        "claimant": "Daniel",
        "defendant": "ClearSkin Medical Group",
        "actor": "a clinic assistant",
        "injury": "facial scarring and anxiety before work presentations",
        "object": "a laser treatment device",
    },
    {
        "setting": "a co-working office near Raffles Place",
        "claimant": "Aisha",
        "defendant": "DeskHive Pte Ltd",
        "actor": "a facilities manager",
        "injury": "a sprained ankle and missed client meetings",
        "object": "a loose floor panel",
    },
    {
        "setting": "a weekend market at Geylang Serai",
        "claimant": "Ken",
        "defendant": "MarketBridge Organisers",
        "actor": "a security officer",
        "injury": "bruising and a panic episode",
        "object": "a temporary queue gate",
    },
    {
        "setting": "a private bus shuttle serving an industrial estate",
        "claimant": "Siti",
        "defendant": "Orbit Shuttle Services",
        "actor": "a bus captain",
        "injury": "neck pain and physiotherapy costs",
        "object": "a malfunctioning bus door",
    },
    {
        "setting": "a rooftop garden launch in Punggol",
        "claimant": "Jonas",
        "defendant": "SkyPatch Residents' Committee",
        "actor": "an event helper",
        "injury": "a shoulder injury and broken camera equipment",
        "object": "unsecured planter boxes",
    },
]

FACT_FRAGMENTS = {
    "negligence": "The organiser controlled the activity and had notice of a foreseeable risk before the incident.",
    "duty_of_care": "The claimant was in the class of people directly exposed to the defendant's operational choices.",
    "standard_of_care": "A low-cost precaution was available, but staff skipped it to keep the schedule moving.",
    "causation": "The hospital note says the harm would probably have been avoided if that precaution had been taken.",
    "remoteness": "The claimant also suffered an unusual follow-on loss after routine treatment was delayed.",
    "contributory_negligence": "The claimant ignored a visible warning and chose the faster route through the risk area.",
    "consent_defence": "The claimant signed a short waiver but says the specific risk was never explained.",
    "volenti_non_fit_injuria": "The defendant argues that the claimant freely accepted the obvious physical risk.",
    "illegality_defence": "At the time, the claimant was using the service to complete an unlawful private errand.",
    "vicarious_liability": "The immediate wrongdoer was carrying out an assigned task, although in a careless way.",
    "private_nuisance": "Noise, fumes, or vibration repeatedly interfered with neighbouring property use.",
    "trespass_to_land": "Workers crossed a marked boundary and placed equipment on the claimant's land without consent.",
    "rylands_v_fletcher": "The defendant stored a large quantity of material that escaped from the premises.",
    "defamation": "A message naming the claimant was posted in a residents' chat and repeated by others.",
    "harassment": "The messages continued after the claimant asked for them to stop.",
    "assault": "The actor raised a hand tool and threatened immediate force at close range.",
    "battery": "The actor then made deliberate physical contact while moving the claimant aside.",
    "false_imprisonment": "The claimant was kept in a locked room and told they could not leave until a bag search ended.",
    "intentional_infliction_of_mental_harm": "The actor knew the claimant was vulnerable and used threats calculated to cause distress.",
    "occupiers_liability": "The defendant controlled the premises and knew visitors would pass through the hazard.",
    "employers_liability": "The employee says training was rushed and protective equipment was unavailable.",
    "product_liability": "The item failed during ordinary use even though it had been marketed as safe for that use.",
    "strict_liability": "The claimant frames the claim around risk allocation rather than personal fault.",
    "psychiatric_harm": "The claimant seeks recovery for a recognised psychiatric condition after witnessing the event.",
    "economic_loss": "Most of the claimed loss is lost profit unconnected to physical damage.",
}

ISSUES = {
    "negligence": "Negligence: duty, breach, damage, causation, and defences.",
    "duty_of_care": "Duty of care: proximity, foreseeability, and policy limits.",
    "standard_of_care": "Standard of care: reasonable precautions, risk magnitude, and burden of prevention.",
    "causation": "Causation: factual causation, scope of liability, and intervening acts.",
    "remoteness": "Remoteness: whether the kind of harm was reasonably foreseeable.",
    "contributory_negligence": "Contributory negligence: claimant fault and apportionment.",
    "consent_defence": "Consent: scope and quality of consent to the risk.",
    "volenti_non_fit_injuria": "Volenti: whether acceptance of risk was free, full, and voluntary.",
    "illegality_defence": "Illegality: connection between the wrong and the claim.",
    "vicarious_liability": "Vicarious liability: employment relationship and close connection.",
    "private_nuisance": "Private nuisance: substantial interference with land use.",
    "trespass_to_land": "Trespass to land: direct unauthorised entry or placement.",
    "rylands_v_fletcher": "Escape-based liability: accumulation, escape, and foreseeability.",
    "defamation": "Defamation: publication, reference, defamatory meaning, and defences.",
    "harassment": "Harassment: course of conduct and alarm or distress.",
    "assault": "Assault: reasonable apprehension of immediate unlawful force.",
    "battery": "Battery: intentional direct physical contact without lawful basis.",
    "false_imprisonment": "False imprisonment: total restraint without lawful justification.",
    "intentional_infliction_of_mental_harm": "Intentional mental harm: intention, vulnerability, causation, and damage.",
    "occupiers_liability": "Occupiers' liability: control, visitor status, and premises hazard.",
    "employers_liability": "Employers' liability: safe system, training, and equipment.",
    "product_liability": "Product liability: defect, ordinary use, and causal link.",
    "strict_liability": "Strict liability: whether fault need not be proved for the pleaded route.",
    "psychiatric_harm": "Psychiatric harm: recognised illness, proximity, and remoteness.",
    "economic_loss": "Economic loss: pure loss limits and assumption of responsibility.",
}


def _hash_record(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _difficulty(index: int, topics: list[str]) -> str:
    if len(topics) >= 4 or index % 5 == 0:
        return "hard"
    if len(topics) == 3 or index % 3 == 0:
        return "medium"
    return "easy"


def _time_limit(difficulty: str) -> int:
    return {"easy": 20, "medium": 30, "hard": 45}[difficulty]


def _record(index: int) -> dict[str, Any]:
    topics = TOPIC_SETS[(index - 1) % len(TOPIC_SETS)]
    scenario = SCENARIOS[(index - 1) % len(SCENARIOS)]
    variant = (index - 1) // len(TOPIC_SETS) + 1
    claimant = (
        f"{scenario['claimant']} {variant}" if variant > 1 else scenario["claimant"]
    )
    question_prompt = (
        f"Advise {claimant} on possible tort claims and defences under Singapore law."
    )
    fragments = " ".join(FACT_FRAGMENTS[topic] for topic in topics)
    fact_pattern = (
        f"At {scenario['setting']}, {claimant} attended as a visitor or customer. "
        f"{scenario['defendant']} assigned {scenario['actor']} to manage "
        f"{scenario['object']}. {fragments} {claimant} suffered "
        f"{scenario['injury']}. A later internal note records that staff had discussed "
        f"the risk earlier that week, but no one escalated it before the event."
    )
    issues_expected = [ISSUES[topic] for topic in topics]
    difficulty = _difficulty(index, topics)
    core_payload = {
        "id": f"sg_tort:contrib_{index:03d}",
        "text": f"{question_prompt}\n\n{fact_pattern}",
        "topics": topics,
        "question_prompt": question_prompt,
        "fact_pattern": fact_pattern,
        "issues_expected": issues_expected,
        "model_answer": (
            "A strong answer should identify the pleaded torts, separate primary "
            "liability from defences, apply each issue to the concrete facts, and "
            "state where further evidence is needed."
        ),
        "marking_rubric": {
            "issue_spotting": 4,
            "rule_accuracy": 4,
            "fact_application": 6,
            "defences": 3,
            "structure": 3,
        },
        "difficulty": difficulty,
        "time_limit_minutes": _time_limit(difficulty),
        "jurisdiction_notes": (
            "Singapore tort practice hypo; authorities must be checked during review."
        ),
        "answer_visibility": "hidden",
        "source_exam_context": {
            "source_type": "repo_authored_submission",
            "authorship_basis": "repository_authored_original",
            "contributor_role": "project",
            "review_status": "reviewed",
            "certification": {
                "certified_by": "project",
                "certified_at": AUTHORED_DATE,
                "originality_certified": True,
                "permission_certified": True,
                "no_real_exam_text": True,
                "no_personal_data": True,
            },
        },
        "corpus_pack_key": "sg_tort",
        "jurisdiction": "sg",
        "subject": "tort",
        "subtopics": [],
        "source": {
            "source_id": SOURCE_ID,
            "url": SOURCE_URL,
            "source_format": "json",
            "access": "local_repo",
            "authorship": "repository_authored_original",
        },
        "provenance": {
            "source_url": SOURCE_URL,
            "authored_at": AUTHORED_DATE,
            "reviewed_at": AUTHORED_DATE,
            "review_status": "reviewed",
        },
        "license": {
            "name": "repository_authored_contribution",
            "url": None,
            "redistribution_status": "bundled_fixture",
            "attribution_required": False,
            "commercial_use": "allowed_by_project_contribution_certification",
            "terms_notes": (
                "Original repository-authored practice hypo; no third-party exam text."
            ),
        },
        "metadata": {
            "source_id": SOURCE_ID,
            "batch": "sg_tort_contrib_v1",
            "authorship_basis": "repository_authored_original",
        },
        "created_at": AUTHORED_DATE,
        "updated_at": AUTHORED_DATE,
    }
    core_payload["provenance"]["record_hash"] = _hash_record(
        {
            "id": core_payload["id"],
            "text": core_payload["text"],
            "topics": core_payload["topics"],
            "issues_expected": core_payload["issues_expected"],
        }
    )
    return core_payload


def build_records(count: int = 80) -> list[dict[str, Any]]:
    return [_record(index) for index in range(1, count + 1)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--count", type=int, default=80)
    args = parser.parse_args()

    records = build_records(args.count)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(records, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(records)} records to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
