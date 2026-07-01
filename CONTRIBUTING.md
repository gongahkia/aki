# Contributing

Start with a small, source-clear contribution. The fastest path is a manifest-only corpus pack PR that proves source legality, taxonomy fit, and local validation before adding ingestion code.

## Corpus Packs

Jikai accepts new jurisdictions and subjects through corpus packs. Start with [docs/corpus-pack-manifest.md](docs/corpus-pack-manifest.md), then copy the SG reference shape from [corpus/packs/sg_tort/manifest.json](corpus/packs/sg_tort/manifest.json).

Required contribution path:

1. Create `corpus/packs/<pack_key>/manifest.json`.
2. Fill in jurisdiction, subject, source URLs, source format, license/terms notes, taxonomy, ingestion command, cleaner command, and validation expectations.
3. Run `python3 script/validate_corpus_pack.py corpus/packs/<pack_key>/manifest.json`.
4. Add or update scraper/cleaner code only when the source terms allow the workflow.
5. Add tests or fixtures that do not depend on paid, private, or non-redistributable text.
6. Open a PR that explains source provenance and redistribution status.

Good first issues use `good-first-corpus` or `good-first-jurisdiction`. A good first PR should be narrow: one source family, one jurisdiction, one subject, and no core retrieval or generation refactor.

## Licensing Rules

Do not commit third-party legal text unless the source terms permit redistribution. This includes paid outlines, casebooks, commercial bar-prep material, proprietary summaries, and scraped full text from sources with restricted or unknown terms.

For restricted or unknown sources, contribute only:

- Manifest metadata.
- Source URLs and terms URLs.
- Scraper or cleaner code.
- Small synthetic fixtures.
- Instructions for users to reproduce the corpus locally.

Every pack must set `license.redistribution_status` to `allowed`, `restricted`, `unknown`, or `bundled_fixture`.

## Source Citation

Every corpus-pack PR must cite:

- Source homepage or collection URL.
- Terms URL.
- License name or terms label.
- Access method: local repo, public web, bulk download, manual, API, or other.
- Redistribution status and reasoning.
- Retrieval date for fetched sources.

If the terms are unclear, set `license.redistribution_status` to `unknown` and do not commit third-party raw or clean text.

## Topic Taxonomy

Topic keys must be lower snake case and stable. Prefer a small taxonomy that can pass validation over a large taxonomy with sparse or ambiguous records.

Each topic should include:

- `key`
- `label`
- `category`
- `description`
- `aliases`
- `subtopics`

Jurisdiction-specific aliases are allowed when they improve input matching or validation.

## Tests and Validation

Corpus-pack PRs should include at least one of:

- A manifest-only validation update.
- Scraper or cleaner unit tests using synthetic or redistributable fixtures.
- Corpus-loading tests for the new pack.
- Validation-rule tests for jurisdiction-specific terminology or doctrine.

## Local Checks

Run focused checks before PR:

```sh
python3 script/validate_corpus_pack.py corpus/packs/sg_tort/manifest.json
python3 script/validate_blind_eval_artifact.py
git diff --check
```

For code changes, also run the relevant Python or TUI tests for the touched area.

## Issue Templates

Use:

- Corpus-pack request: concrete source-backed pack proposals.
- Jurisdiction request: first-class jurisdiction support before source work is ready.
- Ingestion bug: scraper, cleaner, manifest, or validation failures.
- Validation-quality report: generated-output quality or doctrinal problems.

Do not paste paid, private, account-gated, or non-redistributable legal text into issues.

## Cadence

Post-launch maintenance target: one new corpus pack or major feature every 2-4 weeks for the first 3 months. Prefer small reviewable increments:

1. Manifest and licensing review.
2. Ingestion or cleaner code.
3. Corpus-loading and validation tests.
4. Prompt or validation overlay.
5. Demo or README update after the pack works locally.
