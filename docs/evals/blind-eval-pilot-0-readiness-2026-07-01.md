# Blind Evaluation Pilot 0 Readiness

Date: 2026-07-01
Rubric: blind-eval-rubric-v1.md
Status: protocol ready; human ratings pending

## Scope

This is a setup artifact, not a completed pilot evaluation. It records the protocol, legal baseline constraints, and data shape needed before collecting ratings.

## Current Results

| Field | Value |
| --- | --- |
| human sample size | 0 |
| paired samples rated | 0 |
| rater count | 0 |
| rater profile | pending |
| anonymization method | packet IDs only; source labels hidden |
| blinding method | samples shown as A/B with randomized order |
| scoring distribution | pending |
| preference distribution | pending |
| failure modes | pending |
| claims permitted | none |
| claims blocked | all public comparative quality claims |

## Baseline Decision

Quimbee and Studicata are not cleared baselines for committed sample text.

- Quimbee terms reviewed: https://www.quimbee.com/about/terms
- Studicata terms reviewed: https://www.studicata.com/legal/terms-of-use

Use one of these alternatives for the first pilot:

- Reviewer-written original baseline with written permission.
- Public-domain or open-licensed practice problem.
- In-house simple-prompt baseline generated and stored with the packet.
- Incumbent sample only after written permission.

## Ready-to-Run Checklist

- Choose jurisdiction and corpus pack.
- Generate 10 Jikai samples after freezing the rubric.
- Select 10 legally cleared baseline samples.
- Build packet manifest from `blind-eval-sample-manifest.template.json`.
- Randomize A/B order per packet.
- Recruit at least three eligible raters.
- Collect ratings using `blind-eval-rater-sheet.csv`.
- Summarize completed ratings with `python3 script/summarize_blind_eval_results.py docs/evals/blind-eval-rater-sheet.csv --manifest docs/evals/blind-eval-sample-manifest.json --output docs/evals/blind-eval-summary.json --markdown docs/evals/blind-eval-summary.md --require-publishable`.
- Publish aggregate results, failure modes, and claim limits.

## Blocker

#14 cannot be closed from repo work alone because the acceptance criteria require at least three legally trained blind raters and a scoring distribution. Fabricating those ratings would invalidate the artifact.
