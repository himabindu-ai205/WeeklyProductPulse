"""Pydantic contracts for reviews, themes, pulse, and validation (architecture §9)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Store = Literal["play_store"]
Trend = Literal["rising", "falling", "steady"]


class DateWindow(BaseModel):
    from_: date = Field(alias="from")
    to: date

    model_config = {"populate_by_name": True}


class Review(BaseModel):
    id: str
    store: Store = "play_store"
    date: date
    rating: int | None = Field(default=None, ge=1, le=5)
    title: str = ""
    text: str
    app_version: str | None = None


class Theme(BaseModel):
    id: str
    label: str
    description: str = ""
    review_ids: list[str] = Field(default_factory=list)
    count_corpus: int = 0
    count_week: int = 0
    avg_rating_week: float | None = None
    baseline_weekly: float = 0.0
    trend: Trend = "steady"


class PulseTheme(BaseModel):
    id: str
    label: str
    count_week: int
    avg_rating_week: float | None = None
    trend: Trend
    summary: str


class PulseQuote(BaseModel):
    text: str
    review_id: str
    theme_id: str
    rating: int | None = None
    date: date


class PulseAction(BaseModel):
    title: str
    detail: str
    theme_id: str


class Pulse(BaseModel):
    product_name: str
    week_ending: date
    corpus_window: DateWindow
    reporting_window: DateWindow
    window_note: str | None = None
    review_count_week: int = 0
    review_count_corpus: int = 0
    avg_rating_week: float | None = None
    store: Store = "play_store"
    top_themes: list[PulseTheme] = Field(default_factory=list)
    quotes: list[PulseQuote] = Field(default_factory=list)
    actions: list[PulseAction] = Field(default_factory=list)
    body_word_count: int = 0
    doc_url: str | None = None
    draft_id: str | None = None


class ValidationResult(BaseModel):
    passed: bool
    body_word_count: int = 0
    failures: list[str] = Field(default_factory=list)
    pii_hits: list[str] = Field(default_factory=list)
    fixable: bool = True
