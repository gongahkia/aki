# Jikai: ML Foundation Before LLM Generation

Status: draft for launch review  
Primary audience: Hacker News, legal-tech builders, law students who inspect the repo  
Repo: https://github.com/gongahkia/jikai  
Demo: local `/demo/pipeline` route now; video artifact at `docs/launch/jikai-demo-video.mp4`; hosted URL pending issue #13

## The Short Version

Most AI study tools start with a prompt. Jikai starts earlier.

The project is an open-source engine for common-law exam-question practice. It generates legal hypotheticals and model answers, but the important part is not that a large language model writes prose. The important part is that the LLM is only the final drafting stage. Before that draft is allowed to happen, the request moves through a set of smaller, inspectable systems: corpus-pack selection, topic normalization, ML scoring, structural planning, retrieval, prompt assembly, and validation.

That architecture is the difference between "ask the model for a torts question" and "assemble a constrained legal-practice artifact from a corpus, a topic taxonomy, and a validation gate." Jikai is trying to make the second path usable for law students and reusable for legal-tech builders.

The current reference corpus is Singapore Tort. The pivot is to treat Singapore Tort as one corpus pack inside a broader common-law engine, with UK and US Tort as the launch targets once licensing and source constraints are resolved. That matters because legal education is jurisdictional, but the engineering pattern is portable. A negligence hypothetical in Singapore, England and Wales, or a US 1L classroom has different authority and local flavor, but the generation workflow has the same shape: choose doctrine, retrieve grounding material, generate a fact pattern, validate the requested issues, and export something a student can study from.

## Why Not Just Prompt an LLM?

Raw prompting is easy to demo and hard to trust. A prompt can ask for a negligence hypothetical with causation and remoteness. The model can return something fluent. That fluency creates the problem: unless the system preserves intermediate state, a user cannot tell whether the requested topics were actually represented, whether the fact pattern drifted outside the corpus, whether a jurisdiction-specific detail was invented, or whether the result is just a generic exam question wearing legal vocabulary.

Jikai does not solve legal hallucination in a universal sense. It is not a legal oracle, and it is not a substitute for instruction. It narrows the problem. It makes the system answer a more concrete question: given a selected corpus pack and topic request, can we produce a practice hypothetical whose structure, retrieval context, and validation results are visible enough for a student or maintainer to inspect?

That is why the repo leans into ML-foundation-before-LLM rather than "AI tutor" language. The ML layer does not replace the LLM. It constrains it. The LLM still writes the final user-facing text, but it receives a narrower job after other code has already shaped the problem.

## The Pipeline

The main generation path is documented in the README, but the implementation is spread across focused modules:

- `src/domain/packs.py` resolves corpus packs and domain scope.
- `src/services/topic_guard.py` normalizes topics and rejects unsupported combinations.
- `src/ml/pipeline.py` coordinates classifier, regressor, and clustering components.
- `src/ml/topic_selector.py` and `src/ml/structural_planner.py` help decide which topic mix and fact-pattern shape to use.
- `src/services/corpus_service.py` and `src/services/vector_service.py` retrieve examples through vector search or overlap fallback.
- `src/services/prompt_engineering/templates.py` builds the generation prompt.
- `src/services/llm_service.py` routes to Ollama, OpenAI, Anthropic, Gemini, or a local LLM server.
- `src/services/validation_service.py` and `src/services/hypothetical_service.py` check topic coverage, party constraints, realism, similarity, and optional LLM validation.
- `src/services/export_service.py` turns outputs into study artifacts, including Anki TSV.

In practice, the request enters through the API or TUI with a corpus pack, jurisdiction, subject, topic list, party count, and user preferences. The scope guard canonicalizes that request. The ML layer scores and clusters candidate structure. Retrieval pulls grounding examples. Prompt assembly turns the structured state into model input. The provider gateway drafts. Validation checks whether the output is usable enough to return. The result can then be stored, reported, regenerated, or exported.

The point of this design is not that every stage is sophisticated. Some are deliberately simple. The point is that each stage owns one constraint and leaves evidence behind. That makes failures easier to debug than a single prompt string.

## Corpus Packs Are the Product Boundary

The early version of Jikai was built around Singapore Tort. That was useful for proving the workflow, but too narrow as a public open-source project. The current direction is to turn the corpus into a pack format: a manifest, raw source paths, license metadata, jurisdiction and subject fields, topic taxonomy, and derived bronze, silver, and gold layers.

The medallion pipeline is implemented in `src/services/corpus_medallion.py`. Bronze records preserve raw provenance: source path, source format, retrieved timestamp, content hash, and byte size. Silver records normalize extracted text and carry provenance forward. Gold records attach corpus-pack metadata, jurisdiction, subject, topics, source metadata, and license information for active retrieval.

That layering is intentionally boring. Legal corpora are full of operational risk: bad OCR, missing source metadata, ambiguous licenses, duplicate text, old scraped pages, and jurisdiction-specific topic drift. A pack has to be inspectable before it becomes model input. The medallion path makes those transformations explicit and hashable.

Recent ingestion work also adds retry, streaming, events, quarantine, and per-source health. HTTP fetches for US CAP and UK TNA sources now go through streaming helpers with jittered exponential retry. Silver-layer validation can quarantine bad records without corrupting valid output. The API health response includes ingestion source health, so a maintainer can see last-success timestamps instead of guessing whether the corpus is fresh.

That is infrastructure work, not feature sparkle. It is also the part that makes the project easier to extend. A contributor adding another common-law corpus pack should not have to learn the whole app. They should have to provide sources, a manifest, topic labels, and enough tests to prove the pack can move through bronze, silver, and gold without breaking retrieval.

## Local-First Is a Legal-Tech Feature

Jikai defaults to Ollama. The provider layer also supports remote APIs, but local-first is not an implementation detail. It changes the risk profile.

Legal education examples can contain sensitive personal study notes, professor-specific patterns, or institution-specific materials. A local generation path lets a student or educator run the engine without sending those inputs to a hosted model provider. It also lowers recurring cost. That matters for law students, where willingness to pay is limited and closed study platforms can be expensive.

The provider gateway lives in `src/services/llm_service.py` and `src/services/llm_providers/`. It handles provider initialization, health checks, fallback behavior, streaming support, circuit-breaker state, and model selection. The point is not to worship any provider. The point is to make the generation layer swappable while keeping the rest of the pipeline stable.

For a Hacker News audience, local-first also makes the repo easier to evaluate. You can inspect the code, run the API, use the fixture pipeline trace, and decide whether the architecture is reasonable without signing up for a closed service.

## Validation Is the Credibility Layer

The most obvious criticism of an AI legal-study tool is quality. That criticism is correct. If the system generates slick but wrong hypotheticals, it is worse than useless.

Jikai's answer is not "the model is smart." The answer is validation. Validation is split across deterministic checks and optional model-assisted checks. Topic validation looks for requested doctrinal coverage. Party-count checks ensure the generated fact pattern respects the requested complexity. Realism and similarity checks try to catch outputs that are too thin, too generic, or too close to existing examples. Retrieval metadata keeps the corpus context attached to the generation.

This does not prove correctness. It creates a gate. A generated hypothetical can fail the gate. That failure is a useful result because it tells the app to regenerate, report a degraded result, or expose why the output should not be trusted.

The public launch should be careful here. The defensible claim is not "Jikai eliminates hallucinations." That would be false. A defensible claim is: Jikai uses corpus grounding, ML planning, and validation gates before returning generated practice material. The repo exposes those stages so users can inspect and improve them.

That distinction will matter on HN. Builders will look for overclaiming. The launch copy should welcome that scrutiny by naming the current limits: Singapore Tort is the only complete active corpus today; UK and US packs require source and licensing review; hosted demo work is tracked separately; blind comparison against commercial tools is not complete until external raters finish it.

## The Demo Surface

The repo includes a pipeline trace surface under `src/api/routes/demo.py`. The route can serve a visual shell and a JSON trace. It defaults to fixture mode so a reviewer can inspect the pipeline shape without requiring a live LLM provider. It can also expose prompt details when explicitly requested.

This matters because the best demo is not only "watch a paragraph appear." The interesting demo is the staged view: request, scope guard, ML foundation, retrieval, prompt, generation, validation. A 90-second launch video should show that state, then show the generated hypothetical, then show the study workflow value through export or Anki.

The hosted demo is still a separate launch blocker. Until issue #13 is done, the blog should link to the repo and local demo route rather than pretending there is a public URL. That is less flashy, but it is accurate.

## Why Legal Hypotheticals Instead of Bar Prep Claims?

The most tempting launch hook is "open-source bar prep." It is also risky. Bar prep has a specific meaning, especially in the United States: multiple-choice MBE practice, essays, performance tests, jurisdiction-specific bar rules, and commercial courseware. Jikai currently generates doctrinal hypotheticals and model answers. That is adjacent to bar prep, but not the same thing.

The more defensible framing is "open-source AI hypothetical generator for common-law students." It can still compare the cost and openness of Jikai with closed study subscriptions, but it should not claim to replace an entire bar course. The honest value is unlimited practice volume, local execution, inspectable pipeline stages, corpus-pack extensibility, and export into study workflows.

That narrower claim is stronger because it can be evaluated. A student can ask for negligence and causation. The app can generate a fact pattern. The validation result can show topic coverage. The export path can produce study cards. A maintainer can inspect the source corpus and generation trace.

## What Needs to Happen Before Launch

The launch package should not go live until four gates pass.

First, the hosted demo must be stable. HN users should be able to try something without cloning the repo. A local-first project can still have a public demo, provided the demo is clearly labeled and rate-limited.

Second, the claims must be tightened. Avoid "beats Quimbee" unless the comparison is tied to a concrete dimension such as cost, openness, local execution, or generated hypothetical volume. Do not claim quality superiority until blind ratings exist.

Third, the demo video must show actual workflow value. It should not be a slide deck. It should show the pipeline trace, a generated hypothetical, a validation pass, and an export or study artifact.

Fourth, the maintainer must be on-call for the first four hours after posting. HN launch threads are not press releases. The comments are part of the launch. The right response style is factual, short, and technical: acknowledge limits, link to code, explain tradeoffs, and never ask for upvotes.

## Where This Can Go

If the corpus-pack shape works, Jikai becomes more than an SG Tort generator. It becomes a path for adding legal education corpora with explicit provenance and validation. That could mean UK Tort, US Tort, Contract, Criminal Law, Evidence, or jurisdiction-specific variants contributed by students and educators.

The hard part is not making an LLM produce legal-looking text. The hard part is building enough surrounding machinery that the generated text can be traced, constrained, and improved. Jikai's bet is that legal-study tooling should be built around that machinery first.

That is the architecture worth launching: ML foundation before LLM generation, corpus packs before generic prompts, validation before trust, and study artifacts after generation.
