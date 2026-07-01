# Jikai HN Launch Package

Status: draft  
Rules checked: 2026-07-01  
Repo: https://github.com/gongahkia/jikai  
Hosted demo: blocked by issue #13  
Demo video: `docs/launch/jikai-demo-video.mp4`
Pipeline demo route: local `/demo/pipeline`

## Rule Checks

| Channel | Source checked | Constraint for Jikai |
|---|---|---|
| Hacker News Show HN | https://news.ycombinator.com/showhn.html | Show HN needs something people can try. If hosted demo is not live, submit the repo/local demo only if the quickstart is reliable. |
| Hacker News guidelines | https://news.ycombinator.com/newsguidelines.html | Use factual technical language. Avoid hype and vote requests. |
| Reddit general rules | https://redditinc.com/policies/reddit-rules | Follow each community's rules, participate authentically, do not spam or manipulate votes. |
| Reddit self-promotion guide | https://www.reddit.com/r/reddit.com/wiki/selfpromotion/ | Do not just drop links. Keep self-promo rare, engage in comments, and avoid asking for upvotes. |
| r/LawSchool | https://www.reddit.com/r/LawSchool/ | The community is for current and former law-school users and is not for legal advice. Post as a study-tool request for feedback, not legal advice. |
| r/MachineLearning | https://www.reddit.com/r/MachineLearning/ | Rules emphasize no spam. Use `[P]` or the current project flair only after checking the live sidebar. |
| X rules | https://help.x.com/en/rules-and-policies/x-rules | Avoid misleading claims, platform manipulation, or repeated automated promotion. |
| LinkedIn policies | https://www.linkedin.com/help/linkedin/answer/34593 | Keep professional, non-spammy, and accurate. |

## Launch Links

| Link | Owner | Status |
|---|---|---|
| GitHub repo | maintainer | Ready |
| Blog post | maintainer | Draft at `docs/launch/blog-ml-foundation-before-llm.md` |
| Hosted demo | maintainer | Blocked by #13 |
| Demo video | maintainer | Ready: `docs/launch/jikai-demo-video.mp4`; runbook at `docs/launch/demo-video-runbook.md` |
| Blind eval artifact | external raters | Blocked by #14 |

## Show HN Title

Preferred:

> Show HN: Jikai - local-first AI hypotheticals for common-law students

Fallback if hosted demo is stable:

> Show HN: Jikai - an inspectable ML-before-LLM engine for legal hypotheticals

Avoid:

> Show HN: Open-source bar prep that beats Quimbee

Reason: bar prep and doctrinal hypothetical practice are not identical. "Beats" needs blind comparison evidence that is not complete.

## Show HN Body

HN URL field should point to the hosted demo if #13 is complete. Otherwise point to the GitHub repo and make the first comment the body below.

Draft first comment:

> Hi HN, I built Jikai, an open-source generator for common-law legal hypotheticals and model answers.
>
> The technical idea is ML foundation before LLM drafting: corpus-pack scope guard, topic normalization, classifier/regressor/clustering signals, retrieval, prompt assembly, provider routing, and validation gates before the output is returned.
>
> Current complete corpus pack is Singapore Tort. UK and US Tort are the next target packs after source/licensing review. It runs locally with Ollama by default, with OpenAI/Anthropic/Gemini/local-provider adapters behind the same service layer.
>
> What is worth inspecting:
> - `src/ml/pipeline.py` for the ML foundation layer
> - `src/services/workflow_facade.py` for orchestration
> - `src/services/corpus_medallion.py` for bronze/silver/gold corpus provenance
> - `src/api/routes/demo.py` for the pipeline trace demo
> - `src/services/validation_service.py` for validation gates
>
> This is not a lawyer and not a bar-review replacement. The narrow claim is: it creates inspectable, corpus-backed hypothetical practice material and exports study artifacts such as Anki TSV.
>
> I would especially like feedback on the corpus-pack interface, validation design, and whether the ML-before-LLM architecture is useful beyond legal education.

## Blog CTA

Place at top and bottom:

> Try Jikai locally: `git clone https://github.com/gongahkia/jikai`, then `make env-setup`, `make dev-setup`, and `make run`. The hosted demo link will be added once #13 is closed.

## Launch Checklist

| Gate | Owner | Pass condition | Status |
|---|---|---|---|
| Repo quickstart | maintainer | Fresh clone can run API/TUI or local API route with documented deps | Pending final dry run |
| Hosted demo | maintainer | Public URL returns pipeline demo and generation path | Blocked by #13 |
| Blog | maintainer | 2,000-3,000 words, factual claims, code references, repo/demo links | Draft ready |
| Demo video | maintainer | <=90s, actual generation + validation + export/study value | Ready |
| Blind eval | external raters | >=3 raters complete comparison sheet | Blocked by #14 |
| HN copy | maintainer | No bar-prep conflation, no "beats" claim without metric | Draft ready |
| Social posts | maintainer | X, LinkedIn, Reddit variants prepared | Draft ready |
| On-call | maintainer | First 4 hours reserved, response matrix open | Ready |
| Rollback | maintainer | Demo can be disabled or HN comment updated if service degrades | Pending hosted demo |

## Timing

Preferred window: Tuesday or Wednesday, 08:00-10:00 US Pacific.

No-go windows:

- Maintainer cannot actively reply for the first 4 hours.
- Hosted demo is unstable.
- Repo quickstart is broken.
- LLM provider health path is failing without a clear local-first fallback.
- Blind eval or quality caveat is being overstated.

## Rollback / No-Go Criteria

No-go before posting:

- Public demo 5xx rate or startup errors.
- Corpus health lacks current source timestamps.
- README quickstart fails on a clean machine.
- Blog contains unverified quality superiority claims.
- Demo video shows fixture data while implying live generation.

Rollback after posting:

- If hosted demo fails, update first HN comment with local-only instructions and mark hosted demo as temporarily unavailable.
- If output quality is challenged, link to validation code and state current limits. Do not argue that validation proves legal correctness.
- If licensing is challenged, state exact source and license status. If uncertain, say it is under review and disable affected pack.

## Companion Posts

### X / Twitter

> I built Jikai: an open-source, local-first generator for common-law legal hypotheticals.
>
> The interesting part is the architecture: ML foundation before LLM drafting. Corpus pack -> topic guard -> ML signals -> retrieval -> prompt -> validation -> study export.
>
> Repo: https://github.com/gongahkia/jikai

Thread follow-up:

> Current complete pack: Singapore Tort. UK/US Tort are next after licensing review. Not legal advice, not a bar-review replacement. The narrow goal is inspectable practice-question generation.

### LinkedIn

> I have been rebuilding Jikai as open-source infrastructure for AI-generated common-law hypothetical practice.
>
> The design is intentionally not a raw chatbot: corpus-pack scope, ML planning, retrieval, provider routing, and validation happen before LLM drafting. The current reference pack is Singapore Tort, with UK and US Tort planned after source and licensing review.
>
> I am looking for feedback from legal educators, law students, and builders on the corpus-pack model and validation gates.
>
> Repo: https://github.com/gongahkia/jikai

### r/LawSchool

Only post if self-promotion is allowed or moderators approve.

> I built an open-source local-first tool for generating legal hypotheticals for study practice. It is not legal advice and not a bar course. Current complete corpus is Singapore Tort, so I am mainly looking for feedback on whether the generated fact-pattern workflow would be useful to law students.
>
> I can share the repo if this kind of study-tool feedback post is allowed here.

### r/MachineLearning

Only post after checking live flair rules.

> [P] Jikai: ML-before-LLM pipeline for legal hypothetical generation
>
> I built an open-source project that uses a smaller ML/retrieval/validation foundation before LLM drafting. The domain is common-law exam hypotheticals. I am interested in feedback on the architecture: where deterministic guards and lightweight ML signals are useful, and where they become brittle.

## First 4 Hours On-Call Plan

| Time | Action |
|---|---|
| T-15m | Open repo, blog, demo, logs, issue tracker, health endpoint, response matrix |
| T+0 | Submit HN link; post first comment immediately |
| T+15m | Answer setup and architecture questions first |
| T+30m | Pin/update first comment if common confusion appears |
| T+60m | Check demo logs, corpus health, API errors |
| T+120m | Open issues for valid bugs found in thread |
| T+240m | Post summary comment with fixes, known limits, and next steps |

Response rules:

- Prefer code links over claims.
- Label limits directly.
- Do not debate legal advice.
- Do not ask for votes.
- Do not use AI-generated canned replies.
