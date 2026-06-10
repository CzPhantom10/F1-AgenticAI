"""Pydantic schemas for the Analyst Agent API."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class Message(BaseModel):
    """A single chat message in the conversation history."""
    role: str
    content: str


class AnalystQueryRequest(BaseModel):
    """Incoming natural-language question for the analyst."""

    question: str = Field(..., min_length=1, max_length=2000)
    history: list[Message] | None = None

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Question cannot be empty")
        return cleaned


class AnalystSource(BaseModel):
    """Reference to a data record used when generating the answer."""

    type: str
    label: str


class AnalystQueryResponse(BaseModel):
    """Analyst answer with traceable data sources."""

    answer: str
    sources: list[AnalystSource]
