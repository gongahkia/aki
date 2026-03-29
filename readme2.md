# Jikai — Analysis, Research & Improvement Roadmap

## 1. Project Assessment

### Architecture Verdict: PARTIALLY SOUND, SIGNIFICANT IMPLEMENTATION GAPS

**Sound decisions:**
- Two-stage pipeline (ML scaffold → LLM refinement) reduces hallucination via corpus grounding
- Deterministic validation avoids expensive LLM calls for quality gates
- Multi-provider LLM with circuit breaker + fallback chain (Ollama, OpenAI, Anthropic, Google, local)
- Local-first (Ollama) default for code privacy
- Dual interface (FastAPI REST + Rust TUI)
- Topic-aware orchestration with canonical topic normalization
- 28 canonical Singapore tort topics with alias resolution

**Critical flaws identified:**
1. **Name substitution regex corrupts text** — `hypo_generator.py:251` regex `\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b` matches "Singapore", "Court", "High Court" etc., injecting party names into legal terms
2. **Quality bootstrap uses length-as-proxy** — `workflow_facade.py:197-205` estimates quality purely from text length (<500=0.62, <1200=0.72, etc.), poisoning all downstream ML models
3. **Entity extraction false negatives** — `validation_service.py:239` uses substring matching (`word in e`) instead of word-boundary matching, filtering out valid entities containing "Court", "Law", etc.
4. **Topic validation is context-blind** — `validation_service.py:300` bare keyword matching (`kw in text_lower`) catches "duty" in unrelated contexts like "feudal duty"
5. **Structural planner never trains** — `structural_planner.py` has no labeled training data; always falls back to hardcoded rules, making the ML component dead code
6. **Corpus fragment selection is positional** — `hypo_generator.py:243` takes sentences at 25%-75% position instead of selecting semantically relevant fragments
7. **Diversity checker rebuilds vectorizer every call** — `hypo_generator.py:386` creates new `TfidfVectorizer` + `fit_transform` on every diversity check

---

## 2. Competitive Landscape

### Direct Competitors: NONE

Jikai is the only open-source project combining ML classification + LLM generation for jurisdiction-specific legal hypothetical generation. The legal AI FOSS space is dominated by:

| Category | Examples | Relevance to Jikai |
|----------|----------|-------------------|
| RAG Q&A chatbots | OLAW (Harvard, 135★), LawGlance (238★), LawGPT | Different goal: answer questions, not generate hypotheticals |
| Legal NLP tools | LexNLP (771★), OpenNyAI (87★) | Extraction/classification only |
| Benchmarks | LegalBench (558★), LexGLUE, Pile of Law | Evaluation datasets, not generation |
| SG-specific | LLM-RAG-singapore-lawyer (1★) | Dormant, Q&A only |
| Educational AI | SocraticQuizbot (5★) | Quizzes on readings, doesn't generate hypotheticals |
| Legal case gen | CaseGen (16★) | Chinese law benchmarks, not educational tool |

### Institutional (Closed Source)
- **LawNet 4.0 GPT-Legal Q&A** (SAL + IMDA): AI search for SG law, handles hypothetical queries
- **NUS ScholAIstic**: GenAI for cross-examination practice
- **NUS-Google SG Law LLM**: Singapore law-specific LLM (not yet released)

### Key Differentiation
| Dimension | Jikai | Best Alternative |
|-----------|-------|-----------------|
| ML+LLM hybrid pipeline | ✓ scikit-learn → LLM | None found |
| Hypothetical generation | ✓ Full fact patterns | SocraticQuizbot (Q&A only) |
| Singapore tort law focus | ✓ 28 topics, SG corpus | LLM-RAG-sg-lawyer (dormant) |
| Multi-provider LLM | ✓ 5 providers | Most: 1-2 |
| Semantic corpus retrieval | ✓ ChromaDB + sentence-transformers | OLAW (CourtListener API) |
| Quality validation pipeline | ✓ ML + deterministic gates | CaseGen (LLM-as-judge) |
| Interactive TUI | ✓ Rust/ratatui | Most: Streamlit |

---

## 3. Domain Research Findings

### Legal Hypothetical Generation: Best Practices
1. **RAG grounding is essential** — Stanford found 69-88% hallucination rates without retrieval (Magesh et al., 2025)
2. **Multi-stage validation** — Even RAG systems hallucinate 17-33% (Lexis+ AI, Westlaw AI)
3. **Iterative refinement** — LLM critique+revision cycles significantly improve output (arXiv:2508.08314)
4. **Jurisdiction-specific grounding** — Generic LLMs lack SG-specific knowledge (e.g., Spandeck test for duty of care)
5. **Human-in-the-loop** — All literature requires human verification before educational deployment
6. **Complexity control** — Calibrated difficulty levels essential for pedagogy

### Hallucination in Legal AI
- LLMs hallucinate 69-88% on specific legal queries without RAG (arXiv:2401.01301)
- Worst performance on oldest and newest cases
- Contra-factual bias: LLMs assume factual premises are true even when wrong
- RAG reduces but doesn't eliminate: Lexis+ AI still 17%, Westlaw AI 17-33%

### Singapore Tort Law Education
- Key textbook: *The Law of Torts in Singapore* (2nd Ed), Gary Chan (SMU) — covers all 28 topics in Jikai
- No publicly available SG tort law datasets on GitHub/HuggingFace
- LawNet data behind paywall
- AAAI-26 Bridge AI+Law conference scheduled in Singapore

### Legal-Domain Models
| Model | Params | Domain | Note |
|-------|--------|--------|------|
| SaulLM-7B/54B/141B | 7B-141B | General legal | MIT, 400B+ token corpus |
| Legal-BERT | 110M | English legal | 12GB legal text, outperforms general BERT |
| InLegalBERT | 110M | Indian legal | From IIT Kharagpur Law-AI |

---

## 4. Feature Roadmap (Prioritized)

### P0: Critical Bug Fixes
- [ ] Fix name substitution regex false positives (`hypo_generator.py`)
- [ ] Fix entity extraction substring matching (`validation_service.py`)
- [ ] Fix quality score estimation length bias (`workflow_facade.py`)
- [ ] Cache diversity checker vectorizer (`hypo_generator.py`)
- [ ] Fix case citation path handling (`templates.py`)

### P1: Core Improvements
- [ ] Context-aware topic keyword matching (`validation_service.py`)
- [ ] Semantic corpus fragment selection (`hypo_generator.py`)
- [ ] Abbreviation-aware sentence splitting (`hypo_generator.py`)
- [ ] User feedback → training data pipeline (`database_service.py`, `workflow_facade.py`)
- [ ] Optional LLM validation pass (`validation_service.py`)
- [ ] Simplify structural planner to rule-based only (`structural_planner.py`)

### P2: New Features
- [ ] Legal-BERT embedding model option (`vector_service.py`)
- [ ] Model answer generation for hypotheticals (`hypothetical_service.py`, `templates.py`)
- [ ] Corpus-calibrated difficulty levels (`complexity_controller.py`)
- [ ] Anki flashcard export (`export_service.py`)
- [ ] Batch generation with topic coverage matrix (`workflow_facade.py`)

### P3: Future Considerations
- [ ] Fine-tuned Legal-BERT for SG tort classification
- [ ] Reactive hypotheticals (student-responsive, per Steward 2024)
- [ ] LegalBench evaluation integration
- [ ] Socratic dialogue mode
- [ ] Multi-jurisdiction expansion (Contract, Equity)

---

## 5. Academic References

1. Magesh et al. "Hallucination-Free? Assessing the Reliability of Leading AI Legal Research Tools" — Stanford, 2025
2. Steward, "Reactive Hypotheticals in Legal Education" — Akron Law Review Vol 57, 2024
3. Harrington, "Introducing QuizBot: An Innovative AI-Assisted Assessment in Legal Education" — SSRN, 2024
4. "Large Legal Fictions: Profiling Legal Hallucinations in LLMs" — arXiv:2401.01301, 2024
5. "Automated Commit Message Generation with Large Language Models" — IEEE TSE, arXiv:2404.14824
6. "GenAI vs. Law Students: Criminal Law Exam Performance" — Taylor & Francis, 2024
7. "Assessing the Quality of AI-Generated Exams" — arXiv:2508.08314, 2025
8. Simon, "Focused and Fun: A How-to Guide for Creating Hypotheticals for Law Students" — Scribes
9. "Large Language Models Meet Legal AI: A Survey" — arXiv:2509.09969, 2025
10. Chan, *The Law of Torts in Singapore* (2nd Ed) — SAL Academy Publishing

---

## 6. Value Assessment

**Does this project have value?** Yes — it occupies a genuine gap in the legal education AI space. No open-source tool generates jurisdiction-specific legal hypotheticals with ML+LLM hybrid architecture.

**How to add more value:**
1. Fix critical bugs (quality bootstrap poisoning ML models is the highest-priority issue)
2. Add model answer generation (transforms from question generator to complete study tool)
3. Add Anki export (meets students where they already study)
4. Implement feedback loop (models improve from actual usage)
5. Add Legal-BERT embeddings (domain-specific > general-purpose for legal text)
6. Publish corpus as HuggingFace dataset (no SG tort law datasets exist publicly)
