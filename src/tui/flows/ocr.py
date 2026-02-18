"""OCR and Preprocessing flow."""

from pathlib import Path
from rich import box
from rich.panel import Panel
from questionary import Choice

from src.tui.console import console, tlog
from src.tui.inputs import _select_quit, _path


class OCRFlowMixin:
    """Mixin for OCR and preprocessing flows."""

    def ocr_flow(self):
        console.print("\n[bold yellow]OCR / Preprocess Corpus[/bold yellow]")
        while True:
            c = _select_quit(
                "OCR Menu",
                choices=[
                    Choice("Preprocess raw corpus (TXT/PDF/PNG/DOCX)", value="1"),
                    Choice("Convert single file to TXT (OCR)", value="2"),
                ],
            )
            if c is None:
                return
            if c == "__jump_gen__":
                return "__jump_gen__"
            if c == "1":
                # Assumes the method is available on self (from CorpusFlowMixin)
                if hasattr(self, "_preprocess_raw"):
                    self._preprocess_raw()
                else:
                    console.print("[red]Preprocess method not available[/red]")
            elif c == "2":
                self._ocr_single()

    def _ocr_single(self):
        path = _path("File to OCR (PDF/PNG/JPG/DOCX)", default="")
        if not path:
            return
        try:
            from ..services.corpus_preprocessor import extract_text, normalize_text

            with console.status("[bold green]Extracting text...", spinner="dots"):
                text = normalize_text(extract_text(Path(path)))
            if not text:
                console.print("[red]✗ No text extracted (check file format/deps)[/red]")
                return
            console.print(
                Panel(
                    text[:2000] + ("..." if len(text) > 2000 else ""),
                    title=f"Extracted from {Path(path).name}",
                    box=box.ROUNDED,
                    border_style="green",
                )
            )
            out = _path("Save TXT to (enter to skip)", default="")
            if out:
                Path(out).write_text(text, encoding="utf-8")
                console.print(f"[green]✓ Saved to {out}[/green]")
            tlog.info("OCR  %s → %d chars", path, len(text))
        except Exception as e:
            console.print(f"[red]✗ OCR failed: {e}[/red]")
            console.print(
                "[dim]Tip: ensure pytesseract and tesseract are installed[/dim]"
            )
