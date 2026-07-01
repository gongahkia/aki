"""Render the launch demo video from the demo trace endpoint."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import textwrap
from pathlib import Path
from urllib.request import urlopen

from PIL import Image, ImageDraw, ImageFont

DEFAULT_TRACE_URL = (
    "http://127.0.0.1:8000/demo/pipeline/trace?topics=negligence,causation"
)
DEFAULT_OUTPUT = Path("docs/launch/jikai-demo-video.mp4")
WIDTH = 1280
HEIGHT = 720
FPS = 2


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


FONT_TITLE = _font(46, bold=True)
FONT_H2 = _font(32, bold=True)
FONT_BODY = _font(24)
FONT_MONO = _font(21)
FONT_SMALL = _font(18)


def _load_trace(url: str) -> dict:
    with urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _stage(trace: dict, stage_id: str) -> dict:
    for item in trace.get("stages", []):
        if item.get("id") == stage_id:
            return item
    raise KeyError(stage_id)


def _wrapped(text: str, width: int) -> str:
    return "\n".join(textwrap.wrap(" ".join(str(text).split()), width=width))


def _draw_lines(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    *,
    font: ImageFont.ImageFont = FONT_BODY,
    fill: str = "#17211b",
    width: int = 72,
    spacing: int = 8,
) -> None:
    draw.multiline_text(
        xy,
        _wrapped(text, width),
        font=font,
        fill=fill,
        spacing=spacing,
    )


def _base(title: str, subtitle: str = "") -> Image.Image:
    img = Image.new("RGB", (WIDTH, HEIGHT), "#f5f7f4")
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, WIDTH, 88), fill="#ffffff")
    draw.line((0, 88, WIDTH, 88), fill="#cbd6cf", width=2)
    draw.text((54, 24), title, font=FONT_H2, fill="#17211b")
    if subtitle:
        draw.text((54, 98), subtitle, font=FONT_SMALL, fill="#58645d")
    return img


def _pill(
    draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, color: str
) -> None:
    x, y = xy
    draw.rounded_rectangle((x, y, x + 190, y + 46), radius=23, fill=color)
    draw.text((x + 18, y + 11), text, font=FONT_SMALL, fill="#ffffff")


def _card(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    size: tuple[int, int],
    heading: str,
    body: str,
    *,
    accent: str = "#0f7a4f",
) -> None:
    x, y = xy
    w, h = size
    draw.rounded_rectangle((x, y, x + w, y + h), radius=10, fill="#ffffff")
    draw.rectangle((x, y, x + 8, y + h), fill=accent)
    draw.text((x + 24, y + 20), heading, font=FONT_H2, fill="#17211b")
    _draw_lines(draw, (x + 24, y + 70), body, font=FONT_BODY, width=54)


def _scene_title(trace: dict) -> Image.Image:
    img = _base("Jikai demo", "local-first common-law hypothetical practice")
    draw = ImageDraw.Draw(img)
    draw.text(
        (54, 170), "ML foundation before LLM drafting", font=FONT_TITLE, fill="#17211b"
    )
    _draw_lines(
        draw,
        (58, 250),
        "A corpus pack, topic guard, ML signals, retrieval, prompt assembly, generation, validation, and study export are visible before launch claims are made.",
        width=70,
    )
    _pill(draw, (58, 420), trace.get("mode", "fixture"), "#245f9f")
    _pill(
        draw,
        (266, 420),
        trace.get("summary", {}).get("corpus_pack", "sg_tort"),
        "#0f7a4f",
    )
    _pill(draw, (474, 420), "Ollama-ready", "#9d6200")
    return img


def _scene_pipeline(trace: dict) -> Image.Image:
    img = _base("Inspectable pipeline", "one request moves through explicit stages")
    draw = ImageDraw.Draw(img)
    stages = trace.get("stages", [])
    x = 64
    y = 170
    for idx, item in enumerate(stages):
        col = idx % 4
        row = idx // 4
        cx = x + col * 300
        cy = y + row * 150
        draw.rounded_rectangle((cx, cy, cx + 250, cy + 90), radius=12, fill="#ffffff")
        draw.text(
            (cx + 18, cy + 18), item.get("label", ""), font=FONT_SMALL, fill="#17211b"
        )
        draw.text(
            (cx + 18, cy + 50), item.get("status", ""), font=FONT_SMALL, fill="#0f7a4f"
        )
    return img


def _scene_generation(trace: dict) -> Image.Image:
    generation = _stage(trace, "generation").get("details", {})
    img = _base(
        "Generated hypothetical", "deterministic demo trace, live mode optional"
    )
    draw = ImageDraw.Draw(img)
    _card(
        draw,
        (58, 150),
        (1164, 430),
        "Fact pattern",
        generation.get("output", ""),
        accent="#245f9f",
    )
    return img


def _scene_validation(trace: dict) -> Image.Image:
    validation = _stage(trace, "validation").get("details", {})
    img = _base(
        "Validation gate", "topic, realism, exam-likeness, and similarity checks"
    )
    draw = ImageDraw.Draw(img)
    passed = "passed" if validation.get("passed") else "needs review"
    _pill(draw, (58, 142), passed, "#0f7a4f" if validation.get("passed") else "#a7332e")
    checks = validation.get("checks", {})
    rows = [
        ("overall", str(validation.get("overall_score", ""))),
        ("legal realism", str(validation.get("legal_realism_score", ""))),
        ("exam likeness", str(validation.get("exam_likeness_score", ""))),
        (
            "similarity",
            str(validation.get("similarity_check", {}).get("max_similarity", "")),
        ),
    ]
    x = 58
    y = 230
    for label, value in rows:
        _card(draw, (x, y), (540, 100), label, value, accent="#0f7a4f")
        x += 590
        if x > 800:
            x = 58
            y += 135
    _draw_lines(
        draw,
        (58, 570),
        "Representative check keys: " + ", ".join(sorted(checks.keys())[:8]),
        font=FONT_SMALL,
        width=115,
    )
    return img


def _scene_study(trace: dict) -> Image.Image:
    study = _stage(trace, "study").get("details", {})
    img = _base("Study workflow", "model answer plus Anki-compatible TSV preview")
    draw = ImageDraw.Draw(img)
    _card(
        draw,
        (58, 145),
        (540, 430),
        "Model answer",
        study.get("model_answer", ""),
        accent="#0f7a4f",
    )
    _card(
        draw,
        (650, 145),
        (570, 430),
        "Anki TSV preview",
        study.get("anki_tsv_preview", ""),
        accent="#9d6200",
    )
    return img


def _scene_close() -> Image.Image:
    img = _base("Open source, local-first", "current complete pack: Singapore Tort")
    draw = ImageDraw.Draw(img)
    draw.text(
        (54, 190), "https://github.com/gongahkia/jikai", font=FONT_TITLE, fill="#17211b"
    )
    _draw_lines(
        draw,
        (58, 285),
        "Not legal advice. Not a full bar-review replacement. The narrow goal is inspectable practice-question generation with corpus provenance, validation, and exportable study artifacts.",
        width=70,
    )
    return img


def _write_video(frames: list[Image.Image], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for index, frame in enumerate(frames):
            frame.save(tmp_path / f"frame_{index:04d}.png")
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-framerate",
                str(FPS),
                "-i",
                str(tmp_path / "frame_%04d.png"),
                "-vf",
                "fps=24",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(output),
            ],
            check=True,
        )


def render(trace: dict, output: Path) -> None:
    scene_frames = [
        (_scene_title(trace), 8),
        (_scene_pipeline(trace), 10),
        (_scene_generation(trace), 12),
        (_scene_validation(trace), 10),
        (_scene_study(trace), 12),
        (_scene_close(), 8),
    ]
    frames: list[Image.Image] = []
    for frame, seconds in scene_frames:
        frames.extend([frame] * (seconds * FPS))
    _write_video(frames, output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-url", default=DEFAULT_TRACE_URL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    render(_load_trace(args.trace_url), args.output)
    print(f"Wrote demo video to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
