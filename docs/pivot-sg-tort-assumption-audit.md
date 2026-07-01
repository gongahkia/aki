# SG Tort Assumption Audit

Status: current-state audit for Phase 1 pivot work.
Date: 2026-07-01.
Source issue: [#12](https://github.com/gongahkia/jikai/issues/12).
Related ADR: [0001 Jurisdiction And Corpus Packs](adr/0001-jurisdiction-and-corpus-packs.md).

## Summary

The repo already has the start of a pack boundary in [src/domain/packs.py](../src/domain/packs.py), but most runtime paths still assume a single `sg_tort` world: Singapore, Tort, topic-only selection, and one clean corpus path. The largest changes are not cosmetic. They affect corpus shape, request models, retrieval filters, prompts, validators, database history, and the Rust TUI API client.

Current clean corpus fact: `corpus/clean/tort/corpus.json` contains 41 records in a legacy `text` + `topic` shape. Records do not expose first-class `jurisdiction`, `subject`, or `subtopics`.

## Intended Query Shape

Canonical user/runtime query:

```json
{
  "corpus_pack": "sg_tort",
  "jurisdiction": "sg",
  "subject": "tort",
  "topics": ["negligence"],
  "subtopics": ["duty_of_care"]
}
```

Canonical retrieval filters:

```json
{
  "corpus_pack_key": "sg_tort",
  "jurisdiction": "sg",
  "subject": "tort",
  "topic": "negligence",
  "subtopic": "duty_of_care"
}
```

Compatibility rule: requests that omit `corpus_pack`, `jurisdiction`, or `subject` continue to resolve to `sg_tort`, `sg`, and `tort` until a deprecation pass removes the legacy defaults.

## Scope Inspected

- Python config, domain registry, corpus, retrieval, validation, prompt, workflow, ML, DB, API, job routes, startup checks.
- Rust TUI config, API models, generation, chat, corpus, scrape, embed, menu screens.
- Tests, README, Makefile, env sample, package metadata, alembic migrations.
- `WORKON-PIVOT-ASAP.md` sections 5, 6.2, 6.4, 7, and 9.

## High Blast Radius

| Area | Assumption | Evidence | Required change |
|---|---|---|---|
| Corpus path and shape | Clean corpus is `corpus/clean/tort/corpus.json` and legacy records are topic-only. | [src/config/settings.py](../src/config/settings.py), [src/services/corpus_service.py](../src/services/corpus_service.py), [src/services/corpus_preprocessor.py](../src/services/corpus_preprocessor.py), [src/api/routes/jobs.py](../src/api/routes/jobs.py) | Add `CorpusRecord` with `corpus_pack_key`, `jurisdiction`, `subject`, `topics`, `subtopics`, source and license metadata. Keep reader support for legacy `topic`. |
| Request model | Generation and validation accept `topics` + `law_domain`, not jurisdiction or subject. | [src/services/hypothetical_service.py](../src/services/hypothetical_service.py), [src/api/routes/workflow.py](../src/api/routes/workflow.py), [src/api/routes/validation.py](../src/api/routes/validation.py), [tui/src/api/types.rs](../tui/src/api/types.rs) | Add request fields for `corpus_pack`, `jurisdiction`, `subject`, and `subtopics`; keep `law_domain` as an alias for `subject` during migration. |
| SG-only enforcement | Runtime rejects non-Singapore requests. | [src/services/hypothetical_service.py](../src/services/hypothetical_service.py) | Replace `_enforce_singapore_scope` with domain-pack resolution and pack support checks. |
| Prompt behavior | System and generation prompts are Singapore Tort Law prompts. | [src/services/prompt_engineering/templates.py](../src/services/prompt_engineering/templates.py) | Split shared common-law prompt base from jurisdiction/subject overlays. |
| Validation behavior | Validators score Singapore context and tort-topic matches directly. | [src/services/validation_service.py](../src/services/validation_service.py), [src/services/topic_guard.py](../src/services/topic_guard.py) | Move topic rules and jurisdiction context indicators behind pack-specific validation overlays. |
| Retrieval/index metadata | Vector search is built around tort topics and Singapore wording. | [src/services/vector_service.py](../src/services/vector_service.py), [src/services/corpus_service.py](../src/services/corpus_service.py) | Index and filter by pack, jurisdiction, subject, topic, and subtopic. Rebuild embeddings after schema migration. |
| Topic taxonomy | Only tort topics are canonicalized. | [src/domain/topics.py](../src/domain/topics.py), [tests/test_domain/test_topics.py](../tests/test_domain/test_topics.py) | Convert taxonomy lookup into pack-owned files or registry entries. |
| DB history | Generation history stores `topics` and `law_domain`, but no jurisdiction, subject, pack, or subtopics. | [src/services/database_service.py](../src/services/database_service.py), [alembic/versions/20260228_000001_initial_schema.py](../alembic/versions/20260228_000001_initial_schema.py) | Add migration columns and backfill existing rows as `sg_tort`, `sg`, `tort`. |

## Medium Blast Radius

| Area | Assumption | Evidence | Required change |
|---|---|---|---|
| Settings/env | App settings expose `allowed_law_domains`, `LAW_DOMAIN`, `CHROMA_COLLECTION=tort_hypotheticals`, and SG/Tort defaults. | [src/config/settings.py](../src/config/settings.py), [env.example](../env.example) | Add `DEFAULT_CORPUS_PACK`, pack search paths, and collection names that include pack keys. |
| Domain pack boundary | `DomainPack` exists but only registers `sg_tort`; callers mostly bypass it. | [src/domain/packs.py](../src/domain/packs.py) | Make pack resolution the normal path for topic validation, prompts, corpus paths, and validation. |
| Preprocess jobs | Preprocessor writes to `corpus/clean/tort`; `include_non_tort` is a side flag, not a subject model. | [src/services/corpus_preprocessor.py](../src/services/corpus_preprocessor.py), [src/api/routes/jobs.py](../src/api/routes/jobs.py), [tui/src/screens/preprocess.rs](../tui/src/screens/preprocess.rs) | Route preprocessing through pack manifests and write pack-scoped clean artifacts. |
| Scraping | Scraper sources and metadata are Singapore-specific. | [src/services/scraper_service.py](../src/services/scraper_service.py), [tui/src/screens/scrape.rs](../tui/src/screens/scrape.rs), [tui/src/screens/chat.rs](../tui/src/screens/chat.rs) | Move source URLs, court codes, headers, and license notes into corpus-pack manifests/adapters. |
| ML training defaults | ML labels default to tort-only CSV paths. | [src/config/settings.py](../src/config/settings.py), [src/services/workflow_facade.py](../src/services/workflow_facade.py), [src/api/routes/jobs.py](../src/api/routes/jobs.py) | Add pack-aware training data defaults and model artifact names. |
| Startup checks | Required corpus check is tort-specific. | [src/services/startup_checks.py](../src/services/startup_checks.py), [tests/test_services/test_startup_checks.py](../tests/test_services/test_startup_checks.py) | Check the selected default pack rather than a hardcoded tort corpus. |
| API job defaults | Embed, scrape, label, train defaults point at tort corpus paths. | [src/api/routes/jobs.py](../src/api/routes/jobs.py) | Accept pack key and derive paths from manifest. |
| TUI flow | TUI labels, defaults, compiled topic UI, and chat commands assume SG Tort. | [tui/src/config.rs](../tui/src/config.rs), [tui/src/screens/main_menu.rs](../tui/src/screens/main_menu.rs), [tui/src/screens/generate/topics.rs](../tui/src/screens/generate/topics.rs), [tui/src/screens/generate/mod.rs](../tui/src/screens/generate/mod.rs), [tui/src/screens/embed.rs](../tui/src/screens/embed.rs), [tui/src/state/chat.rs](../tui/src/state/chat.rs) | Add pack selector state and send canonical request fields to the API. |
| Tests | Tests assert tort-only topic behavior and Singapore validation cues. | [tests/test_domain/test_topics.py](../tests/test_domain/test_topics.py), [tests/test_services/test_generation_request.py](../tests/test_services/test_generation_request.py), [tests/test_services/test_validation_service.py](../tests/test_services/test_validation_service.py), [tests/test_services/test_prompt_templates.py](../tests/test_services/test_prompt_templates.py), [tests/test_services/test_corpus_service_vector_fallback.py](../tests/test_services/test_corpus_service_vector_fallback.py) | Add SG regression tests plus at least one fake second pack fixture before UK/US corpora land. |

## Low Blast Radius

| Area | Assumption | Evidence | Required change |
|---|---|---|---|
| README wording | README still documents current SG Tort corpus and examples after the pivot lede. | [README.md](../README.md) | Update examples as pack support ships; keep current-state notes clear. |
| Package metadata | Package description says Singapore Tort Law. | [pyproject.toml](../pyproject.toml) | Rename once the first non-SG pack is runnable. |
| Make targets | Makefile mostly delegates to current scripts and inherits path defaults. | [Makefile](../Makefile) | Add pack args only after API/job routes accept them. |
| Templates | JSON domain templates are tort-specific. | [src/domain/templates](../src/domain/templates) | Move into `sg_tort` pack or define shared tort template layer. |

## Workstream Split

### Schema/Data Migration

1. Define canonical `CorpusRecord` and corpus-pack manifest fields.
2. Add legacy reader support for existing `topic` and topic-list records.
3. Backfill current clean corpus as `corpus_pack_key=sg_tort`, `jurisdiction=sg`, `subject=tort`.
4. Add DB columns: `corpus_pack_key`, `jurisdiction`, `subject`, `subtopics`; backfill old rows.
5. Rebuild Chroma collections with pack-aware metadata.

### Runtime Behavior

1. Resolve every generation, corpus, validation, scrape, embed, label, and train request through `DomainPack`.
2. Add API/TUI fields: `corpus_pack`, `jurisdiction`, `subject`, `subtopics`.
3. Keep `law_domain` and legacy `topics` request compatibility during migration.
4. Replace hardcoded path defaults with manifest-derived paths.
5. Add pack-specific error messages for unsupported jurisdiction/subject/topic combinations.

### Prompt/Validation Behavior

1. Split prompt templates into common-law base plus pack overlay.
2. Move Singapore court/source/citation examples into `sg_tort`.
3. Move tort-topic keyword scoring into pack validation rules.
4. Add a fake second pack test overlay before shipping UK/US data.
5. Add SG regression tests so current behavior stays intentional.

### Docs/TUI/Tests

1. Update README examples only when runtime support exists.
2. Add corpus-pack manifest docs and contributor workflow.
3. Add TUI pack selector and pack-aware chat commands.
4. Update tests to cover legacy requests and canonical requests.
5. Add migration notes for users with old SQLite/Chroma/corpus artifacts.

## Dependency Order

1. Finish ADR and audit. This issue.
2. Define manifest spec. Issue #10.
3. Promote `DomainPack` into the runtime boundary. Issue #9.
4. Convert SG Tort to the first corpus pack. Issue #6.
5. Add overlays for taxonomy, prompts, and validation. Issue #7.
6. Add UK/US ingestion only after licensing checks. Issues #18 and #15.

## Non-Goals For This Audit

- No schema or code migration.
- No UK/US scraping.
- No claim that BAILII, CourtListener, or CAP redistribution terms are cleared.
- No retirement of legacy SG Tort defaults yet.
