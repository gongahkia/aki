# Corpus Contributions

`corpus/contrib/` is for source-clear practice records. Use it for material that is original, permissioned, or otherwise cleared for committed full text.

Rules:
- Do not submit real exam paper text unless written permission is attached.
- Do not submit paid, private, account-gated, or scraped text.
- Keep student answers hidden by default with `answer_visibility: "hidden"`.
- Each record must include `issues_expected` or `model_answer`.
- Each record must carry a registered `source.source_id`.

Run:

```sh
python3 script/validate_contrib_corpus.py
```
