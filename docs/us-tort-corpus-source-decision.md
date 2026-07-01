# US Tort Corpus Source Decision

Status: Phase 2 source decision.
Date checked: 2026-07-01.
Issue: https://github.com/gongahkia/jikai/issues/15.

## Decision

Use Caselaw Access Project static case JSON as the first US Tort corpus source. Use CourtListener for discovery/linkout/API enrichment only until its redistribution path is separately cleared per record.

## Verified Sources

| Source | URL | Finding |
|---|---|---|
| CAP terms | https://case.law/terms/ | The CAP terms page loads content through `https://case.law/templates/cap-terms-page.js`; that template marks CAP caselaw data and metadata as public use under CC0 1.0 and requests attribution/community norms. |
| CAP docs | https://case.law/docs/ | CAP docs point API access to CourtListener and bulk/static download access to `https://static.case.law/`. |
| CourtListener terms | https://www.courtlistener.com/terms/ | The live page returned CloudFront 403 from this environment; the official Free Law Project source template at `https://github.com/freelawproject/courtlistener/blob/main/cl/simple_pages/templates/terms/latest.html` was readable. It contains usage restrictions, warranty disclaimers, privacy/removal, and DMCA policy, but no explicit redistribution license for case text. |
| CourtListener API docs | https://wiki.free.law/c/courtlistener/help/api/rest/v4/overview | REST API v4.4 supports case-law/search APIs, token auth, endpoint permissions, throttling, and rate limits. |
| Free Law API usage | https://free.law/membership/allowed-api-usage/ | Membership API access is for personal, educational, research, journalistic, and exploratory use; revenue-positive products and larger org/internal tooling need commercial terms. |

## Redistribution Rule

CAP static case JSON may be committed when each record carries CAP source URL, CC0 license metadata, and requested attribution. CourtListener API results must not be committed as full text unless the record is traced back to CAP/static/public-domain source metadata or a later source review clears redistribution.

## Initial Corpus Plan

Start with a small 1L tort case subset from CAP static JSON:

| Case | CAP URL | Starter topic |
|---|---|---|
| Palsgraf v. Long Island Railroad | https://static.case.law/ny/248/cases/0339-01.json | duty_of_care |
| MacPherson v. Buick Motor Co. | https://static.case.law/ny/217/cases/0382-01.json | product_liability |
| Escola v. Coca Cola Bottling Co. | https://static.case.law/cal-2d/24/cases/0453-01.json | strict_liability |
| Tarasoff v. Regents of University | https://static.case.law/cal-3d/17/cases/0425-01.json | duty_of_care |
| Summers v. Tice | https://static.case.law/cal-2d/33/cases/0080-01.json | causation |

Do not bulk-import beyond this curated set until issue #23 defines bronze/silver/gold corpus layers and issue #24 defines retrieval ranking at larger scale.
