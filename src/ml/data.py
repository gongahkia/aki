"""Data loading, feature extraction, and preprocessing for ML pipeline."""

from typing import Callable, Optional, Tuple

import pandas as pd
import structlog
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MultiLabelBinarizer

logger = structlog.get_logger(__name__)


def load_data(
    csv_path: str,
    test_size: float = 0.2,
    random_state: int = 42,
    progress_callback: Optional[Callable] = None,
) -> dict:
    """Load labelled corpus from CSV. Columns: text, topic_labels, quality_score, difficulty_level."""
    if progress_callback:
        progress_callback(0.1, "Loading CSV")
    df = pd.read_csv(csv_path)
    required = {"text", "topic_labels", "quality_score", "difficulty_level"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    df["topic_list"] = df["topic_labels"].apply(
        lambda x: [t.strip() for t in str(x).split("|")]
    )
    if progress_callback:
        progress_callback(0.3, "Splitting data")
    train_df, test_df = train_test_split(
        df, test_size=test_size, random_state=random_state
    )
    if progress_callback:
        progress_callback(0.5, "Data loaded")
    return {
        "train": train_df.reset_index(drop=True),
        "test": test_df.reset_index(drop=True),
        "full": df,
    }


def extract_features(
    texts,
    max_features: int = 5000,
    ngram_range: Tuple[int, int] = (1, 2),
    vectorizer: Optional[TfidfVectorizer] = None,
    progress_callback: Optional[Callable] = None,
) -> Tuple:
    """TF-IDF feature extraction. Returns (X, vectorizer)."""
    if progress_callback:
        progress_callback(0.6, "Extracting TF-IDF features")
    if vectorizer is None:
        vectorizer = TfidfVectorizer(
            max_features=max_features, ngram_range=ngram_range, stop_words="english"
        )
        X = vectorizer.fit_transform(texts)
    else:
        X = vectorizer.transform(texts)
    if progress_callback:
        progress_callback(0.8, "Features extracted")
    return X, vectorizer


def binarize_labels(
    topic_lists, binarizer: Optional[MultiLabelBinarizer] = None
) -> Tuple:
    """Multi-label binarization for topics. Returns (y, binarizer)."""
    if binarizer is None:
        binarizer = MultiLabelBinarizer()
        y = binarizer.fit_transform(topic_lists)
    else:
        y = binarizer.transform(topic_lists)
    return y, binarizer
