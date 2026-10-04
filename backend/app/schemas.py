from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Project name cannot be blank.")
        return value


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str | None
    created_at: str


class DatasetOut(BaseModel):
    id: str
    project_id: str
    filename: str
    profile: dict[str, Any]
    created_at: str


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = None


class Visualization(BaseModel):
    type: Literal["bar", "line", "scatter", "histogram", "box", "pie"]
    title: str
    x: str | None = None
    y: str | None = None
    data: list[dict[str, Any]]


class AnalysisResponse(BaseModel):
    conversation_id: str
    answer: str
    summary: str
    analysis_type: str
    code: str | None = None
    result: Any = None
    visualization: Visualization | None = None
    insights: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "high"
