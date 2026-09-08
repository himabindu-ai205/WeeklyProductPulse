"""Render a Pulse object to markdown (architecture §11, §10.5).

The same rendered output later feeds Google Docs and Gmail.
"""

from __future__ import annotations

import re

from .schemas import Pulse, Trend


# ---------------------------------------------------------------------------
# Trend arrow
# ---------------------------------------------------------------------------

_TREND_ARROW: dict[Trend, str] = {
    "rising": "↑ rising",
    "falling": "↓ falling",
    "steady": "→ steady",
}


# ---------------------------------------------------------------------------
# Word-count helper (architecture §10.5)
# ---------------------------------------------------------------------------


def count_body_words(pulse: Pulse) -> int:
    """Count body words per architecture §10.5.

    **Counted:** theme summary sentences, quote text, action titles and details.
    **Not counted:** headings, metadata line, numeric labels, markdown punctuation.
    **Method:** strip markdown, split on whitespace, count tokens containing at
    least one alphanumeric character.
    """
    parts: list[str] = []

    # Theme summaries (the prose after the bold label)
    for t in pulse.top_themes:
        parts.append(t.summary)

    # Quotes
    for q in pulse.quotes:
        parts.append(q.text)

    # Actions (title + detail)
    for a in pulse.actions:
        parts.append(a.title)
        parts.append(a.detail)

    blob = " ".join(parts)
    # Strip residual markdown bold/italic
    blob = re.sub(r"[*_`>\"#]", " ", blob)
    tokens = blob.split()
    return sum(1 for tok in tokens if re.search(r"[A-Za-z0-9]", tok))


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


def render_pulse_md(pulse: Pulse) -> str:
    """Return the full ``pulse.md`` string matching the worked example (§11)."""
    lines: list[str] = []

    # Title
    we = pulse.week_ending.isoformat()
    lines.append(f"# Weekly Review Pulse — {pulse.product_name} — week ending {we}")

    # Metadata line
    avg_str = (
        f"avg {pulse.avg_rating_week:.1f}★"
        if pulse.avg_rating_week is not None
        else "avg n/a"
    )
    rw = pulse.reporting_window
    lines.append(
        f"Play Store · com.nextbillion.groww · "
        f"{pulse.review_count_week} reviews · "
        f"{rw.from_.day}–{rw.to.day} {rw.to.strftime('%b')} · "
        f"{avg_str} "
        f"(corpus: {pulse.review_count_corpus:,} reviews / "
        f"{(pulse.corpus_window.to - pulse.corpus_window.from_).days // 7} weeks)"
    )

    if pulse.window_note:
        lines.append(f"*{pulse.window_note}*")

    lines.append("")

    # Top themes
    lines.append("## Top themes")
    for i, t in enumerate(pulse.top_themes, 1):
        arrow = _TREND_ARROW.get(t.trend, "→ steady")
        avg = f"avg {t.avg_rating_week:.1f}★" if t.avg_rating_week is not None else "avg n/a"
        lines.append(
            f"{i}. **{t.label} — {t.count_week} reviews, {avg}, {arrow}.** "
            f"{t.summary}"
        )
    lines.append("")

    # Quotes
    lines.append("## What users said")
    for q in pulse.quotes:
        lines.append(f'> "{q.text}"')
    lines.append("")

    # Actions
    lines.append("## Action ideas")
    for i, a in enumerate(pulse.actions, 1):
        lines.append(f"{i}. **{a.title}.** {a.detail}")

    return "\n".join(lines) + "\n"
