"""Data loading, feature extraction, and preprocessing for ML pipeline."""

from typing import Callable, Optional, Tuple

import pandas as pd
import structlog
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MultiLabelBinarizer

logger = structlog.get_logger(__name__)

REQUIRED_COLUMNS = {"text", "topics", "quality_score", "complexity"}
TOPIC_DELIMITER = "|"


def _read_csv(csv_path: str) -> pd.DataFrame:
    """Read CSV with encoding fallback (utf-8-sig -> latin-1)."""
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(csv_path, encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Cannot decode CSV at {csv_path} with utf-8-sig or latin-1")


def load_data(
    csv_path: str,
    test_size: float = 0.2,
    random_state: int = 42,
    progress_callback: Optional[Callable] = None,
) -> dict:
    """Load labelled corpus from CSV. Columns: text, topics, quality_score, complexity."""
    if progress_callback:
        progress_callback(0.1, "Loading CSV")
    df = _read_csv(csv_path)
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {missing}. Got: {list(df.columns)}")
    if not pd.api.types.is_numeric_dtype(df["quality_score"]):
        try:
            df["quality_score"] = pd.to_numeric(df["quality_score"])
        except (ValueError, TypeError) as e:
            raise ValueError(f"quality_score column must be numeric: {e}")
    if not pd.api.types.is_numeric_dtype(df["complexity"]):
        try:
            df["complexity"] = pd.to_numeric(df["complexity"])
        except (ValueError, TypeError) as e:
            raise ValueError(f"complexity column must be numeric: {e}")
    if len(df) < 2:
        raise ValueError(f"Need at least 2 rows for train/test split, got {len(df)}")
    df["topic_list"] = df["topics"].apply(
        lambda x: [t.strip() for t in str(x).split(TOPIC_DELIMITER) if t.strip()]
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
