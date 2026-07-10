# UK Tort Corpus Source Decision

Status: Phase 2 source decision.
Date checked: 2026-07-01.
Issue: https://github.com/gongahkia/jikai/issues/18.

## Decision

Use The National Archives Find Case Law service as the first UK Tort corpus source. Do not use BAILII for committed corpus text until its live copyright/terms page can be verified.

## Verified Sources

| Source | URL | Finding |
|---|---|---|
| BAILII copyright page | https://www.bailii.org/bailii/copyright.html | The live page returned an Anubis JavaScript proof-of-work challenge from this environment. I cannot verify BAILII's current reuse terms here, so no BAILII text is committed. |
| Find Case Law API docs | https://nationalarchives.github.io/ds-find-caselaw-docs/public | The API exposes judgments held by The National Archives, XML document URLs, Atom feeds, content hashes, and a 1,000 requests per rolling five minutes per-IP rate limit. |
| Open Justice Licence v2.0 | https://caselaw.nationalarchives.gov.uk/open-justice-licence/version/2 | The licence allows copying, publishing, distribution, transmission, commercial use, research, journalism, education, and legal use, subject to attribution, current-version, dignity, justice-administration, and no-misrepresentation conditions. |
| Open Justice Licence v2.0 | https://caselaw.nationalarchives.gov.uk/open-justice-licence/version/2 | Computational analysis of Find Case Law judgments, including search-engine indexing, is excluded and needs additional permission. |

## Redistribution Rule

Public URL does not imply permission to commit full text. Full-text writes must pass `corpus/source_registry.json` with `text_commit_allowed=true` and `redistribution_status=allowed` or `bundled_fixture`. Sources with `restricted` or `unknown` status may commit only URL, title, date, jurisdiction, topic tags, and short repository-authored notes.

Committed UK sample records may include capped excerpts from current Find Case Law XML with source URL, content hash, retrieved date, attribution, and Open Justice Licence metadata because the registry marks that source as allowed for this capped fixture use. Broad ingestion, embedding, search indexing, enrichment, or other computational analysis must wait for a separate Find Case Law computational-analysis licence or written clearance.

## Initial Corpus Plan

Start with a small teaching-oriented UK tort sample from Find Case Law XML:

| Case | TNA URL | Starter topic |
|---|---|---|
| Robinson v Chief Constable of West Yorkshire Police | https://caselaw.nationalarchives.gov.uk/uksc/2018/4/data.xml | duty_of_care |
| Manchester Building Society v Grant Thornton UK LLP | https://caselaw.nationalarchives.gov.uk/uksc/2021/20/data.xml | economic_loss |
| Khan v Meadows | https://caselaw.nationalarchives.gov.uk/uksc/2021/21/data.xml | clinical_negligence |
| Paul v Royal Wolverhampton NHS Trust | https://caselaw.nationalarchives.gov.uk/uksc/2024/1/data.xml | psychiatric_harm |
| WM Morrison Supermarkets plc v Various Claimants | https://caselaw.nationalarchives.gov.uk/uksc/2020/12/data.xml | vicarious_liability |
| URS Corporation Ltd v BDW Trading Ltd | https://caselaw.nationalarchives.gov.uk/uksc/2025/21/data.xml | economic_loss |

Commit the first five as capped fixtures; keep URS as a verified follow-on candidate. Do not scale beyond capped fixtures until issue #23 defines corpus layers and the computational-analysis licence path is settled.
