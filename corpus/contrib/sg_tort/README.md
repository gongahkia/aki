# SG Tort Authored Contributions

This directory stores Singapore Tort practice hypotheticals that are authored for this repository or submitted with contributor certification.

Required files for new batches:
- `submission_template.json`: record shape.
- `CONTRIBUTOR_CERTIFICATION.md`: DCO-style certification.
- `ANONYMIZATION.md`: source and personal-data rules.
- `REVIEW_CHECKLIST.md`: reviewer gate.

Validation:

```sh
python3 script/validate_contrib_corpus.py corpus/contrib/sg_tort/corpus.json
```
