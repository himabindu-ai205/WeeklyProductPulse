"""LangChain structured-output cluster chain (architecture §10.3).

Assigns each corpus review to exactly one theme via batched LLM calls.
Sees only redacted text. Returns assignments only — never prose quotes.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from .config import AppConfig
from .llm import invoke_structured
from .schemas import Review, Theme
from .theme_math import compute_theme_stats, rank_themes


# ---------------------------------------------------------------------------
# Structured-output schema for a single assignment
# ---------------------------------------------------------------------------


class ReviewAssignment(BaseModel):
    review_id: str
    theme_id: str
    confidence: float = Field(ge=0.0, le=1.0)


class ClusterBatchOutput(BaseModel):
    assignments: list[ReviewAssignment]


class OtherSplitOutput(BaseModel):
    new_theme_id: str
    new_theme_label: str
    reassignments: list[ReviewAssignment] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "cluster.md"


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Cluster
# ---------------------------------------------------------------------------


def _build_theme_list(seeds: Sequence[Any]) -> str:
    """Format seed themes for the prompt."""
    lines = [f"- `{s.id}`: {s.label}" for s in seeds]
    lines.append("- `other`: Reviews that do not fit any seed theme")
    return "\n".join(lines)


def _reviews_to_json(reviews: Sequence[Review]) -> str:
    """Serialize reviews for the prompt (id + text only — no PII columns)."""
    rows = [{"review_id": r.id, "text": r.text, "rating": r.rating} for r in reviews]
    return json.dumps(rows, indent=2)


def cluster_reviews(
    llm: BaseChatModel,
    reviews: list[Review],
    app: AppConfig,
    *,
    corpus_from: date,
    corpus_to: date,
    reporting_from: date,
    reporting_to: date,
) -> list[Theme]:
    """Cluster *reviews* into ≤5 themes using batched LLM calls.

    Returns ranked ``Theme`` objects with stats populated.
    """
    seed_ids = {s.id for s in app.themes.seeds}
    all_valid_ids = seed_ids | {"other"}
    batch_size = app.limits.cluster_batch_size
    max_attempts = app.limits.cluster_max_attempts

    prompt_template = _load_prompt()
    theme_list_str = _build_theme_list(app.themes.seeds)

    assignments: dict[str, ReviewAssignment] = {}

    for start in range(0, len(reviews), batch_size):
        batch = reviews[start : start + batch_size]
        reviews_json = _reviews_to_json(batch)

        prompt_text = prompt_template.replace("{theme_list}", theme_list_str).replace(
            "{reviews_json}", reviews_json
        )
        messages = [
            SystemMessage(
                content=(
                    "You are a review classifier. Return only structured JSON "
                    'matching {"assignments":[{"review_id","theme_id","confidence"}]}.'
                )
            ),
            HumanMessage(content=prompt_text),
        ]

        attempt = 0
        while attempt < max_attempts:
            attempt += 1
            try:
                parsed = invoke_structured(
                    llm,
                    ClusterBatchOutput,
                    messages,
                    min_interval_seconds=app.limits.llm_request_interval_seconds,
                )
                for a in parsed.assignments:
                    tid = a.theme_id if a.theme_id in all_valid_ids else "other"
                    assignments[a.review_id] = ReviewAssignment(
                        review_id=a.review_id,
                        theme_id=tid,
                        confidence=a.confidence,
                    )
                break
            except Exception:
                if attempt >= max_attempts:
                    for r in batch:
                        if r.id not in assignments:
                            assignments[r.id] = ReviewAssignment(
                                review_id=r.id, theme_id="other", confidence=0.0
                            )
                    break

    for r in reviews:
        if r.id not in assignments:
            assignments[r.id] = ReviewAssignment(
                review_id=r.id, theme_id="other", confidence=0.0
            )

    themes = _build_themes(assignments, app, reviews)

    # Split pass: if "other" > 20% and theme count < 5
    other_theme = next((t for t in themes if t.id == "other"), None)
    if (
        other_theme
        and len(reviews) > 0
        and len(other_theme.review_ids) / len(reviews) > 0.20
        and len(themes) < 5
    ):
        themes = _split_other_pass(llm, themes, reviews, assignments, app)

    if len(themes) > 5:
        themes = _merge_to_five(themes)

    corpus_weeks = app.windows.corpus_weeks
    themes_with_stats = [
        compute_theme_stats(
            t, reviews, corpus_from, corpus_to, reporting_from, reporting_to, corpus_weeks
        )
        for t in themes
    ]

    return rank_themes(themes_with_stats)


def _build_themes(
    assignments: dict[str, ReviewAssignment],
    app: AppConfig,
    reviews: list[Review],
) -> list[Theme]:
    """Group assignments into Theme objects."""
    seed_map = {s.id: s.label for s in app.themes.seeds}
    theme_reviews: dict[str, list[str]] = {}

    for a in assignments.values():
        theme_reviews.setdefault(a.theme_id, []).append(a.review_id)

    themes: list[Theme] = []
    for tid, rids in theme_reviews.items():
        label = seed_map.get(tid, tid.replace("_", " ").title())
        themes.append(Theme(id=tid, label=label, review_ids=rids))

    return themes


def _split_other_pass(
    llm: BaseChatModel,
    themes: list[Theme],
    reviews: list[Review],
    assignments: dict[str, ReviewAssignment],
    app: AppConfig,
) -> list[Theme]:
    """One split pass on 'other' if it's > 20% and theme count < 5."""
    other_theme = next((t for t in themes if t.id == "other"), None)
    if not other_theme:
        return themes

    other_reviews = [r for r in reviews if r.id in set(other_theme.review_ids)]
    if not other_reviews:
        return themes

    split_prompt = (
        "Some reviews were classified as 'other'. Find ONE new coherent theme "
        "that covers the largest group. Return structured JSON with "
        "new_theme_id, new_theme_label, and reassignments "
        "(review_id, theme_id, confidence).\n\n"
        "Reviews:\n" + _reviews_to_json(other_reviews[:50])
    )

    try:
        parsed = invoke_structured(
            llm,
            OtherSplitOutput,
            [
                SystemMessage(content="You are a review classifier. Return only structured JSON."),
                HumanMessage(content=split_prompt),
            ],
            min_interval_seconds=app.limits.llm_request_interval_seconds,
        )
        new_id = parsed.new_theme_id.strip().lower().replace(" ", "_")
        new_label = parsed.new_theme_label or new_id.replace("_", " ").title()

        if not new_id or new_id in {t.id for t in themes}:
            return themes

        for ra in parsed.reassignments:
            if ra.theme_id == new_id and ra.review_id in assignments:
                assignments[ra.review_id] = ReviewAssignment(
                    review_id=ra.review_id,
                    theme_id=new_id,
                    confidence=ra.confidence,
                )

        rebuilt = _build_themes(assignments, app, reviews)
        return [
            t.model_copy(update={"label": new_label}) if t.id == new_id else t
            for t in rebuilt
        ]
    except Exception:
        return themes


def _merge_to_five(themes: list[Theme]) -> list[Theme]:
    """If > 5 themes, merge the smallest into 'other' until we have 5."""
    while len(themes) > 5:
        non_other = [t for t in themes if t.id != "other"]
        other = next((t for t in themes if t.id == "other"), None)

        if not non_other:
            break

        smallest = min(non_other, key=lambda t: len(t.review_ids))
        non_other.remove(smallest)

        if other is None:
            other = Theme(id="other", label="Other", review_ids=[])

        other = other.model_copy(
            update={"review_ids": other.review_ids + smallest.review_ids}
        )
        themes = non_other + [other]

    return themes


def write_cluster_artifacts(themes: list[Theme], artifacts_dir: Path) -> None:
    """Write themes.json to the artifacts directory."""
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    path = artifacts_dir / "themes.json"
    payload = [t.model_dump(mode="json") for t in themes]
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
