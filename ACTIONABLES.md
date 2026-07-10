# ACTIONABLES

Audit date: 2026-07-10.
Scope: exam-practice generation for students actively studying law hypotheticals.
Mode: audit-only; this file is the handoff for a future coding agent.

## Bottom Line

The repo does not yet have an extensive online hypo corpus.

Verified local corpus:
- `corpus/labelled/sg_tort/corpus.json`: 41 SG tort fixture records.
- `corpus/clean/tort/corpus.json`: 41 SG tort records.
- `corpus/clean/us_tort/corpus.json`: 5 US tort case-law records.
- `corpus/clean/uk_tort/corpus.json`: 5 UK tort case-law records.
- 21 of 41 SG records match a rough exam-cue regex: `advise|discuss|you may assume|model answer|problem question|essay|hypothetical|IRAC`.
- The UK/US packs are case-law references, not practice-hypo packs.

[Inference] Jikai is differentiated as an exam-practice generator only if the corpus, feedback loop, and student study workflow become first-class. It is not yet corpus-rich enough to claim serious practice coverage.

## P0 Decisions Needed

1. Decide whether bundled practice content may include CC BY-NC-SA material.
   - If yes, add attribution, noncommercial, and share-alike compliance to corpus exports.
   - If no, keep CALI and similar material as link-only/eval-only metadata, or require explicit permission.

2. Decide whether the first real product scope is SG tort only.
   - Recommended: SG tort first; add common-law comparator packs later.
   - Reason: public SG hypo sources are scarce; authored/consented SG material is likely required.

3. Decide whether hosted demo remains public.
   - If public, auth and endpoint lockdown are P0 before LLM/corpus/job endpoints are exposed.

## P0 Tasks

### 3. Stop Treating Public Web as Reusable Text

Codify this rule:

Public URL != permission to commit full text.

Files/surfaces:
- `script/fetch_*.py`
- `src/services/scraper_service.py`
- `docs/*corpus-source-decision.md`
- `corpus/packs/*/manifest.json`

Acceptance:
- Fetch scripts write full text only when registry status is `allowed`.
- Restricted/unknown sources can write only URL, title, date, jurisdiction, topic tags, and short repo-authored notes.
- Tests cover blocked ingestion.

### 4. Build a Student-Useful Record Schema

Current records mostly store fact pattern + topics. Active students need more.

Add optional fields:
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

Acceptance:
- Existing records migrate without data loss.
- New generation/eval can distinguish fact pattern from model answer.
- Export/TUI can hide model answer until requested.

### 5. Expand SG Tort via Authored and Consented Hypos

Web scan did not verify an extensive reusable SG tort hypo corpus. Treat SG expansion as authored/permission-based.

Tasks:
- Add `corpus/contrib/` workflow for student/lecturer/authored submissions.
- Add contributor license agreement or DCO-style certification for hypo text.
- Add anonymization rules: no real exam paper text unless permission is explicit.
- Add review checklist: topic coverage, SG law fit, answer quality, source originality.

Acceptance:
- 80+ SG tort practice hypos with clean authorship/permission.
- At least 5 records per canonical core topic: negligence, duty, breach/standard, causation, remoteness, contributory negligence, consent/volenti, illegality, vicarious liability, nuisance, trespass, defamation, intentional torts.
- Every record has a model answer or issue list.

### 6. Use CALI as the First External Open-Education Candidate

Candidate:
- CALI eLangdell bookstore: https://www.cali.org/the-elangdell-bookstore
- `Tort Law: A 21st-Century Approach`: https://saidtorts2d.lawbooks.cali.org/

Verified signal:
- CALI page says eLangdell books are free, peer-reviewed, Creative Commons licensed.
- The online lawbook states CC BY-NC-SA 4.0 except where otherwise noted.
- It includes interactive questions, Socratic scripts, and tort modules.

Risk:
- CC BY-NC-SA is noncommercial and share-alike.
- MIT code license does not automatically make bundled corpus text MIT.

Tasks:
- Add source registry entry with `text_commit_allowed` pending owner decision.
- If accepted, create separate pack `us_tort_cali_open_education`.
- Preserve attribution per record.
- Mark outputs derived from CALI with noncommercial/share-alike constraints.
- Prefer extracting question metadata and topic tags first; full-text ingestion only after license decision.

Acceptance:
- No CALI text is committed until license compatibility is accepted.
- If accepted, import only clearly licensed book/question sections and retain attribution.

### 7. Register Bar Exam Sources as Link-First, Permission-Later

Candidates:
- California past exams: https://www.calbar.ca.gov/admissions/applicant-resources/past-exams
- New York BOLE past questions/sample answers: https://www.nybarexam.org/ExamQuestions/ExamQuestions.htm
- Texas BLE questions/selected answers: https://ble.texas.gov/selected-answers
- NCBE official study aids: https://www.ncbex.org/study-aids

Observed:
- CA publishes examination questions, essay questions, selected answers, and performance tests across many administrations.
- NY publishes past essay questions with sample candidate answers.
- Texas publishes UBE/MEE/MPT questions and selected answers.
- NCBE sells/distributes official study aids and free sample questions.

Risk:
- Publication for study does not prove redistribution or model-training permission.

Tasks:
- Add all as registry entries with `text_commit_allowed=false` until terms/permission are cleared.
- Build metadata-only crawler: exam date, jurisdiction, component, subject, URL, PDF hash.
- Add manual review workflow to classify tort essays without copying prompt text.
- Use links for student-facing source comparison, not bundled corpus text.

Acceptance:
- Metadata can be committed.
- Full prompt/answer text cannot be committed unless registry status changes to `allowed`.

### 8. Rework Evaluation Around Student Utility

Current eval docs are mostly dry-run/smoke. Build real student-facing eval.

Rubric dimensions:
- issue spotting coverage
- fact sufficiency
- legal ambiguity
- SG law fit
- answer structure
- citation/rule accuracy
- distractor quality
- difficulty calibration
- feedback usefulness

Acceptance:
- 30 held-out SG tort hypos with human rubric ratings.
- At least 2 independent law-trained raters per item.
- Report inter-rater agreement.
- Mark dry-run metrics visually and textually as dry-run until replaced.

### 9. Add Practice Modes Students Actually Need

Tasks:
- `issue_spotting`: fact pattern only; answer hidden.
- `progressive_hints`: hint 1 topic, hint 2 rule, hint 3 issue structure.
- `timed_exam`: timer + answer box + post-attempt reveal.
- `model_answer_review`: compare user answer to issue/rubric checklist.
- `spaced_topic_drill`: repeat weak topics.
- `difficulty_ladder`: easy/medium/hard by issue count and ambiguity.

Surfaces:
- API request/response schemas.
- Rust TUI guided/chat screens.
- Export service.
- DB history.

Acceptance:
- Students can attempt before seeing answer.
- Generated artifacts include rubric and issue checklist.
- TUI/API both expose the same practice modes.

### 10. Fix Local Quality Gates Before Scaling

Current verified failures from audit:
- Full pytest fails on Ollama model-state dependence.
- `flake8` fails.
- `black --check` fails.
- `isort --check-only` fails.
- `mypy` fails.

Tasks:
- Mock Ollama `list_models` in unit tests.
- Format/sort files.
- Fix or quarantine mypy errors with narrow annotations.
- Add a single `make verify` target for Python + Rust.

Acceptance:
- `uv run --python 3.13 python -m pytest tests/ -q` passes.
- `uv run --python 3.13 python -m flake8 src tests` passes.
- `uv run --python 3.13 python -m black --check src tests` passes.
- `uv run --python 3.13 python -m isort --check-only src tests` passes.
- `uv run --python 3.13 python -m mypy src tests --ignore-missing-imports --follow-imports=skip` passes or has documented baseline.
- `cd tui && cargo test` passes.

### 11. Harden Hosted API Before Any Public Student Use

Risk:
- No auth.
- Global LLM provider mutation.
- Corpus/job/file-output endpoints exposed.
- Public generation can burn API spend.

Tasks:
- Add API key auth or disable mutating routes in hosted mode.
- Remove global provider mutation from multi-user path.
- Lock `/jobs/*`, `/corpus/add`, export output paths, cleanup, provider selection.
- Add per-route rate limits and body-size limits.

Acceptance:
- Public demo exposes only safe demo/generate surfaces.
- Mutating/admin routes require auth.
- Provider selection is request-scoped or admin-only.

## P1 Tasks

### 13. Build a Safe Synthetic Expansion Pipeline

Purpose: create more SG-style practice volume without copying restricted online exam text.

Tasks:
- Generate synthetic hypos from repo-authored topic templates and authority metadata.
- Require citation/rule source from `authorities.json`.
- Add novelty checks against existing corpus.
- Add human review queue before adding to gold corpus.

Acceptance:
- Synthetic records are marked `generated_reviewed`.
- No generated record enters default retrieval until reviewed.
- Similarity threshold blocks near-duplicates.

### 14. Add Model-Answer Quality Controls

Tasks:
- Validate IRAC structure.
- Check expected issues are addressed.
- Check answer does not cite unsupported cases/statutes.
- Add "missing issue" and "false issue" diagnostics.

Acceptance:
- Validation report distinguishes hypo quality from answer quality.
- Student feedback is actionable, not only pass/fail.

### 15. Add Corpus Packs for Common-Law Comparator Practice

Candidates:
- `us_tort_case_law`: existing CAP-based cases.
- `uk_tort_case_law`: existing TNA Open Justice Licence cases.
- `us_tort_open_education`: CALI if license decision passes.
- `bar_exam_link_index`: metadata-only unless permission clears.

Acceptance:
- Each pack has source registry entries.
- Pack selection is explicit in API/TUI.
- SG generation does not silently use US/UK law unless user asks.

### 16. Create a Baseline Comparison Harness

Compare:
- Jikai generated hypo.
- Existing repo fixture hypo.
- Licensed external hypo, if cleared.
- Generic LLM prompt output.

Metrics:
- student utility
- legal accuracy
- issue density
- novelty
- answer helpfulness

Acceptance:
- Blind rater packet generator works without leaking source labels.
- Results distinguish dry-run, internal, and external-human eval.

## P2 Tasks

### 17. Build Student Progress Tracking

Tasks:
- Store attempts, self-ratings, rubric misses, repeated weak topics.
- Add spaced repetition queue.
- Export study plan.

Acceptance:
- User can see weak topics over time.
- TUI/API expose attempt history.

### 18. Add Course/Module Configuration

Tasks:
- Let educators define topic syllabus, allowed authorities, difficulty profile, and exam style.
- Support "NUS-style SG tort", "generic common-law tort", and "bar essay" profiles only when backed by data.

Acceptance:
- Prompt overlays and validators are pack/profile-specific.

### 19. Improve README Positioning

Tasks:
- Say "exam-practice generation", not "bar prep" unless bar content is cleared.
- Say current corpus size plainly.
- Mark dry-run evals plainly.
- Fix version mismatch.

Acceptance:
- README does not overclaim corpus scale, legal correctness, or benchmark rigor.

### 20. Delete ACTIONABLES.md

Once all tasks are done, delete ACTIONABLES.md

## Source Notes From Web Audit

Reusable/possible:
- CALI eLangdell: https://www.cali.org/the-elangdell-bookstore
- CALI `Tort Law: A 21st-Century Approach`: https://saidtorts2d.lawbooks.cali.org/

Published but permission/terms needed before bundling text:
- California past exams: https://www.calbar.ca.gov/admissions/applicant-resources/past-exams
- NY BOLE past questions/sample answers: https://www.nybarexam.org/ExamQuestions/ExamQuestions.htm
- Texas BLE selected answers: https://ble.texas.gov/selected-answers
- NCBE study aids: https://www.ncbex.org/study-aids
- e-lawresources tort law page: https://www.e-lawresources.co.uk/Tort-law.php
- LawTeacher tort essays: https://www.lawteacher.net/free-law-essays/tort-law

Already noted in repo as permission-required:
- 2Civility JumpStart sample torts exam Q&A.
- University of Washington Street Law tort hypotheticals.

## Non-Goals

- Do not scrape and commit random public law school PDFs.
- Do not use commercial bar-prep text.
- Do not treat case-law corpora as sufficient hypo practice.
- Do not claim extensive corpus coverage until the audit command proves it.
