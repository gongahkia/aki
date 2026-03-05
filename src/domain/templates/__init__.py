"""Per-topic generation templates for hypothetical assembly."""

import json
from pathlib import Path
from typing import Dict, List

_TEMPLATES_DIR = Path(__file__).parent
_cache: Dict[str, Dict] = {}


def load_topic_template(topic_key: str) -> Dict:
    """Load a topic template JSON, with in-memory cache."""
    if topic_key in _cache:
        return _cache[topic_key]
    path = _TEMPLATES_DIR / f"{topic_key}.json"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    _cache[topic_key] = data
    return data


def available_templates() -> List[str]:
    """List topic keys with template files."""
    return [p.stem for p in _TEMPLATES_DIR.glob("*.json")]
