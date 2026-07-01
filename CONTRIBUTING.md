# Contributing

## Corpus Packs

Jikai accepts new jurisdictions and subjects through corpus packs. Start with [docs/corpus-pack-manifest.md](docs/corpus-pack-manifest.md), then copy the SG reference shape from [corpus/packs/sg_tort/manifest.json](corpus/packs/sg_tort/manifest.json).

Required contribution path:

1. Create `corpus/packs/<pack_key>/manifest.json`.
2. Fill in jurisdiction, subject, source URLs, source format, license/terms notes, taxonomy, ingestion command, cleaner command, and validation expectations.
3. Run `python3 script/validate_corpus_pack.py corpus/packs/<pack_key>/manifest.json`.
4. Add or update scraper/cleaner code only when the source terms allow the workflow.
5. Add tests or fixtures that do not depend on paid, private, or non-redistributable text.
6. Open a PR that explains source provenance and redistribution status.

## Licensing Rules

Do not commit third-party legal text unless the source terms permit redistribution. This includes paid outlines, casebooks, commercial bar-prep material, proprietary summaries, and scraped full text from sources with restricted or unknown terms.

For restricted or unknown sources, contribute only:

- Manifest metadata.
- Source URLs and terms URLs.
- Scraper or cleaner code.
- Small synthetic fixtures.
- Instructions for users to reproduce the corpus locally.

Every pack must set `license.redistribution_status` to `allowed`, `restricted`, `unknown`, or `bundled_fixture`.

## Local Checks

Run focused checks before PR:

```sh
python3 script/validate_corpus_pack.py corpus/packs/sg_tort/manifest.json
git diff --check
```

For code changes, also run the relevant Python or TUI tests for the touched area.
