# Product Scope Decision

Date: 2026-07-10
Issue: #31
Status: accepted

## Decision

The first real product scope is SG Tort only.

Jikai may keep UK/US/common-law corpus-pack infrastructure and comparator metadata in the repo, but student-facing generation, evaluation claims, hosted-demo positioning, and release language must treat `sg_tort` as the only reference product scope until another pack has reusable practice content, source clearance, pack-specific validation, and human evaluation.

## Evidence

- Local corpus count on 2026-07-10: `corpus/labelled/sg_tort/corpus.json` has 41 records; `corpus/clean/us_tort/corpus.json` and `corpus/clean/uk_tort/corpus.json` each have 5 records.
- `docs/sg-tort-corpus-source-decision.md` records SG Tort as the reference pack and blocks full-text ingestion from restricted or unknown SG sources.
- Web search on 2026-07-10 found SG tort commentary, journal articles, and public case-law sources, but did not verify a reusable public SG practice-hypothetical corpus.
- Web search did find more generic US/non-SG tort practice materials; those do not support SG-first product claims.

## Product Rule

- Default runtime pack: `sg_tort`.
- Default release/demo claim: SG Tort exam-practice generation.
- UK/US packs: comparator, research, or metadata-only until pack acceptance is documented.
- New source ingestion: link-first unless `corpus/source_registry.json` allows committed text.
- Benchmark/eval copy: name SG Tort explicitly unless the measured artifact includes another accepted pack.

## Exit Criteria For A Second Product Scope

A second pack may become student-facing only after all are true:

- Pack manifest, taxonomy, prompt overlay, and validation overlay are complete.
- Source registry permits committed practice text or the pack is explicitly metadata/link-only.
- Held-out eval records and a blind-rater rubric exist for that pack.
- README and demo copy distinguish SG results from the new pack results.
