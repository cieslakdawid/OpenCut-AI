"""Models for natural-language editor commands (app.routes.command)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CommandRequest(BaseModel):
    """A natural-language editing command from the user."""

    command: str = Field(..., description="Natural-language editing instruction")
    timeline_state: dict[str, Any] | None = Field(
        default=None, description="Optional current timeline state for context"
    )
    model: str | None = Field(default=None, description="Optional LLM model override")


class EditorAction(BaseModel):
    """A single structured action to apply to the timeline."""

    type: str = Field(..., description="Action type, e.g. cut, trim, add_text")
    target: str | None = Field(default=None, description="Target clip id, if any")
    params: dict[str, Any] = Field(default_factory=dict)


class CommandResponse(BaseModel):
    """Structured result of interpreting a command."""

    actions: list[EditorAction] = Field(default_factory=list)
    explanation: str = ""
    confidence: float = 0.5
    raw_response: str = ""
