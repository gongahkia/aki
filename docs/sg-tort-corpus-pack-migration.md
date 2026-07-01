# SG Tort Corpus Pack Migration

Status: Phase 1 reference-pack migration note.
Pack manifest: [corpus/packs/sg_tort/manifest.json](../corpus/packs/sg_tort/manifest.json).

## Current Contract

`sg_tort` is now the default corpus pack. Its manifest points at the existing clean corpus file:

```text
corpus/clean/tort/corpus.json
```

The file remains in the legacy `text` + `topic` shape. Runtime loading wraps every record with canonical pack fields:

- `corpus_pack_key=sg_tort`
- `jurisdiction=sg`
- `subject=tort`
- `subtopics=[]`

No clean-corpus record is dropped during this wrapper migration.

## Local User Impact

No manual corpus rewrite is required for existing users. Existing SG Tort generation requests still default to the same corpus and topic taxonomy.

Users with existing local artifacts should rebuild derived state when they need pack-aware retrieval metadata:

```sh
rm -rf chroma_db
```

SQLite history is migrated in-place at app startup with default `sg_tort`, `sg`, `tort`, and `[]` values for older rows.

## Future Migration

A later data migration can rewrite `corpus/clean/tort/corpus.json` into canonical records on disk. Until then, the loader is the compatibility boundary and the manifest is the pack source of truth.
