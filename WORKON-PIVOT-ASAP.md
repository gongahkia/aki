# WORKON-PIVOT-ASAP

Strategic memo. Status: locked direction, open-ended timeline.

## 0. Decision summary (locked)

- **Goal**: GitHub stars + HN virality within the legal tech niche.
- **Pivot scope**: Broaden the engine. SG Tort becomes one corpus among many.
- **Coverage at launch**: Common-law core — SG + UK + US.
- **Positioning angles (dual)**: (a) legal exam-question *infrastructure*, (b) ML-foundation-before-LLM as the novel framing.
- **HN launch hook**: "Open-source bar-prep that beats $X/yr Quimbee" — provocative comparison. Risk-managed below.
- **Doc style**: Strategic memo (this file).
- **Timeline**: open-ended; phased gates instead.
- **Protected assets**: none — anything can be rewritten if it serves virality in legal tech.

## 1. Honest diagnosis of the current state

- 0 stars, 0 forks since Nov 2024. ~16 months of build, zero discovery.
- Positioning collapses TAM three times over: *Singapore* × *Tort* × *students*. Each axis is narrow; the product is the intersection.
- README leads with personal story (finals season 2024), reference to a manga character ("Jikai" = sorcery from Kagurabachi), and a LinkedIn poll. [Inference] Reads as portfolio/passion project, not infrastructure.
- The actual reusable assets are buried under that framing: ML-as-foundation pipeline, multi-provider LLM abstraction (Ollama/OpenAI/Anthropic/Gemini/local), Rust TUI, FastAPI surface with async jobs, ChromaDB-backed RAG, Anki export, async job system, validation pipeline. Any one of these is HN-front-page material if framed correctly. None are framed correctly.
- `src/ml/pipeline.py` enforcing ML-foundation-before-LLM (per README) is genuinely novel framing; HN audiences respond to "we constrain the LLM, not the other way around". Currently invisible in the pitch.

## 2. Market analysis

### 2.1 Commercial / sales viability — bluntly negative as-is

- [Inference] Singapore LLB cohort across NUS + SMU is small (low thousands total across all years; ~300–500 Torts-taking students/yr). [Speculation] Even 100% capture at Quimbee-tier pricing yields ~$20–50K/yr ceiling. Not a business.
- Law students are notoriously low-WTP. Real money is institutional B2B (12–24 month sales cycles to law schools / bar prep companies) — and a single-jurisdiction tool gets nowhere there.
- US bar-prep market is large but [Unverified] dominated by BARBRI (1.3M+ historical users), Themis, Kaplan, plus Studicata (AI-native, launched early 2025, [Unverified] 60K case briefs generated in months).
- [Unverified] Quimbee Bar Review was discontinued post-BARBRI acquisition (July 2025). Quimbee now offers SideBar Videos only. **This is an opening, not a closed door.**

### 2.2 Viral OSS / HN viability — the real opportunity

- [Unverified] "Mike" (Will Chen, ex-Latham): 1K GitHub stars in 72 hours, fastest-growing legal tech repo in history.
- [Unverified] OpenClaw (Peter Steinberger): 9K → 60K stars in days, 210K+ stars total in early 2026 — high-quality legal training data.
- [Inference] Pattern: HN-viral legal repos are (a) general-purpose, (b) reusable as infrastructure, (c) carry a sharp narrative ("dethrones X", "Y in N hours", "open-source replacement for $Z/yr SaaS"), (d) often from credentialed authors (Latham lawyer, PSPDFKit founder).
- [Inference] Jikai today has none of the four. After pivot it can credibly have (b), (c), (d) — (a) handled by broadening coverage and exposing the engine.
- Local-first via Ollama is a strong HN signal — [Inference] sovereignty / cost / privacy arguments resonate with that audience. Keep and lead with it.

### 2.3 Competitive landscape post-pivot

| Player | Stack | Audience | Threat to Jikai-after-pivot |
|---|---|---|---|
| BARBRI / Themis / Kaplan | Closed, content-heavy | US bar takers | High in revenue, low in OSS/HN attention |
| Studicata | AI-native, US-focused | US 1Ls + bar | Highest direct competitor in *generated* content quality |
| Quimbee SideBar | Supplemental video | US law students | Low — different format |
| Mike, OpenClaw, Harvey, Lexis+AI | General legal AI | Practitioners | Low — different problem (practice vs. study) |
| Law School AI, similar small tools | Flashcards/MCQ from syllabus | Law students | Medium — same niche but shallow |
| Anki + manual flashcards | DIY | Students globally | High inertia; we must integrate, not replace |

[Inference] The white space is: **open-source, common-law-multi-jurisdiction, ML-grounded hypothetical & exam-question generator that ships with curated corpora and integrates with Anki/study workflows**. Studicata is the only one even close, and they are closed-source US-only.

## 3. Pivot thesis

**One sentence**: *Jikai becomes the open-source infrastructure layer for AI-generated common-law exam questions, with an ML-foundation pipeline that constrains hallucination by design, shipping SG+UK+US Tort as launch corpora and a contribution path for the rest of the curriculum.*

Two narratives, same artifact:
1. **For HN / builders / researchers** — "ML constrains LLM, not the other way around. Multi-stage classifier → regressor → clusterer → semantic retrieval → templated LLM generation → validation. Local-first via Ollama. Rust TUI. Bring your own corpus."
2. **For law students / educators / press** — "The open-source bar-prep tool that beats $X/yr Quimbee/BARBRI on practice volume — runs on your laptop, free forever, common-law jurisdictions."

The narratives reinforce: the technical depth makes the educational claim credible; the educational claim makes the technical depth matter.

## 4. The HN launch hook — and how to de-risk it

**Chosen hook**: *"Open-source bar-prep that beats $X/yr Quimbee."*

**Risks**:
- [Unverified] Quimbee's flagship Bar Review was discontinued July 2025 — direct comparison may read as outdated. Reframe target to current incumbents: BARBRI (~$3K+ courses) or Studicata.
- HN scrutinizes provocative claims. If "beats" is not defended on at least one concrete metric (questions generated/hour, cost, jurisdictions, corpus size, model-answer accuracy), the thread implodes.
- Bar prep ≠ law school hypotheticals. Bar = MBE multiple-choice + essays. Jikai = fact-pattern hypotheticals. Conflating them invites pile-on. Either broaden the engine to MBE-style output (significant work) or pick a more honest comparison.

**Recommended refined framing** (still provocative, defensible):
> *"Open-source AI hypothetical generator for common-law students. Generates unlimited Tort fact patterns with model answers, runs locally on Ollama, exports to Anki. Replaces the $200/yr Quimbee/Studicata subscription for hypothetical practice."*

**Defended metrics** (must hold before launch):
- N hypotheticals generated/min on commodity hardware.
- N curated cases across SG + UK + US.
- N% of generated outputs passing the ML validation gate.
- Side-by-side: one Jikai hypothetical vs one Quimbee/Studicata equivalent, blind-rated by ≥3 law students/grads.

## 5. Coverage strategy — common-law SG + UK + US

**Why this scope**:
- Shared doctrinal DNA (negligence, duty of care, causation, remoteness, defamation, etc.). Minimum new abstractions vs. adding civil-law jurisdictions.
- Combined audience = the relevant English-language legal-education internet.
- One subject (Tort) across three jurisdictions ships deeper than three subjects across one jurisdiction.

**Corpus acquisition** (the real bottleneck):
- SG: already done. `corpus/clean/tort/corpus.json`.
- UK: BAILII is the canonical free source for English & Welsh case law. Existing scrapers in `script/` and `lib/` are the right shape. [Inference] Need a new scraper + cleaner per jurisdiction; reuse the ingestion adapters already present (BeautifulSoup4, lxml, PyMuPDF).
- US: CourtListener / Caselaw Access Project (Harvard) — bulk data exists, [Inference] permissive licensing for non-commercial use; verify before redistribution. Tort is a 1L subject so volume of teaching cases is well-defined.
- Corpus must be partitioned by jurisdiction tag and queryable by `(jurisdiction, topic, subtopic)`. Today's schema looks topic-only — needs extension.

**Abstractions to add**:
- `Jurisdiction` as a first-class concept in models, prompts, retrieval filters, and validation rules.
- A `corpus-pack` plugin shape — declarative manifest (jurisdiction, subject, source URLs, license, topic taxonomy) so the community can contribute additional jurisdictions or subjects without forking core.
- Per-jurisdiction prompt templates (`src/services/prompt_engineering/templates.py`) — common-law shared base + jurisdictional overlays.

## 6. What to do with current technical assets

User has explicitly authorized rewriting anything. Decisions below are by ROI on virality, not sentiment.

### 6.1 Keep and amplify
- **ML pipeline** (`src/ml/pipeline.py`, `classifier.py`, `regressor.py`, `clustering.py`, `topic_selector.py`, `structural_planner.py`) — *this is the differentiator*. Lead the technical narrative here. Write a blog post explaining the architecture; that post is the HN submission, with the repo as the artifact.
- **Multi-provider LLM abstraction** (`src/services/llm_service.py`, `src/services/llm_providers/`) — local-first via Ollama is HN gold. Keep, document prominently.
- **Validation pipeline** including the recent Legal-BERT + LLM validation work (commits `a53ff5a`, `21da92b`) — this is the credible answer to "but it hallucinates". Surface it in the README's first 10 lines.
- **Anki export** (commit `909d68d`) — high-leverage student-tool resonance. Keep and feature.
- **Batch generation with topic coverage** (commit `762b3fc`) — directly supports the "unlimited practice questions" pitch. Keep.
- **FastAPI + async job system** — enables a hosted demo (next section). Keep.

### 6.2 Refactor for generalization
- Corpus schema: add `jurisdiction` field everywhere (models, DB schema, retrieval, prompts, validation).
- Prompt templates: extract jurisdiction-specific bits behind a strategy/overlay system.
- Topic taxonomy: per-jurisdiction taxonomy files instead of one hardcoded list.
- Provider registry: already extensible — document the contribution path.

### 6.3 Demote, don't delete
- **Rust TUI** (`tui/`): keep but no longer the headline. The dual-stack maintenance burden is real and HN audiences mostly evaluate via README + demo + code, not TUI screenshots. Move from "primary surface" to "power-user surface"; lead instead with a CLI or a hosted demo video.
- **Manga-character branding** in README references section: keep for personality, but not until after the technical pitch lands. Move to bottom of README.

### 6.4 Drop
- Personal-story rationale ("finals season December 2024", LinkedIn poll image) as the lede. Move to bottom or remove. It signals personal project.
- Any single-jurisdiction assumptions hardcoded into prompts, validators, or topic lists.

### 6.5 Build new
- **Hosted demo** at a stable URL (e.g. Fly.io / Railway). HN visitors will not `make dev-setup`. Either a Streamlit/Gradio front or a minimal Next.js page that hits the FastAPI backend. *This is the single biggest conversion lever for HN traffic → stars.*
- **Show-me-the-pipeline page**: a single page that visualizes one generation end-to-end (input topics → ML stage outputs → retrieved cases → prompt → LLM output → validation pass/fail). [Inference] This is the screenshot that ends up on Twitter.
- **CONTRIBUTING.md** with the corpus-pack plugin spec. Lower the contribution barrier so jurisdictions/subjects accrete from the community.
- **One blog post** (2,000–3,000 words) on the ML-foundation-before-LLM architecture, with code references. *This* is what gets submitted to HN; the README points at it.
- **Comparison artifact**: side-by-side blind-eval results (Jikai vs. Quimbee/Studicata on hypothetical quality). Without this the provocative hook collapses.
- **A demo video** (≤90s) — necessary for non-builder press / law-student audience.

## 7. Phased plan (open-ended timeline, gated by outcomes not dates)

### Phase 0 — Stop the bleeding (days)
- Rewrite README top-of-fold around the new positioning. Manga reference and personal-rationale move to bottom.
- Add the architecture diagram and one screenshot of the ML pipeline output near the top.
- Add `WORKON-PIVOT-ASAP.md` to gitignore? No — keep visible as the working memo.

### Phase 1 — Generalize the engine (weeks)
- Add `jurisdiction` as a first-class concept across schema, retrieval, prompts, validation.
- Define the corpus-pack manifest format.
- Refactor SG Tort into the new corpus-pack shape as the reference implementation.
- Backfill tests for cross-jurisdiction correctness.

**Gate to Phase 2**: an internal user can swap corpus packs at runtime and generate hypotheticals against either.

### Phase 2 — Two more corpora (weeks)
- UK Tort corpus via BAILII ingestion. Reuse existing scraper/cleaner shape.
- US Tort corpus via CourtListener / Caselaw Access Project. Verify licensing first.
- Per-jurisdiction prompt overlays and validation rule overlays.

**Gate to Phase 3**: blind-rate 10 hypotheticals per jurisdiction; ML validation pass rate ≥ target (define before testing — [Inference] suggest ≥80%).

### Phase 3 — Productionize the pitch (weeks)
- Hosted demo deployed and stable.
- Pipeline visualization page.
- 90-second demo video.
- Blog post drafted and edited.
- Side-by-side comparison artifact with Quimbee/Studicata samples.
- CONTRIBUTING.md + corpus-pack spec finalized.

**Gate to Phase 4**: dogfood — give 5 law students or recent grads access for 1 week; collect feedback; iterate.

### Phase 4 — Launch (single day window)
- Tuesday or Wednesday US morning post to HN ("Show HN: …").
- Same day: blog post live, Twitter/X thread with pipeline screenshot, LinkedIn post to law-student communities, /r/LawSchool post (read rules first), Reddit /r/MachineLearning Show-and-Tell.
- On-call to respond to HN comments within first 4 hours — non-negotiable.

### Phase 5 — Sustain (months)
- Ship one new corpus pack or major feature every 2–4 weeks for ~3 months. Sustains "active project" signal that drives steady stars.
- Open issues labelled `good-first-corpus`, `good-first-jurisdiction`.
- Track: stars/week, HN front-page rank, downloads, contributor count, /r/LawSchool mentions.

## 8. Open risks the user should know

1. **Licensing on US/UK case data** is the single highest-risk item. Get clarity before ingesting and redistributing. [Inference] CAP and BAILII have specific terms; failure to respect them is reputationally fatal for an OSS legal project.
2. **Bar exam ≠ hypothetical** confusion: if the hook says "bar prep" but the output is doctrinal hypotheticals, HN top comments will dunk. Either pivot output toward MBE-format MCQ (significant additional work) or honestly position as "hypothetical practice" and let the comparison be to practice problems, not bar exams.
3. **Quimbee/BARBRI/Studicata** could trivially copy the hypothetical-generation feature once Jikai validates the demand. The defensive moat is open-source community + corpus pack ecosystem + ML-foundation framing, not the generator itself.
4. **Solo maintainer burnout**: open-ended timeline + ambitious scope + Rust+Python dual stack. Phase 1–2 are the riskiest; defend against scope creep ruthlessly.
5. **Quality of generated hypotheticals** is what the entire pitch rests on. If a blind-rated comparison goes poorly, the hook becomes a liability. Build the comparison artifact *early*, even before phase 2 ships, to know what to improve.
6. **Dual-stack maintenance** (Python + Rust): every API change requires two updates. Consider whether the TUI is worth that ongoing tax given it's no longer the headline.

## 9. What to write next (concrete first actions)

In strict order, smallest-blast-radius first:

1. README rewrite (Phase 0) — new lede, new positioning, demote personal-story section.
2. `corpus/` schema audit — list every hardcoded SG / Tort assumption.
3. ADR for `jurisdiction` as first-class concept (one short file under `docs/` or in this memo's followup).
4. Corpus-pack manifest spec draft.
5. UK Tort ingestion script prototype against BAILII (license-clear).
6. Blind-eval rubric drafted *before* generating comparison samples.

## 10. Sources

- [AI Startups Target Law Students for Legal Market Edge — JDJournal, Apr 2026](https://www.jdjournal.com/2026/04/07/ai-startups-target-law-students-for-legal-market-edge/)
- [The 10 Legal Tech Trends that Defined 2025 — LawSites](https://www.lawnext.com/2026/01/the-10-legal-tech-trends-that-defined-2025.html)
- [85 Predictions for AI and the Law in 2026 — National Law Review](https://natlawreview.com/article/85-predictions-ai-and-law-2026)
- [Mike, the Open Source Legal AI Platform — Artificial Lawyer, May 2026](https://www.artificiallawyer.com/2026/05/04/mike-the-open-source-legal-ai-platform-will-chen-interview/)
- [Mike OSS — Legal IT Insider, May 2026](https://legaltechnology.com/2026/05/05/mike-oss-open-source-legal-ai-tool-changes-the-negotiation/)
- [OpenClaw's Meteoric Rise on GitHub — webpronews](https://www.webpronews.com/openclaws-meteoric-rise-on-github-how-an-open-source-legal-ai-project-dethroned-react-as-the-most-starred-software-repository/)
- [AI-Powered: Studicata's Game-Changer — GeekExtreme](https://www.geekextreme.com/ai-powered-studicatas-law-school-bar-exam-prep/)
- [Quimbee Bar Review & SideBar Videos — Test Prep Insight (post-BARBRI acquisition)](https://testprepinsight.com/reviews/quimbee-bar-review/)
- [Studicata — Law School & Bar Exam Prep](https://www.studicata.com/law-school-and-bar-exam-prep/)
- [legal-ai · GitHub Topics](https://github.com/topics/legal-ai?o=asc&s=stars)
- [SMU Yong Pung How School of Law — Wikipedia (audience sizing)](https://en.wikipedia.org/wiki/Yong_Pung_How_School_of_Law)
- [NUS Faculty of Law (audience sizing)](https://law1a.nus.edu.sg/admissions/faqs_jd.html)
- [Singapore Legal Tech overview — LawTech.Asia](https://lawtech.asia/legal-technology-in-singapore/)
