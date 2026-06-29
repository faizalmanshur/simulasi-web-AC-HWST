from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SimulationRequest(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)


class ExportRequest(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)
    results: dict[str, Any] | None = None
