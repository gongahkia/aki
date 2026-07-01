"""Run entity consistency validation over local generated hypotheticals."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services.entity_validator import entity_consistency_validator
from src.services.hypo_generator import hypo_generator


TOPIC_SETS = [
    ["negligence"],
    ["negligence", "causation"],
    ["duty_of_care", "standard_of_care"],
    ["private_nuisance", "remoteness"],
    ["battery", "assault"],
]


async def run_smoke(samples: int) -> int:
    failures = 0
    for index in range(samples):
        topics = TOPIC_SETS[index % len(TOPIC_SETS)]
        generated = await hypo_generator.generate(
            topics,
            complexity=2 + (index % 3),
            num_parties=2 + (index % 3),
            max_retries=1,
        )
        result = entity_consistency_validator.validate(
            generated["text"],
            corpus_pack="sg_tort",
            jurisdiction="sg",
            subject="tort",
        )
        if result.issue_count:
            failures += 1
    print(
        f"OK: entity validator processed {samples} generated hypotheticals; "
        f"soft_failures={failures}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=50)
    args = parser.parse_args()
    return asyncio.run(run_smoke(max(1, args.samples)))


if __name__ == "__main__":
    raise SystemExit(main())
