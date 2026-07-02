# Jikai-Eval — SG Tort v1

Held-out evaluation set for the Jikai generation pipeline. **Not used for training**; the training corpus at `corpus/labelled/sg_tort/corpus.json` stays frozen at 41 entries for reproducibility. This set is used exclusively by `script/run_jikai_eval.py` and the ablation runner.

## File

`sg_tort_v1.jsonl` — 50 held-out SG-tort eval cases, one JSON per line, matching `src/evals/models.EvalCase` (with an additional `relevant_corpus_ids` field in `expected_output` for retrieval metrics).

## Case shape

```json
{
  "name": "unique_case_id",
  "inputs": {
    "topics": ["negligence", "causation"],
    "num_parties": 3,
    "complexity": 3,
    "seed": "sg-tort-v1-01",
    "query": "short retrieval query"
  },
  "expected_output": {
    "contains": ["duty", "breach", "causation"],
    "tort_elements": ["duty", "breach", "causation", "damage"],
    "relevant_corpus_ids": ["sg_tort_neg_001"],
    "min_length": 400,
    "statutes": ["Contributory Negligence and Personal Injuries Act"]
  },
  "metadata": {
    "jurisdiction": "sg",
    "source_authority": "Spandeck Engineering v DSTA [2007] SGCA 37",
    "difficulty": "medium",
    "category": "Negligence-Based"
  }
}
```

## Coverage

| Category | Cases |
|----------|-------|
| Negligence-Based (duty, standard, causation, remoteness, contributory) | 14 |
| Intentional Torts (battery, assault, false imprisonment, trespass) | 8 |
| Liability (vicarious, occupiers, product, employers, strict) | 12 |
| Specific Torts (defamation, nuisance, harassment) | 8 |
| Damages (economic loss, psychiatric harm) | 4 |
| Doctrines & Defences (Rylands, consent, illegality, limitation, res ipsa, novus actus, volenti) | 8 |

Difficulty: 8 easy, 21 medium, 21 hard.

## Sources

All authorities cited in `metadata.source_authority` are open-access or repository fixtures:

- **SAL Annual Review of Singapore Cases — Tort Law chapters (2014–2024)** — open access via [journalsonline.academypublishing.org.sg](https://journalsonline.academypublishing.org.sg/Journals/Singapore-Academy-of-Law-Annual-Review-of-Singapore-Cases). Provides doctrinal framing and case selection for the SG-specific fact patterns.
- **Singapore Law Gazette** — open access, [lawgazette.com.sg](https://lawgazette.com.sg). Recent tort features (2017 onwards).
- **Singapore Law Watch Ch. 20 Law of Negligence** — [singaporelawwatch.sg](https://www.singaporelawwatch.sg/About-Singapore-Law/Commercial-Law/ch-20-the-law-of-negligence). Official commentary.
- **eLitigation.sg** — [elitigation.sg](https://www.elitigation.sg). Full text of Singapore Supreme Court judgments (used for `Lo Kok Jong v Eng Beng [2024]`, `[2024] SGHC 36`, etc.).
- **ASEAN Law Association — SG legal system chapter on tort** — [PDF](https://www.aseanlawassociation.org/wp-content/uploads/2019/11/ALA-SG-legal-system-Part-5-3.pdf).
- **Common-law leading cases** (Donoghue v Stevenson, Wagon Mound, Rylands v Fletcher, etc.) — public-domain historical authorities.

## Licensing

This eval set contains only **case identifiers**, **doctrinal keywords**, and **short retrieval queries** authored for this repository. It does not redistribute headnotes or judgment text. See the individual sources above for their own terms.

## Version

- `v1` — 2026-07-02 — 50 cases, initial release.

Future versions should expand coverage (currently light on assault, harassment sub-doctrines, and multi-jurisdiction cross-references) and add gold model-answer references for direct BLEU/ROUGE comparison.
