"""Unified structured generation adapter."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


async def generate_structured(
    provider: Any,
    schema: type[BaseModel],
    prompt: str,
    **kwargs: Any,
) -> BaseModel:
    """Generate a provider response and validate it as the requested schema."""
    if not bool(getattr(provider, "supports_json_schema", False)):
        raise NotImplementedError("Provider does not support JSON schema output")
    result = await provider.generate_structured(schema, prompt, **kwargs)
    return schema.model_validate(result)


__all__ = ["generate_structured"]
