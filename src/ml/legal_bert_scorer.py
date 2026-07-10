"""Legal-BERT quality scorer — replaces the GBM regressor.

The old `QualityRegressor` was a `GradientBoostingRegressor` on 5000-dim TF-IDF
trained on ~33 examples. This module replaces it with a transformer-based
scorer suited to legal text.

Default base is `nlpaueb/legal-bert-base-uncased`. On CPU-only environments the
fallback base `cross-encoder/nli-deberta-v3-base` is used (already downloaded
by the NLI verifier), avoiding an extra model download.

Public API:
- `LegalBertScorer.train(texts, scores)` — fine-tunes a small regression head
- `LegalBertScorer.score(text) -> float in [0, 1]`
- `LegalBertScorer.save_model(path)` / `load_model(path)`
"""

from __future__ import annotations

import json
import os
from typing import Any, Iterable

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


class LegalBertScorer:
    """Quality scorer backed by a legal-domain transformer with a regression head."""

    DEFAULT_BASE = "nlpaueb/legal-bert-base-uncased"
    FALLBACK_BASE = "sentence-transformers/all-MiniLM-L6-v2"

    def __init__(self, base_model: str | None = None, max_length: int = 384):
        self.base_model = base_model or self.DEFAULT_BASE
        self.max_length = max_length
        self.model: Any = None
        self.tokenizer: Any = None
        self.is_trained: bool = False
        self._metrics: dict[str, Any] = {}
        self._device: str = "cpu"

    # ---- deps -----------------------------------------------------------
    def _require_transformers(self) -> Any:
        try:
            import torch
            from transformers import (
                AutoModelForSequenceClassification,
                AutoTokenizer,
            )

            return torch, AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:
            raise ImportError(
                "torch + transformers required for LegalBertScorer. "
                "Install via `pip install torch transformers`."
            ) from exc

    def _load_base(self) -> None:
        torch, AutoModelForSequenceClassification, AutoTokenizer = (
            self._require_transformers()
        )
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.base_model)
            self.model = AutoModelForSequenceClassification.from_pretrained(
                self.base_model, num_labels=1
            )
        except Exception as exc:  # pragma: no cover — depends on HF cache
            logger.warning(
                "Legal-BERT base unavailable, falling back",
                base=self.base_model,
                fallback=self.FALLBACK_BASE,
                error=str(exc),
            )
            self.base_model = self.FALLBACK_BASE
            self.tokenizer = AutoTokenizer.from_pretrained(self.base_model)
            self.model = AutoModelForSequenceClassification.from_pretrained(
                self.base_model, num_labels=1
            )
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model.to(self._device)

    # ---- training -------------------------------------------------------
    def train(
        self,
        texts: Iterable[str],
        scores: Iterable[float],
        *,
        num_epochs: int = 8,
        batch_size: int = 8,
        learning_rate: float = 2e-5,
    ) -> dict[str, Any]:
        torch, _, _ = self._require_transformers()
        from torch.utils.data import DataLoader, Dataset

        if self.model is None:
            self._load_base()

        texts_list = [str(t) for t in texts]
        scores_arr = np.asarray([float(s) for s in scores], dtype=np.float32)
        if scores_arr.max() > 1.0 + 1e-6:  # normalise 0-10 to 0-1 if needed
            scores_arr = scores_arr / 10.0
        scores_arr = np.clip(scores_arr, 0.0, 1.0)

        tokenizer = self.tokenizer

        class _RegressionDataset(Dataset):
            def __init__(
                self, texts: list[str], targets: np.ndarray, max_length: int
            ) -> None:
                enc = tokenizer(
                    texts,
                    truncation=True,
                    padding="max_length",
                    max_length=max_length,
                    return_tensors="pt",
                )
                self.input_ids = enc["input_ids"]
                self.attention_mask = enc["attention_mask"]
                self.targets = torch.tensor(targets, dtype=torch.float32)

            def __len__(self) -> int:
                return int(self.input_ids.shape[0])

            def __getitem__(self, idx: int) -> dict[str, Any]:
                return {
                    "input_ids": self.input_ids[idx],
                    "attention_mask": self.attention_mask[idx],
                    "labels": self.targets[idx],
                }

        dataset = _RegressionDataset(texts_list, scores_arr, self.max_length)
        loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

        optim = torch.optim.AdamW(self.model.parameters(), lr=learning_rate)
        loss_fn = torch.nn.MSELoss()

        self.model.train()
        for epoch in range(num_epochs):
            epoch_loss = 0.0
            for batch in loader:
                optim.zero_grad()
                out = self.model(
                    input_ids=batch["input_ids"].to(self._device),
                    attention_mask=batch["attention_mask"].to(self._device),
                )
                pred = out.logits.squeeze(-1)
                loss = loss_fn(pred, batch["labels"].to(self._device))
                loss.backward()
                optim.step()
                epoch_loss += float(loss.item())
            logger.info(
                "LegalBertScorer epoch",
                epoch=epoch,
                loss=epoch_loss / max(len(loader), 1),
            )
        self.model.eval()
        self.is_trained = True
        self._metrics = {
            "backend": "legal_bert_scorer",
            "base_model": self.base_model,
            "device": self._device,
            "n_samples": len(texts_list),
            "num_epochs": num_epochs,
        }
        return self._metrics

    # ---- inference ------------------------------------------------------
    def score(self, text: str) -> float:
        """Return quality score in [0, 1]. Falls back to 0.5 when untrained."""
        if not self.is_trained or self.model is None or self.tokenizer is None:
            return 0.5
        torch, _, _ = self._require_transformers()
        enc = self.tokenizer(
            str(text),
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt",
        )
        with torch.no_grad():
            out = self.model(
                input_ids=enc["input_ids"].to(self._device),
                attention_mask=enc["attention_mask"].to(self._device),
            )
        val = float(out.logits.squeeze().item())
        return max(0.0, min(1.0, val))

    def evaluate(
        self,
        texts: Iterable[str],
        scores: Iterable[float],
    ) -> dict[str, Any]:
        from sklearn.metrics import mean_absolute_error, r2_score

        texts_list = [str(t) for t in texts]
        y_true = np.asarray([float(s) for s in scores], dtype=np.float32)
        if y_true.max() > 1.0 + 1e-6:
            y_true = y_true / 10.0
        y_pred = np.asarray([self.score(t) for t in texts_list], dtype=np.float32)
        self._metrics.update(
            {
                "mae": float(mean_absolute_error(y_true, y_pred)),
                "r2": float(r2_score(y_true, y_pred)) if len(y_true) > 1 else 0.0,
                "eval_size": len(texts_list),
            }
        )
        return self._metrics

    # ---- persistence ----------------------------------------------------
    def save_model(self, path: str) -> None:
        if self.model is None or self.tokenizer is None:
            raise RuntimeError("Nothing to save")
        os.makedirs(path, exist_ok=True)
        self.model.save_pretrained(path)
        self.tokenizer.save_pretrained(path)
        with open(os.path.join(path, "jikai_scorer_meta.json"), "w") as f:
            json.dump(
                {
                    "base_model": self.base_model,
                    "max_length": self.max_length,
                    "metrics": self._metrics,
                },
                f,
                indent=2,
            )
        logger.info("LegalBertScorer saved", path=path)

    def load_model(self, path: str) -> None:
        _, AutoModelForSequenceClassification, AutoTokenizer = (
            self._require_transformers()
        )
        self.tokenizer = AutoTokenizer.from_pretrained(path)
        self.model = AutoModelForSequenceClassification.from_pretrained(path)
        meta_path = os.path.join(path, "jikai_scorer_meta.json")
        if os.path.exists(meta_path):
            with open(meta_path) as f:
                meta = json.load(f)
            self.base_model = meta.get("base_model", self.base_model)
            self.max_length = int(meta.get("max_length", self.max_length))
            self._metrics = meta.get("metrics", {})
        import torch

        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model.to(self._device)
        self.model.eval()
        self.is_trained = True
        logger.info("LegalBertScorer loaded", path=path, device=self._device)


__all__ = ["LegalBertScorer"]
