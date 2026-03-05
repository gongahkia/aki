"""Chat NLU API endpoint."""

from fastapi import APIRouter
from pydantic import BaseModel

from ...services.chat_nlu import interpret

router = APIRouter()


class InterpretRequest(BaseModel):
    text: str
    use_llm: bool = True


@router.post("/interpret")
async def interpret_chat(req: InterpretRequest):
    """Interpret natural language into a structured command."""
    result = await interpret(req.text, use_llm=req.use_llm)
    return result
