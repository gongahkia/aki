# SG Tort Corpus Source Decision

Status: Reference pack. Sources documented for the frozen 41-entry training corpus and the held-out 50-case eval set (`corpus/eval/sg_tort_v1.jsonl`).
Date checked: 2026-07-02.

## Decision

Use only open-access Singapore legal publishing for corpus and eval enrichment. Do not commit full-text judgments from restricted sources. Case identifiers, doctrinal keywords, headnote-style paraphrases, and short retrieval queries authored for this repository are permitted.

## Verified Sources

| Source | URL | Finding |
|---|---|---|
| SAL Journals Online | https://journalsonline.academypublishing.org.sg | The Singapore Academy of Law publishes the SAL Annual Review, SAL Journal, and SAL Practitioner on an open-access basis. Tort law chapters (2014–2024) are freely downloadable. |
| Singapore Law Gazette | https://lawgazette.com.sg | Official monthly journal of the Law Society of Singapore. Archive from October 2017; open access to feature articles including tort content. |
| Singapore Law Watch | https://www.singaporelawwatch.sg/About-Singapore-Law/Commercial-Law/ch-20-the-law-of-negligence | SAL's official commentary. Ch. 20 (Law of Negligence) is open access and cited widely by SG practitioners. |
| eLitigation.sg | https://www.elitigation.sg | Official case-law portal for Singapore courts. Judgments (Supreme Court, State Courts) available in HTML/PDF; free retrieval, redistribution requires terms review. |
| CommonLII | http://www.commonlii.org/sg/ | Free case-law aggregator; older SG judgments. Not currently used for full-text redistribution. |
| Singapore Judiciary | https://www.judiciary.gov.sg/judgments | Official Supreme Court judgment portal; used for scraping when redistribution terms are cleared. |
| ASEAN Law Association SG chapter | https://www.aseanlawassociation.org/wp-content/uploads/2019/11/ALA-SG-legal-system-Part-5-3.pdf | Open PDF summarising the SG legal system, including tort. |

## Redistribution Rule

Committed SG records include:

- The bundled 41-entry training corpus at `corpus/labelled/sg_tort/corpus.json` (repository fixture, authored for this project).
- Case identifiers, doctrinal keywords, and short headnote paraphrases in `corpus/packs/sg_tort/authorities.json` (authored for this project — no verbatim excerpts).
- The 50-case eval set at `corpus/eval/sg_tort_v1.jsonl` (short retrieval queries and expected doctrinal keywords authored for this project).

Not committed:

- Full-text SG Supreme Court judgments (redistribution terms not yet cleared).
- SAL Annual Review chapter text (open access but redistribution terms require attribution and non-alteration checks not yet automated in ingestion pipeline).

## Corpus Growth Plan

Phase 1 (current):
- 41 gold training entries (frozen for reproducibility).
- 50 held-out eval cases.
- 15 leading authorities + 7 statutes in `authorities.json` for prompt overlay and citation grounding.

Phase 2 (future — not this release):
- Ingest SAL Annual Review Tort chapters 2014–2024 as bronze/silver/gold layers via existing medallion pipeline once attribution automation lands.
- Add recent eLitigation.sg judgments (2020–2024) after per-source redistribution review.
- Expand `authorities.json` to ≥ 40 entries covering all 27 taxonomy topics.

## Related

- Corpus pack manifest: `corpus/packs/sg_tort/manifest.json`
- Authorities index: `corpus/packs/sg_tort/authorities.json`
- Eval set: `corpus/eval/sg_tort_v1.jsonl`
- ADR 0001: `docs/adr/0001-jurisdiction-and-corpus-packs.md`
- UK source decision: `docs/uk-tort-corpus-source-decision.md`
- US source decision: `docs/us-tort-corpus-source-decision.md`
