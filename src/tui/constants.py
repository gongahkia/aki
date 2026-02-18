"""Jikai TUI Constants."""

import os

TITLE = "Jikai"
VERSION = "0.1.0"
LOG_LEVEL = "INFO"

# Paths
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
LOG_PATH = os.path.join(LOG_DIR, "tui.log")
HISTORY_PATH = "data/history.json"
STATE_FILE = "data/state.json"
OLLAMA_HOST = "http://localhost:11434"
LOCAL_LLM_HOST = "http://localhost:1234"

TOPICS = [
    "negligence",
    "duty_of_care",
    "causation",
    "remoteness",
    "battery",
    "assault",
    "false_imprisonment",
    "defamation",
    "private_nuisance",
    "trespass_to_land",
    "vicarious_liability",
    "strict_liability",
    "harassment",
    "occupiers_liability",
    "product_liability",
    "contributory_negligence",
    "economic_loss",
    "psychiatric_harm",
    "employers_liability",
]

TOPIC_DESCRIPTIONS = {
    "negligence": "duty, breach, damage, causation",
    "duty_of_care": "neighbour principle, proximity",
    "causation": "but-for test, legal causation",
    "remoteness": "foreseeability of damage",
    "contributory_negligence": "claimant's own fault",
    "battery": "intentional application of force",
    "assault": "apprehension of immediate contact",
    "false_imprisonment": "unlawful restraint of liberty",
    "trespass_to_land": "unlawful entry onto land",
    "vicarious_liability": "employer liability for employee torts",
    "strict_liability": "liability without fault",
    "occupiers_liability": "duties to visitors and trespassers",
    "employers_liability": "workplace safety duties",
    "product_liability": "defective product claims",
    "defamation": "false statements harming reputation",
    "private_nuisance": "unreasonable interference with land use",
    "harassment": "course of conduct causing alarm",
    "economic_loss": "pure financial loss claims",
    "psychiatric_harm": "nervous shock and mental injury",
}

TOPIC_CATEGORIES = {
    "Negligence-Based": ["negligence", "duty_of_care", "causation", "remoteness", "contributory_negligence"],
    "Intentional Torts": ["battery", "assault", "false_imprisonment", "trespass_to_land"],
    "Liability": ["vicarious_liability", "strict_liability", "occupiers_liability", "employers_liability", "product_liability"],
    "Specific Torts": ["defamation", "private_nuisance", "harassment"],
    "Damages": ["economic_loss", "psychiatric_harm"],
}

PROVIDERS = ["ollama", "openai", "anthropic", "google", "local"]

PROVIDER_MODELS = {
    "ollama": ["llama3", "llama3.1", "mistral", "gemma2", "phi3", "codellama", "qwen2"],
    "openai": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-3.5-turbo",
        "o1",
        "o1-mini",
    ],
    "anthropic": [
        "claude-sonnet-4-5-20250929",
        "claude-opus-4-20250918",
        "claude-haiku-4-5-20251001",
        "claude-3-5-sonnet-20241022",
    ],
    "google": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
    "local": ["default"],
}

HOTKEY_MAP = {
    "g": "gen",
    "h": "history",
    "s": "settings",
    "p": "providers",
}

# Global hotkeys that work from any submenu
GLOBAL_HOTKEYS = {
    "g": "__jump_gen__",
}

HELP_DESCRIPTIONS = {
    "ocr": "extract text from PDF/DOCX/images into the corpus (requires: pymupdf, python-docx, pillow, pytesseract)",
    "corpus": "view, search, and filter preprocessed corpus entries",
    "label": "tag corpus entries with topics and quality scores for training",
    "train": "train ML models on labelled data for better generation (requires: scikit-learn, pandas)",
    "embed": "create vector embeddings for semantic search during generation (requires: chromadb, sentence-transformers, torch)",
    "gen": "create a new tort law scenario using AI",
    "export": "save a generated hypothetical as DOCX or PDF (requires: python-docx)",
    "history": "browse past generations with search and filter",
    "stats": "view statistics about your corpus and generations",
    "tools": "batch operations: bulk generate, import cases, bulk label",
    "settings": "configure API keys, hosts, and defaults",
    "providers": "check health and set default LLM provider",
    "guided": "step-by-step walkthrough for first-time users",
    "cleanup": "selectively remove generated files, models, logs, etc.",
    "more": "access secondary features: history, stats, settings, etc.",
}

SERVICE_DEPS = {
    "ocr": ["pymupdf", "python-docx", "pillow", "pytesseract"],
    "train": ["scikit-learn", "pandas", "joblib"],
    "embed": ["chromadb", "sentence-transformers", "torch"],
    "export": ["python-docx"],
    "gen": ["httpx"],
    "google": ["google-generativeai"],
    "anthropic": ["anthropic"],
}

# Map pip package names to import names for verification
IMPORT_MAP = {
    "pymupdf": "fitz",
    "python-docx": "docx",
    "pillow": "PIL",
    "scikit-learn": "sklearn",
    "sentence-transformers": "sentence_transformers",
    "google-generativeai": "google.generativeai",
}
