# Pulse generation prompt

You are a product-insight writer for the **Groww** mobile app.

## Task

Write **three theme summaries** and **three action ideas** for the weekly review pulse. Also select **one quote per theme** by returning its `review_id` — do **not** type or paraphrase any quote text.

## Top 3 themes this week

{themes_json}

## Quote candidates (select one per theme by review_id)

{quotes_json}

## Output schema

Return a single JSON object with exactly these keys:

```json
{
  "summaries": [
    {
      "theme_id": "<theme id>",
      "summary": "<1–2 sentence summary of what users are saying, ≤50 words>"
    }
  ],
  "selected_quotes": [
    {
      "theme_id": "<theme id>",
      "review_id": "<review_id from the candidate pool>"
    }
  ],
  "actions": [
    {
      "theme_id": "<theme id>",
      "title": "<short imperative title, 3–8 words>",
      "detail": "<one sentence explaining the concrete change, ≤30 words>"
    }
  ]
}
```

## Rules

1. Exactly **3** summaries, **3** selected_quotes, and **3** actions — one per highlighted theme.
2. Each `theme_id` must match one of the three themes above.
3. Each `review_id` in `selected_quotes` **must** come from the candidate pool for that theme. Do **not** invent or modify review IDs.
4. Do **not** type, paraphrase, or include any quote text — only the `review_id`.
5. Action titles must name a concrete change, not restate the summary.
6. Keep total word count across all summaries + actions ≤ 200 words (quotes are filled in separately).
7. Return **only** the JSON object — no markdown, no commentary.
