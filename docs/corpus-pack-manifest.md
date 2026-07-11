# Corpus-Pack Manifest Spec

Status: draft v1 for Phase 1.
Schema version: `1.0`.
Reference manifest: [corpus/packs/sg_tort/manifest.json](../corpus/packs/sg_tort/manifest.json).
US expansion manifest: [corpus/packs/us_tort/manifest.json](../corpus/packs/us_tort/manifest.json).
UK expansion manifest: [corpus/packs/uk_tort/manifest.json](../corpus/packs/uk_tort/manifest.json).
Draft fixture-only example: [corpus/packs/sg_contract/manifest.json](../corpus/packs/sg_contract/manifest.json).
Validator: [script/validate_corpus_pack.py](../script/validate_corpus_pack.py).

## Purpose

A corpus pack is the unit of legal content Jikai can ingest, retrieve from, prompt against, and validate. It binds jurisdiction, subject, taxonomy, source terms, ingestion commands, cleaner commands, validation expectations, and artifact paths without requiring core code forks.

## Local Validation

Run from the repo root:

```sh
python3 script/validate_corpus_pack.py corpus/packs/sg_tort/manifest.json
python3 script/validate_corpus_pack.py corpus/packs/us_tort/manifest.json
python3 script/validate_corpus_pack.py corpus/packs/uk_tort/manifest.json
python3 script/validate_corpus_pack.py corpus/packs/sg_contract/manifest.json
```

The validator checks JSON syntax, required fields, topic shape, unique topic keys, non-empty pipeline commands, and local corpus/raw paths.

## Required Fields

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | string | Manifest schema version. Current value: `1.0`. |
| `key` | string | Stable pack key, lower snake case. Example: `sg_tort`. |
| `display_name` | string | Human-readable pack name. |
| `status` | string | `reference`, `draft`, `experimental`, or `stable`. |
| `jurisdiction.code` | string | Short jurisdiction code. Examples: `sg`, `uk`, `us`. |
| `jurisdiction.name` | string | Human-readable jurisdiction name. |
| `jurisdiction.legal_system` | string | Legal-system family or local descriptor. |
| `subject.key` | string | Subject key. Example: `tort`. |
| `subject.name` | string | Human-readable subject name. |
| `corpus.clean_path` | string | Clean corpus artifact path, repo-root relative. |
| `corpus.supplemental_paths` | string array | Optional extra clean corpus files loaded after `clean_path`. |
| `corpus.raw_paths` | string array | Raw source directories, repo-root relative. |
| `corpus.record_format` | string | Current clean record format. |
| `corpus.id_prefix` | string | Prefix used for canonical record IDs. |
| `sources` | array | Source descriptors with URL, format, access, terms notes. |
| `license.name` | string | License or source-terms label. |
| `license.redistribution_status` | string | `allowed`, `restricted`, `unknown`, or `bundled_fixture`. |
| `license.terms_notes` | string | Plain-language redistribution notes. |
| `taxonomy.version` | string | Taxonomy version/date. |
| `taxonomy.topics` | array | Topic definitions. |
| `pipeline.ingestion_command` | string | Command to acquire or stage pack data. |
| `pipeline.cleaner_command` | string | Command to build clean corpus JSON. |
| `validation.expected_record_count_min` | integer | Minimum expected clean records. |
| `validation.required_record_fields` | string array | Fields required in current clean records. |

Each `sources[]` item requires:

| Field | Type | Meaning |
|---|---|---|
| `name` | string | Source name. |
| `registry_source_id` | string | Key in `corpus/source_registry.json`; full-text ingestion must pass that registry entry. |
| `url` | string or null | Source URL or `file://` path. |
| `source_format` | string | `html`, `txt`, `pdf`, `docx`, `json`, `bulk_json`, etc. |
| `access` | string | `local_repo`, `public_web`, `bulk_download`, `manual`, etc. |
| `terms_url` | string or null | URL to source terms when available. |
| `notes` | string | Pack-specific source notes. |

Each `taxonomy.topics[]` item requires:

| Field | Type | Meaning |
|---|---|---|
| `key` | string | Canonical topic key, lower snake case. |
| `label` | string | Human-readable label. |
| `category` | string | Grouping for UI and docs. |
| `description` | string | Short topic scope. |
| `aliases` | string array | Accepted input aliases. |
| `subtopics` | array | Optional finer-grained topics. Use `[]` if none yet. |

Clean corpus records may include student-practice fields:

- `question_prompt`
- `fact_pattern`
- `issues_expected`
- `model_answer`
- `marking_rubric`
- `difficulty`
- `time_limit_minutes`
- `jurisdiction_notes`
- `answer_visibility`
- `source_exam_context`

Readers must preserve legacy `text` while treating `fact_pattern` as the student-facing facts when present. Model answers and rubrics should stay hidden unless a caller explicitly requests them.

## Optional Fields

| Field | Type | Meaning |
|---|---|---|
| `pipeline.embedding_command` | string | Command to rebuild vector indexes. |
| `pipeline.training_command` | string | Command to train pack-specific ML artifacts. |
| `corpus.supplemental_paths` | string array | Authored or permissioned add-on corpus files. |
| `validation.canonical_record_fields` | string array | Target schema fields after migration. |
| `validation.topic_coverage` | string | Topic coverage expectation. |
| `validation.jurisdiction_expectations` | string array | Jurisdiction-specific validation cues. |
| `validation.quality_checks` | string array | Human or automated quality checks. |
| `course_profiles` | object | Optional educator-defined course/module profiles scoped to this pack. |
| `artifacts` | object | Optional vector/model/label artifact names. |
| `maintainers` | array | Optional pack maintainers. |
| `notes` | string | Free-form implementation notes. |

## Course Profiles

`course_profiles` lets a pack define selectable overlays for syllabus topics, allowed authorities, difficulty, exam style, prompt guidance, and validation thresholds. Profiles are discoverable through `/corpus/profiles` and selectable with `course_profile` on generation and validation requests.

Only profiles with `data_backed: true` are selectable for prompt/validation overlays. Use `data_backed: false` for planned profiles such as `bar_essay` until redistribution-safe corpus records, authority metadata, and answer/rubric examples exist.

Each profile may include:

| Field | Type | Meaning |
|---|---|---|
| `display_name` | string | Human-readable profile label. |
| `syllabus_topics` | string array | Canonical topics accepted by this profile. |
| `allowed_authority_ids` | string array | Authority/statute IDs allowed for answer citation support. |
| `difficulty_profile` | object | Supported levels, party ranges, or timing targets. |
| `exam_style` | object | Answer format and issue-spotting conventions. |
| `overlays.prompt` | object | Profile-specific prompt guidance merged over the pack prompt overlay. |
| `overlays.validation` | object | Profile-specific validation thresholds merged over the pack validation overlay. |
| `data_backed` | boolean | Whether profile use is backed by committed corpus/authority data. |
| `data_sources` | string array | Corpus/metadata paths supporting the profile. |
| `notes` | string | Source limitations or usage caveats. |

## Redistribution Rules

Pack manifests must distinguish source access from redistribution rights.

- `allowed`: source terms permit redistributing the included clean text under the stated terms.
- `restricted`: source terms permit access or scraping, but not redistributing full text.
- `unknown`: terms are not verified. Do not commit raw or clean third-party text.
- `bundled_fixture`: content is already bundled as repository fixture data; this is not clearance for new external text.

Do not commit paid outlines, casebooks, Quimbee/BARBRI/Studicata material, student notes without permission, or scraped full text from sources whose terms do not permit redistribution. For restricted or unknown sources, commit only the manifest, scraper/cleaner code, metadata, and reproducible commands.

## Phase 2 Fit

The same fields support UK and US Tort packs:

- UK Tort can use `jurisdiction.code=uk`, `subject.key=tort`, BAILII/source terms in `sources`, and a UK prompt/validation overlay.
- US Tort can use `jurisdiction.code=us`, `subject.key=tort`, CourtListener/CAP source terms in `sources`, and US citation/validation overlays.
- Both packs can share common-law base topics while declaring jurisdiction-specific aliases and subtopics.
