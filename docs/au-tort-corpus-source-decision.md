# Australia Tort Corpus Source Decision

Status: proposal only; no ingestion.
Reviewed: 2026-07-01.
Issue: #26.

## Decision

Use `jurisdiction.code=au`, `jurisdiction.name=Australia`, `jurisdiction.legal_system=common_law_federal_state`, and `subject.key=tort`.

Do not ingest AU Tort text yet. Start with source/legal review and a manifest proposal only. Australian court sources have inconsistent reuse terms, so the first usable pack should prefer sources with explicit judgment-reuse permission and preserve attribution, source URL, version, and publication-restriction metadata.

Public URL does not imply permission to commit full text. Full-text writes must pass `corpus/source_registry.json` with `text_commit_allowed=true` and `redistribution_status=allowed` or `bundled_fixture`. AU sources currently remain metadata-only: URL, title, date, jurisdiction, topic tags, and short repository-authored notes.

## Source Review

| Source | Source URL | Access | Terms URL | Redistribution status | Decision |
| --- | --- | --- | --- | --- | --- |
| High Court of Australia judgments | https://www.hcourt.gov.au/cases-and-judgments/judgments/judgments-1998-current | Public web, search/browse | https://www.hcourt.gov.au/terms-use | `restricted` until per-record third-party checks; otherwise promising | Best first candidate. Terms allow commercial and non-commercial reproduction if accuracy, attribution, original URL, non-misleading use, and no official-version implication are preserved. Third-party material still needs separate permission. |
| Federal Court of Australia judgments | https://www.fedcourt.gov.au/digital-law-library/judgments | Public web, search/browse | https://www.fedcourt.gov.au/copyright | `restricted` until pack preserves unaltered judgment text and acknowledgements | Good second candidate. Judgment text can be reproduced or published in unaltered form with acknowledgement that it is a Court judgment/decision; commentary/headnotes must be attributed to publisher, not Court. |
| NSW Caselaw | https://www.caselaw.nsw.gov.au/browse | Public web, search/browse | https://www.caselaw.nsw.gov.au/policy.html | `restricted` | Useful state-law source, but terms impose conditions: accuracy, current official version consistency, suppression-order compliance, no official-version implication, no editorial material, robots-exclusion handling, and revocable authorisation. Use only after crawler/linking policy is implemented. |
| Queensland Courts | https://www.queenslandjudgments.com.au/ | Public web | https://www.courts.qld.gov.au/footer/pages/copyright | `unknown` / permission-required | Do not ingest full text. Terms prohibit reproduction except Copyright Act exceptions without prior written permission; personal-use copying only. |
| Supreme Court of Western Australia | https://www.supremecourt.wa.gov.au/J/judgments.aspx | Public web | https://www.supremecourt.wa.gov.au/_misc/disclaimer_print.aspx | `unknown` / permission-required | Do not ingest full text. Terms allow unaltered personal/non-commercial/in-organisation use, prohibit commercial substantial reproduction without permission, and require permission for links. |

## Evidence Notes

- High Court terms state that website material may be used and reproduced for commercial and non-commercial purposes if the reproduction is accurate, respectful, non-misleading, attributed to the High Court of Australia, and linked to the original version. They also exclude third-party copyrighted material from that permission.
- Federal Court copyright terms distinguish judgments/decisions from other material. Judgments and excerpts can be reproduced or published in unaltered form with acknowledgement that they are Court or Tribunal judgments/decisions and with source acknowledgement.
- NSW Caselaw policy authorises reproduction and publication of judicial decisions only under listed conditions, including suppression-order compliance, official-version consistency, exclusion of external robots from indexing decisions, no editorial material from law-report agencies, and revocability.
- Queensland Courts and Supreme Court of Western Australia terms are not suitable for committed full-text corpus data without written permission.

## Recommended First Pack Shape

```json
{
  "key": "au_tort",
  "display_name": "Australian Tort Law",
  "status": "proposal",
  "jurisdiction": {
    "code": "au",
    "name": "Australia",
    "legal_system": "common_law_federal_state"
  },
  "subject": {
    "key": "tort",
    "name": "Tort Law"
  },
  "license": {
    "redistribution_status": "restricted",
    "terms_notes": "Source-specific conditions must be preserved per record; do not ingest Queensland or WA full text without written permission."
  }
}
```

Do not create `corpus/packs/au_tort/manifest.json` until clean/raw artifact paths and per-source rights handling are ready. A manifest that points at empty placeholder corpus paths would pass validation but misrepresent implementation status.

## Topic Taxonomy Proposal

| Topic key | Label | Aliases | Subtopics |
| --- | --- | --- | --- |
| `negligence` | Negligence | negligent conduct, reasonable care | duty, breach, damage |
| `duty_of_care` | Duty Of Care | duty, salient features, proximity | novel duty, public authority, pure mental harm |
| `standard_of_care` | Standard Of Care | breach, reasonable person, precautions | probability of harm, seriousness, burden, social utility |
| `causation` | Causation | factual causation, scope of liability | necessary condition, exceptional causation, remoteness |
| `defamation` | Defamation | defamatory matter, publication, serious harm | identification, publication, defences |
| `nuisance` | Nuisance | private nuisance, interference with land | substantial interference, unreasonable interference |
| `vicarious_liability` | Vicarious Liability | employer liability, course of employment | employee relationship, close connection |
| `occupiers_liability` | Occupiers Liability | premises liability, occupier duty | entrants, obvious risk, warnings |
| `economic_loss` | Economic Loss | pure economic loss, negligent misstatement | vulnerability, reliance, assumption of responsibility |
| `defences` | Defences | contributory negligence, voluntary assumption of risk | apportionment, obvious risk, illegality |

## Citation Style

Expected neutral citation examples:

- `[2026] HCA 22`
- `[2025] FCA 100`
- `[2024] NSWCA 50`
- `[2023] QSC 10`
- `[2022] WASC 20`

Pack records should store:

- `court`
- `neutral_citation`
- `decision_date`
- `source_url`
- `terms_url`
- `source_copyright_owner`
- `redistribution_status`
- `suppression_or_non_publication_checked`
- `official_version_warning`

## Validation Cues

Jurisdiction indicators:

- australia
- australian
- commonwealth
- high court
- federal court
- supreme court of new south wales
- court of appeal
- hca
- fca
- nswca
- qsc
- wasc

Topic indicators:

- negligence: duty, breach, reasonable care, damage
- duty_of_care: salient features, vulnerability, proximity, policy
- standard_of_care: reasonable person, precautions, foreseeable risk
- causation: necessary condition, scope of liability, remoteness
- defamation: publication, identification, defamatory meaning, serious harm
- nuisance: substantial interference, unreasonable interference, land
- vicarious_liability: employment, course of employment, close connection
- occupiers_liability: occupier, premises, entrant, obvious risk
- economic_loss: reliance, vulnerability, pure economic loss
- defences: contributory negligence, voluntary assumption of risk, illegality

## Next Implementation Gate

Before opening an AU Tort ingestion PR:

1. Choose High Court-only or High Court plus Federal Court as the first source set.
2. Add source-specific license metadata to every record.
3. Preserve original source URLs and attribution text.
4. Implement suppression-order and publication-restriction checks for any state source.
5. Keep Queensland and WA as metadata/link-only until written permission exists.
6. Validate the proposed `au_tort` manifest only after real clean/raw artifact paths exist.
