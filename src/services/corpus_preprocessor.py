"""
Corpus preprocessor: converts raw files (TXT/PDF/PNG/DOCX) to clean corpus JSON.
Scans corpus/raw/*/ directories, infers topic from directory name, and rebuilds
corpus/clean/tort/corpus.json with all entries.
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

RAW_DIR = Path("corpus/raw")
CLEAN_DIR = Path("corpus/clean/tort")
CORPUS_FILE = CLEAN_DIR / "corpus.json"
SUPPORTED_RAW = {".txt", ".pdf", ".png", ".jpg", ".jpeg", ".docx"}

DIR_TOPIC_MAP: Dict[str, List[str]] = {
    "tort": [
        "negligence",
        "duty of care",
        "standard of care",
        "causation",
        "remoteness",
    ],
    "contract": ["contract", "breach of contract", "consideration"],
    "negligence": ["negligence", "duty of care", "standard of care"],
    "defamation": ["defamation"],
    "nuisance": ["private nuisance", "public nuisance"],
    "trespass": ["trespass to land", "trespass to person"],
}


def extract_text_from_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").strip()


def extract_text_from_pdf(path: Path) -> str:
    """Extract text from PDF using PyMuPDF."""
    try:
        import pymupdf

        doc = pymupdf.open(str(path))
        pages = [page.get_text() for page in doc]
        doc.close()
        return "\n".join(pages).strip()
    except ImportError:
        logger.warning("pymupdf not installed, skipping %s", path)
        return ""


def extract_text_from_image(path: Path) -> str:
    """OCR an image file using pytesseract + Pillow."""
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(path)
        text = pytesseract.image_to_string(img)
        return text.strip()
    except ImportError:
        logger.warning("pytesseract/pillow not installed, skipping %s", path)
        return ""
    except Exception as e:
        logger.warning("OCR failed for %s: %s", path, e)
        return ""


def extract_text_from_docx(path: Path) -> str:
    """Extract text from DOCX using python-docx."""
    try:
        import docx

        doc = docx.Document(str(path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paragraphs).strip()
    except ImportError:
        logger.warning("python-docx not installed, skipping %s", path)
        return ""


def extract_text(path: Path) -> str:
    """Route to correct extractor based on file extension."""
    ext = path.suffix.lower()
    if ext == ".txt":
        return extract_text_from_txt(path)
    elif ext == ".pdf":
        return extract_text_from_pdf(path)
    elif ext in {".png", ".jpg", ".jpeg"}:
        return extract_text_from_image(path)
    elif ext == ".docx":
        return extract_text_from_docx(path)
    return ""


def infer_topics_from_dir(dir_name: str) -> List[str]:
    """Infer base topics from the directory name."""
    key = dir_name.lower().replace("-", "_").replace(" ", "_")
    return DIR_TOPIC_MAP.get(key, [key.replace("_", " ")])


def normalize_text(text: str) -> str:
    """Collapse whitespace, strip, normalize unicode quotes."""
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def scan_raw_directory(
    raw_dir: Optional[Path] = None,
) -> List[Dict]:
    """
    Scan corpus/raw/*/ for supported files, extract text, infer topics.
    Returns list of {"text": ..., "topic": [...], "metadata": {...}} dicts.
    """
    raw_dir = raw_dir or RAW_DIR
    entries = []
    if not raw_dir.exists():
        logger.warning("Raw directory not found: %s", raw_dir)
        return entries

    for subdir in sorted(raw_dir.iterdir()):
        if not subdir.is_dir():
            continue
        base_topics = infer_topics_from_dir(subdir.name)
        for fpath in sorted(subdir.iterdir()):
            if not fpath.is_file():
                continue
            if fpath.suffix.lower() not in SUPPORTED_RAW:
                continue
            text = extract_text(fpath)
            if not text or len(text) < 50:
                logger.info("Skipping short/empty file: %s", fpath)
                continue
            text = normalize_text(text)
            entries.append(
                {
                    "text": text,
                    "topic": base_topics,
                    "metadata": {
                        "source_file": str(fpath.relative_to(raw_dir)),
                        "source_dir": subdir.name,
                    },
                }
            )
            logger.info("Processed %s (%d chars)", fpath.name, len(text))

    return entries


def build_corpus(
    raw_dir: Optional[Path] = None,
    output_path: Optional[Path] = None,
    merge_existing: bool = True,
) -> int:
    """
    Build clean corpus JSON from raw directory.
    If merge_existing=True, preserves manually-curated entries that have no
    source_file metadata (i.e. not from raw/).
    Returns total entry count.
    """
    output_path = output_path or CORPUS_FILE
    existing = []
    if merge_existing and output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            existing = json.load(f)

    curated = [e for e in existing if not e.get("metadata", {}).get("source_file")]
    raw_entries = scan_raw_directory(raw_dir)

    merged = curated + raw_entries
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)

    logger.info(
        "Corpus built: %d curated + %d raw = %d total",
        len(curated),
        len(raw_entries),
        len(merged),
    )
    return len(merged)


def convert_file_to_txt(input_path: Path, output_dir: Optional[Path] = None) -> Path:
    """
    Convert a single PDF/PNG/DOCX to .txt, saving alongside or in output_dir.
    Returns path to the generated .txt file.
    """
    text = extract_text(input_path)
    if not text:
        raise ValueError(f"Could not extract text from {input_path}")

    text = normalize_text(text)
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        out = output_dir / (input_path.stem + ".txt")
    else:
        out = input_path.with_suffix(".txt")

    out.write_text(text, encoding="utf-8")
    return out


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if len(sys.argv) > 1 and sys.argv[1] == "convert":
        if len(sys.argv) < 3:
            print("Usage: python -m src.services.corpus_preprocessor convert <file>")
            sys.exit(1)
        p = Path(sys.argv[2])
        out = convert_file_to_txt(p)
        print(f"Converted → {out}")
    else:
        count = build_corpus()
        print(f"Corpus rebuilt: {count} entries → {CORPUS_FILE}")
