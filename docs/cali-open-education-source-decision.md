# CALI Open-Education Source Decision

Date: 2026-07-10
Status: metadata-only candidate
Issue: #30

## Decision

Do not bundle CC BY-NC-SA practice text by default. CALI `Tort Law: A 21st-Century Approach` is registered as the first external open-education tort candidate, but full text remains blocked until the project owner explicitly accepts CC BY-NC-SA 4.0 noncommercial and share-alike constraints and the export path preserves attribution, noncommercial, and share-alike metadata.

Committed artifacts may include:
- source URLs
- chapter titles
- topic tags
- attribution metadata
- license constraints

Committed artifacts must not include:
- chapter body text
- hypotheticals or question prompt text
- model answers
- rubrics derived from CALI wording

## Evidence

- Book page: https://saidtorts2d.lawbooks.cali.org/
- Notices/license page: https://saidtorts2d.lawbooks.cali.org/front-matter/notices/
- CALI eLangdell bookstore: https://www.cali.org/the-elangdell-bookstore

The book page identifies the title, author, subject, publication date, and CC BY-NC-SA licensing. The source registry keeps `text_commit_allowed=false` and `derived_metadata_allowed=true`.

## Gate

If the owner accepts the license constraints, import only clearly licensed sections and keep per-record attribution, noncommercial, and share-alike metadata. Until then, `corpus/metadata/us_tort_cali_open_education/metadata.json` remains link-only metadata and `cali_tort_21st_century` keeps `text_commit_allowed=false`.
