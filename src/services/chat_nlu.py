"""Chat NLU service: interprets natural language into structured commands.

LLMs are used ONLY for intent classification here — never for generating legal text.
Falls back to keyword matching when LLM is unavailable.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)

NLU_SYSTEM_PROMPT = """You are a command interpreter for Jikai, a legal hypothetical generator.
Your ONLY job is to interpret the user's natural language input and return a structured JSON command.
You must NEVER generate legal text, hypotheticals, or any legal content.

Return JSON with exactly these fields:
- "command_type": one of: generate, report, label, settings, topics, history, stats, providers, help, corpus, export, preprocess, train, embed, scrape, cleanup, unknown
- "parameters": dict of extracted parameters relevant to the command

For "generate": extract topics (list of strings), complexity (1-5), num_parties (int)
For "report": extract generation_id (int), issue_types (list), comment (string)
For "settings": extract key (string), value (string)
For other commands: extract any relevant parameters

If you cannot determine the intent, use command_type "unknown".
Respond with ONLY valid JSON, no explanation."""

# keyword patterns for fallback
_KEYWORD_PATTERNS: List[tuple] = [
    (r"\b(generate|create|make|new)\b.*\b(hypo|hypothetical|scenario)", "generate"),
    (r"\b(report|flag|issue)\b", "report"),
    (r"\b(label|annotate|tag)\b", "label"),
    (r"\b(setting|config|preference)\b", "settings"),
    (r"\b(topic|topics|list topics)\b", "topics"),
    (r"\b(history|past|previous)\b", "history"),
    (r"\b(stat|stats|statistics)\b", "stats"),
    (r"\b(provider|model|llm|ollama|gemini)\b", "providers"),
    (r"\b(help|what can|how do)\b", "help"),
    (r"\b(corpus|browse|search)\b", "corpus"),
    (r"\b(export|download|save)\b", "export"),
    (r"\b(preprocess|prepare)\b", "preprocess"),
    (r"\b(train|retrain|fit)\b", "train"),
    (r"\b(embed|index|vector)\b", "embed"),
    (r"\b(scrape|crawl|fetch)\b", "scrape"),
    (r"\b(clean|cleanup|purge)\b", "cleanup"),
]

_TOPIC_KEYWORDS = [
    "negligence", "duty of care", "causation", "remoteness", "battery",
    "assault", "defamation", "nuisance", "harassment", "false imprisonment",
    "vicarious liability", "trespass", "rylands", "contributory",
]


def _keyword_fallback(text: str) -> Dict[str, Any]:
    """Keyword matching when LLM is unavailable."""
    text_lower = text.lower().strip()
    command_type = "unknown"
    for pattern, cmd in _KEYWORD_PATTERNS:
        if re.search(pattern, text_lower):
            command_type = cmd
            break
    params: Dict[str, Any] = {}
    if command_type == "generate":
        topics = [t for t in _TOPIC_KEYWORDS if t in text_lower]
        params["topics"] = topics if topics else ["negligence"]
        complexity_match = re.search(r'\b([1-5])\b', text)
        params["complexity"] = int(complexity_match.group(1)) if complexity_match else 3
        party_match = re.search(r'(\d+)\s*part', text_lower)
        params["num_parties"] = int(party_match.group(1)) if party_match else 3
    return {"command_type": command_type, "parameters": params}


async def interpret(text: str, use_llm: bool = True) -> Dict[str, Any]:
    """Interpret user text into a structured command.

    Tries LLM first (if available), falls back to keyword matching.
    """
    if use_llm:
        try:
            return await _llm_interpret(text)
        except Exception as e:
            logger.warning("LLM NLU failed, using keyword fallback", error=str(e))
    return _keyword_fallback(text)


async def _llm_interpret(text: str) -> Dict[str, Any]:
    """Use LLM to interpret user intent."""
    from .llm_service import LLMRequest, llm_service
    request = LLMRequest(
        prompt=text,
        system_prompt=NLU_SYSTEM_PROMPT,
        max_tokens=256,
        temperature=0.1,
    )
    response = await llm_service.generate(request)
    raw = response.text.strip()
    # extract JSON from response
    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if json_match:
        parsed = json.loads(json_match.group())
        if "command_type" in parsed:
            return parsed
    return _keyword_fallback(text)
