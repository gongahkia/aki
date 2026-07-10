"""SetFit multi-label topic classifier — replaces TF-IDF+LinearSVC on small data.

SetFit (Sentence Transformer Fine-tuning) uses contrastive learning on sentence
embeddings and is designed for the low-shot regime this project sits in
(~33 training examples). See Tunstall et al., 2022 (arXiv:2209.11055).

The class here is intentionally decoupled from `TopicClassifier` so both
backends can coexist behind the `MLPipeline` dispatch flag. Import of setfit
is lazy so the module can be inspected without the dep installed.
"""

from __future__ import annotations

import os
from typing import Any, Callable, Iterable

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


class SetFitTopicClassifier:
    """Multi-label SetFit classifier over the SG-tort taxonomy.

    Persistence is directory-based (matches SetFit's `save_pretrained`).
    """

    def __init__(
        self,
        base_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        multi_target_strategy: str = "one-vs-rest",
    ) -> None:
        self.base_model = base_model
        self.multi_target_strategy = multi_target_strategy
        self.model: Any = None
        self.labels: list[str] = []
        self.is_trained: bool = False
        self._metrics: dict[str, Any] = {}

    def _require_setfit(self) -> Any:
        try:
            from setfit import SetFitModel, Trainer, TrainingArguments

            return SetFitModel, Trainer, TrainingArguments
        except ImportError as exc:
            raise ImportError(
                "setfit is required for SetFitTopicClassifier. "
                "Install with `pip install setfit` (GPU strongly recommended for training)."
            ) from exc

    def train(
        self,
        texts: Iterable[str],
        topic_lists: Iterable[list[str]],
        *,
        labels: list[str] | None = None,
        num_iterations: int = 20,
        num_epochs: int = 1,
        batch_size: int = 16,
        progress_callback: Callable[[float, str], None] | None = None,
    ) -> dict[str, Any]:
        """Fit SetFit on (texts, topic_lists). Multi-label via one-vs-rest.

        `labels` fixes label order; if not provided it is inferred from
        `topic_lists` union.
        """
        SetFitModel, Trainer, TrainingArguments = self._require_setfit()

        texts_list = [str(t) for t in texts]
        topic_lists_list = [list(t) for t in topic_lists]
        if labels is None:
            seen: dict[str, None] = {}
            for row in topic_lists_list:
                for t in row:
                    seen[str(t)] = None
            labels = list(seen.keys())
        self.labels = list(labels)

        y = self._binarize(topic_lists_list, self.labels)

        if progress_callback:
            progress_callback(0.1, "Loading SetFit base model")
        self.model = SetFitModel.from_pretrained(
            self.base_model, multi_target_strategy=self.multi_target_strategy
        )

        if progress_callback:
            progress_callback(0.25, "Building contrastive dataset")

        try:
            from datasets import Dataset
        except ImportError as exc:
            raise ImportError(
                "The `datasets` package is required by SetFit. Install with `pip install datasets`."
            ) from exc

        train_ds = Dataset.from_dict({"text": texts_list, "label": y.tolist()})

        args = TrainingArguments(
            batch_size=batch_size,
            num_iterations=num_iterations,
            num_epochs=num_epochs,
        )
        trainer = Trainer(
            model=self.model,
            train_dataset=train_ds,
            args=args,
        )
        if progress_callback:
            progress_callback(0.5, "Contrastive fine-tuning")
        trainer.train()
        self.is_trained = True
        if progress_callback:
            progress_callback(1.0, "SetFit trained")

        self._metrics = {
            "backend": "setfit",
            "base_model": self.base_model,
            "n_samples": len(texts_list),
            "n_labels": len(self.labels),
            "labels": self.labels,
            "num_iterations": num_iterations,
            "num_epochs": num_epochs,
        }
        logger.info(
            "SetFit classifier trained",
            n_samples=len(texts_list),
            n_labels=len(self.labels),
        )
        return self._metrics

    def _binarize(self, topic_lists: list[list[str]], labels: list[str]) -> np.ndarray:
        idx = {lbl: i for i, lbl in enumerate(labels)}
        y: np.ndarray = np.zeros((len(topic_lists), len(labels)), dtype=np.int64)
        for i, row in enumerate(topic_lists):
            for t in row:
                j = idx.get(str(t))
                if j is not None:
                    y[i, j] = 1
        return y

    def predict_topics(
        self, texts: Iterable[str], threshold: float = 0.5
    ) -> list[list[str]]:
        if not self.is_trained or self.model is None:
            raise RuntimeError("SetFitTopicClassifier not trained")
        texts_list = [str(t) for t in texts]
        # setfit returns numpy or torch depending on version; predict_proba is available for classifier head.
        try:
            proba = self.model.predict_proba(texts_list)
        except AttributeError:
            preds = self.model.predict(texts_list)
            proba = np.asarray(preds)
        proba = np.asarray(proba)
        out: list[list[str]] = []
        for row in proba:
            active = [
                self.labels[i] for i, p in enumerate(row) if float(p) >= threshold
            ]
            out.append(active)
        return out

    def predict_confidence(
        self, text: str, requested_topics: list[str]
    ) -> dict[str, float]:
        """Return per-topic confidence for the requested topics only.

        Consumed by the ML gate in workflow_facade to decide whether the
        drafted hypothetical actually covers what was asked.
        """
        if not self.is_trained or self.model is None:
            raise RuntimeError("SetFitTopicClassifier not trained")
        try:
            proba = self.model.predict_proba([str(text)])
        except AttributeError:
            proba = np.asarray(self.model.predict([str(text)]))
        proba = np.asarray(proba)[0]
        label_to_conf: dict[str, float] = {}
        for i, lbl in enumerate(self.labels):
            label_to_conf[lbl] = float(proba[i])
        return {t: label_to_conf.get(t, 0.0) for t in requested_topics}

    def evaluate(
        self,
        texts: Iterable[str],
        topic_lists: Iterable[list[str]],
        threshold: float = 0.5,
    ) -> dict[str, Any]:
        """Multi-label precision/recall/F1 (micro) against a held-out set."""
        from sklearn.metrics import precision_recall_fscore_support

        preds = self.predict_topics(texts, threshold=threshold)
        gold_lists = [list(t) for t in topic_lists]
        y_true = self._binarize(gold_lists, self.labels)
        y_pred = self._binarize(preds, self.labels)
        p, r, f, _ = precision_recall_fscore_support(
            y_true, y_pred, average="micro", zero_division=0
        )
        self._metrics.update(
            {
                "micro_precision": float(p),
                "micro_recall": float(r),
                "micro_f1": float(f),
                "eval_threshold": threshold,
                "eval_size": len(gold_lists),
            }
        )
        return self._metrics

    def save_model(self, path: str) -> None:
        if self.model is None:
            raise RuntimeError("Nothing to save")
        os.makedirs(path, exist_ok=True)
        self.model.save_pretrained(path)
        import json

        with open(os.path.join(path, "jikai_setfit_meta.json"), "w") as f:
            json.dump(
                {
                    "labels": self.labels,
                    "base_model": self.base_model,
                    "metrics": self._metrics,
                },
                f,
                indent=2,
            )
        logger.info("SetFit model saved", path=path)

    def load_model(self, path: str) -> None:
        SetFitModel, _, _ = self._require_setfit()
        self.model = SetFitModel.from_pretrained(path)
        meta_path = os.path.join(path, "jikai_setfit_meta.json")
        if os.path.exists(meta_path):
            import json

            with open(meta_path) as f:
                meta = json.load(f)
            self.labels = meta.get("labels", [])
            self.base_model = meta.get("base_model", self.base_model)
            self._metrics = meta.get("metrics", {})
        self.is_trained = True
        logger.info("SetFit model loaded", path=path, n_labels=len(self.labels))


__all__ = ["SetFitTopicClassifier"]
