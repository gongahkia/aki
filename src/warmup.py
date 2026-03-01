"""Warmup command for local topic cache, provider probes, and optional embeddings."""

import argparse
import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict

import httpx
import structlog

from src.config import settings

logger = structlog.get_logger(__name__)


def _load_corpus_topics() -> tuple[list[str], float]:
    started = time.perf_counter()
    corpus_path = Path(settings.corpus_path)
    if not corpus_path.exists():
        raise FileNotFoundError(f"Corpus file not found: {corpus_path}")

    with open(corpus_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    topics = set()
    if isinstance(payload, list):
        for entry in payload:
            if not isinstance(entry, dict):
                continue
            raw_topics = entry.get("topics")
            if raw_topics is None:
                raw_topics = entry.get("topic", [])
            if isinstance(raw_topics, list):
                values = raw_topics
            else:
                values = [raw_topics]
            for topic in values:
                topic_text = str(topic).strip()
                if topic_text:
                    topics.add(topic_text)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    return sorted(topics), elapsed_ms


async def _probe_endpoint(
    client: httpx.AsyncClient,
    name: str,
    url: str,
    headers: Dict[str, str] | None = None,
) -> tuple[str, Dict[str, Any]]:
    try:
        started = time.perf_counter()
        response = await client.get(url, headers=headers)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        healthy = response.status_code < 500
        return (
            name,
            {
                "healthy": healthy,
                "status_code": response.status_code,
                "latency_ms": elapsed_ms,
            },
        )
    except Exception as e:
        return (
            name,
            {
                "healthy": False,
                "error": str(e),
            },
        )


async def _check_provider_health() -> tuple[Dict[str, Any], float]:
    started = time.perf_counter()
    checks: list[tuple[str, Dict[str, Any]]] = []

    async with httpx.AsyncClient(timeout=10.0) as client:
        tasks = []

        # Local providers: actual connectivity probes.
        ollama_host = getattr(settings.llm, "ollama_host", "http://localhost:11434")
        tasks.append(
            _probe_endpoint(client, "ollama", f"{ollama_host.rstrip('/')}/api/tags")
        )

        local_llm_host = getattr(settings, "local_llm_host", "") or ""
        if local_llm_host.strip():
            tasks.append(
                _probe_endpoint(client, "local", f"{local_llm_host.rstrip('/')}/health")
            )
        else:
            checks.append(
                (
                    "local",
                    {"healthy": False, "configured": False, "error": "not configured"},
                )
            )

        # Cloud providers: key presence check plus lightweight endpoint where feasible.
        openai_key = (getattr(settings, "openai_api_key", None) or "").strip()
        if openai_key:
            tasks.append(
                _probe_endpoint(
                    client,
                    "openai",
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {openai_key}"},
                )
            )
        else:
            checks.append(
                (
                    "openai",
                    {"healthy": False, "configured": False, "error": "API key missing"},
                )
            )

        anthropic_key = (getattr(settings, "anthropic_api_key", None) or "").strip()
        if anthropic_key:
            # Anthropic has no cheap unauthenticated status endpoint; key presence check.
            checks.append(
                ("anthropic", {"healthy": True, "configured": True, "probe": "api_key"})
            )
        else:
            checks.append(
                (
                    "anthropic",
                    {"healthy": False, "configured": False, "error": "API key missing"},
                )
            )

        google_key = (getattr(settings, "google_api_key", None) or "").strip()
        if google_key:
            checks.append(
                ("google", {"healthy": True, "configured": True, "probe": "api_key"})
            )
        else:
            checks.append(
                (
                    "google",
                    {"healthy": False, "configured": False, "error": "API key missing"},
                )
            )

        if tasks:
            checks.extend(await asyncio.gather(*tasks))

    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    return dict(checks), elapsed_ms


def _initialize_embeddings() -> tuple[bool, float, str | None]:
    started = time.perf_counter()
    model_name = getattr(settings, "embedding_model", "all-MiniLM-L6-v2")
    script = (
        "from sentence_transformers import SentenceTransformer;"
        f"SentenceTransformer({model_name!r});"
        "print('embedding_model_ready')"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=180,
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    if result.returncode == 0:
        return True, elapsed_ms, None
    error = (result.stderr or result.stdout or "embedding init failed").strip()
    return False, elapsed_ms, error


async def run_warmup(init_embeddings: bool = False) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "status": "ok",
        "topics_count": 0,
        "topic_load_ms": 0.0,
        "provider_health_ms": 0.0,
        "provider_health": {},
        "embedding_initialized": False,
        "embedding_init_ms": 0.0,
    }

    try:
        topics, topic_ms = _load_corpus_topics()
        summary["topics_count"] = len(topics)
        summary["topic_load_ms"] = topic_ms
    except Exception as e:
        summary["status"] = "degraded"
        summary["topic_error"] = str(e)
        logger.error("Warmup topic preload failed", error=str(e))

    provider_health, provider_health_ms = await _check_provider_health()
    summary["provider_health"] = provider_health
    summary["provider_health_ms"] = provider_health_ms

    if init_embeddings:
        initialized, elapsed_ms, error = _initialize_embeddings()
        summary["embedding_initialized"] = initialized
        summary["embedding_init_ms"] = elapsed_ms
        if error:
            summary["status"] = "degraded"
            summary["embedding_error"] = error
            logger.error("Warmup embedding init failed", error=error)

    logger.info("Warmup completed", **summary)
    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Warm up local topics, provider health, and optional embeddings."
    )
    parser.add_argument(
        "--init-embeddings",
        action="store_true",
        help="Initialize embedding model in a subprocess.",
    )
    args = parser.parse_args()

    summary = asyncio.run(run_warmup(init_embeddings=args.init_embeddings))
    print(json.dumps(summary, indent=2))
    if summary.get("status") != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
