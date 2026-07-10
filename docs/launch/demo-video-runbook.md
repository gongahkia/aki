# 90-Second Demo Video Runbook

Status: recorded
Target length: 75-90 seconds
Recorded artifact: `docs/launch/jikai-demo-video.mp4`
Renderer: `script/render_launch_demo_video.py`

## Goal

Show actual workflow value for non-builder audiences:

1. Choose legal topics.
2. Show the pipeline trace.
3. Generate or display the hypothetical and model-answer path.
4. Show validation passing.
5. Show study export value through Anki/export or a saved artifact.

## Current Artifact

`docs/launch/jikai-demo-video.mp4` is a 60-second MP4 rendered from the local demo trace endpoint. It shows the generated hypothetical, validation gate, model answer, and Anki TSV preview. The hosted demo URL remains blocked by #13.

## Recording Setup

- Browser at hosted demo URL, or local `http://127.0.0.1:8000/demo/pipeline`.
- API health endpoint open in another tab.
- Terminal ready for Anki export command if export is not in UI.
- Screen resolution: 1440x900 or 1920x1080.
- Audio: optional. Captions should carry the story.

## Shot List

| Time | Visual | Narration / Caption |
|---|---|---|
| 0-8s | Repo or demo landing state | "Jikai generates legal hypotheticals with an ML foundation before LLM drafting." |
| 8-18s | Topic input: negligence + causation | "Instead of prompting a model directly, the request starts with corpus pack, jurisdiction, and topic constraints." |
| 18-35s | Pipeline trace stages | "The system runs scope guard, ML signals, retrieval, prompt assembly, generation, and validation as inspectable stages." |
| 35-52s | Generated hypothetical excerpt | "The result is a fact pattern for practice, not legal advice and not a bar-course replacement." |
| 52-68s | Validation panel | "Validation checks requested topics, party count, jurisdiction context, realism, and similarity before the output is trusted." |
| 68-82s | Export or study artifact | "The output can become a model answer, report, or Anki-compatible study card." |
| 82-90s | Repo URL + local-first note | "Open source, local-first via Ollama, current pack: Singapore Tort. UK and US packs are next." |

## Voiceover Script

> This is Jikai, an open-source generator for common-law legal hypotheticals.
>
> The main design choice is ML foundation before LLM drafting. A request starts with a corpus pack, jurisdiction, and topics. Here I am asking for Singapore Tort, negligence, and causation.
>
> The demo shows each stage: topic guard, ML scoring, retrieval, prompt assembly, generation, and validation. The LLM writes the final text, but it is not doing the whole job alone.
>
> Here is the generated fact pattern. It is study practice, not legal advice and not a full bar-review course.
>
> Before returning the result, Jikai checks topic coverage, party count, jurisdiction context, realism, and similarity. If the output fails the gate, it can be regenerated or flagged.
>
> The value for students is practice volume plus study workflow. The generated answer can be saved, reviewed, and exported into artifacts like Anki cards.
>
> Jikai runs locally with Ollama by default. The current complete corpus pack is Singapore Tort, with UK and US Tort planned next.

## Capture Commands

Local API:

```console
KMP_DUPLICATE_LIB_OK=TRUE uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

Health:

```console
make health
```

Anki export endpoint after at least one generation:

```console
curl -s http://127.0.0.1:8000/jobs/export-anki \
  -H 'content-type: application/json' \
  -d '{"output_path":"data/export/anki_cards.tsv","include_model_answer":true}' \
  | python3 -m json.tool
```

## Acceptance Checklist

- Actual app/demo is shown, not slides only.
- No claim that Jikai replaces legal advice.
- No claim that Jikai replaces a full bar course.
- Validation is visible.
- Export or study workflow value is visible.
- Repo URL is visible in final frame.
- Runtime errors, provider keys, and private prompts are not visible.
