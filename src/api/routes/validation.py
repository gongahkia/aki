"""Validation endpoints."""

from typing import List

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


class ValidateRequest(BaseModel):
    text: str
    required_topics: List[str]
    expected_parties: int = 2
    corpus_pack: str = "sg_tort"
    jurisdiction: str = "sg"
    subject: str = "tort"
    subtopics: List[str] = Field(default_factory=list)
    law_domain: str = "tort"
    fast_mode: bool = False


@router.post("/validate")
async def validate(req: ValidateRequest):
    from ...services import validation_service

    result = validation_service.validate_hypothetical(
        text=req.text,
        required_topics=req.required_topics,
        expected_parties=req.expected_parties,
        corpus_pack=req.corpus_pack,
        jurisdiction=req.jurisdiction,
        subject=req.subject,
        subtopics=req.subtopics,
        law_domain=req.law_domain,
        fast_mode=req.fast_mode,
    )
    return result
