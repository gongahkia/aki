# ADR 0001: Jurisdiction And Corpus Packs

Date: 2026-07-01.
Status: Accepted for Phase 1 implementation.
Issue: [#12](https://github.com/gongahkia/jikai/issues/12).

## Context

The pivot plan keeps SG Tort as the first working corpus but broadens Jikai into common-law exam-question infrastructure across SG, UK, and US. Current code has a partial `DomainPack` registry in [src/domain/packs.py](../../src/domain/packs.py), but most code still hardcodes Singapore Tort assumptions through settings, prompts, validators, retrieval, database history, API models, and the TUI.

Current requests and records are mostly topic-only. That is insufficient for cross-jurisdiction retrieval because `negligence` in SG, UK, and US may share labels but differ in authorities, citation style, validation cues, and source licensing.

## Decision

Use corpus packs as the primary runtime boundary. A corpus pack declares jurisdiction, subject, source metadata, license metadata, taxonomy, prompt overlay, validation overlay, clean corpus path, and model/index artifact names.

Canonical corpus records use first-class fields:

```json
{
  "id": "sg_tort:000001",
  "corpus_pack_key": "sg_tort",
  "jurisdiction": "sg",
  "subject": "tort",
  "topics": ["negligence"],
  "subtopics": ["duty_of_care"],
  "text": "Fact pattern or source extract...",
  "source": {
    "name": "manual_seed",
    "url": null
  },
  "license": {
    "name": "project_fixture",
    "redistributable": true
  },
  "metadata": {}
}
```

Canonical runtime queries use:

```json
{
  "corpus_pack": "sg_tort",
  "jurisdiction": "sg",
  "subject": "tort",
  "topics": ["negligence"],
  "subtopics": ["duty_of_care"]
}
```

`law_domain` remains a compatibility alias for `subject` until the API and TUI have migrated.

## Alternatives Considered

### Keep jurisdiction in metadata only

Rejected. Metadata-only jurisdiction makes filtering optional and weak. It also leaves prompt, validation, DB, and TUI code free to keep assuming Singapore Tort.

### Add `law_domain` only

Rejected. `law_domain=tort` cannot distinguish SG Tort from UK Tort or US Tort. It also does not represent source licensing and scraper differences.

### Fork code paths per jurisdiction

Rejected. Separate SG/UK/US services would duplicate retrieval, generation, validation, and UI flows. It would also make community corpus contributions expensive.

### Use corpus-pack manifests and a `DomainPack` registry

Accepted. This matches the existing partial abstraction and keeps jurisdiction, subject, taxonomy, prompt behavior, validation behavior, and data paths in one boundary.

## Migration Sequence

1. Add docs: this ADR, SG Tort assumption audit, and corpus-pack manifest spec.
2. Extend `DomainPack` to include corpus path, manifest metadata, prompt overlay, validation overlay, and artifact naming.
3. Introduce canonical corpus record parsing while continuing to read legacy `topic` records.
4. Backfill `corpus/clean/tort/corpus.json` as `sg_tort`, `sg`, `tort`.
5. Add API/service request fields: `corpus_pack`, `jurisdiction`, `subject`, `subtopics`.
6. Update corpus and vector retrieval to filter by pack, jurisdiction, subject, topic, and subtopic.
7. Update prompts and validators to load pack overlays instead of Singapore/Tort constants.
8. Add DB migration columns and backfill existing generation history.
9. Add TUI pack selector and pack-aware request types.
10. Add tests for legacy SG requests, canonical SG requests, and one fake second pack.

## Compatibility Strategy

- Default omitted `corpus_pack` to `sg_tort`.
- Default omitted `jurisdiction` to `sg`.
- Default omitted `subject` to `tort`.
- Treat legacy `law_domain` as an alias for `subject`.
- Read old corpus records with `topic` or topic-list shapes.
- Backfill old DB rows with `sg_tort`, `sg`, and `tort`.
- Keep existing SG Tort examples working until a later deprecation issue removes legacy fields.
- Do not reuse a Chroma collection across incompatible schemas; create pack/schema-specific collection names.

## Impact Map

- Config: [src/config/settings.py](../../src/config/settings.py), [env.example](../../env.example).
- Domain: [src/domain/packs.py](../../src/domain/packs.py), [src/domain/topics.py](../../src/domain/topics.py), [src/domain/templates](../../src/domain/templates).
- Corpus: [src/services/corpus_service.py](../../src/services/corpus_service.py), [src/services/corpus_preprocessor.py](../../src/services/corpus_preprocessor.py), [src/services/scraper_service.py](../../src/services/scraper_service.py).
- Retrieval: [src/services/vector_service.py](../../src/services/vector_service.py).
- Generation: [src/services/hypothetical_service.py](../../src/services/hypothetical_service.py), [src/services/workflow_facade.py](../../src/services/workflow_facade.py).
- Prompts: [src/services/prompt_engineering/templates.py](../../src/services/prompt_engineering/templates.py).
- Validation: [src/services/validation_service.py](../../src/services/validation_service.py), [src/services/topic_guard.py](../../src/services/topic_guard.py).
- DB: [src/services/database_service.py](../../src/services/database_service.py), [alembic/versions](../../alembic/versions).
- API: [src/api/routes/workflow.py](../../src/api/routes/workflow.py), [src/api/routes/corpus.py](../../src/api/routes/corpus.py), [src/api/routes/validation.py](../../src/api/routes/validation.py), [src/api/routes/jobs.py](../../src/api/routes/jobs.py).
- TUI: [tui/src/api/types.rs](../../tui/src/api/types.rs), [tui/src/screens](../../tui/src/screens), [tui/src/state/chat.rs](../../tui/src/state/chat.rs).
- Tests: [tests/test_domain](../../tests/test_domain), [tests/test_services](../../tests/test_services).

## Consequences

- Implementation becomes schema-first rather than prompt-first.
- UK/US ingestion work waits for pack and license metadata fields.
- Current SG Tort behavior stays the default path during migration.
- Each future subject or jurisdiction must ship a manifest, taxonomy, prompt overlay, validation overlay, and corpus/license metadata.
