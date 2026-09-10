"""Phase 6 — Docs append + Gmail draft via Railway MCP (fake tools only)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest

from src.config import Settings, load_settings
from src.publish import (
    PublishError,
    build_email_body,
    publish_pulse,
    resolve_tools,
)
from src.schemas import DateWindow, Pulse, PulseAction, PulseQuote, PulseTheme


class FakeTool:
    def __init__(self, name: str, handler):
        self.name = name
        self.calls: list[dict[str, Any]] = []
        self._handler = handler

    def invoke(self, input: dict[str, Any]) -> Any:
        self.calls.append(input)
        return self._handler(input)


def _minimal_pulse(*, week_ending: date | None = None) -> Pulse:
    we = week_ending or date(2026, 9, 5)
    return Pulse(
        product_name="Groww",
        week_ending=we,
        corpus_window=DateWindow(**{"from": date(2026, 6, 13), "to": we}),
        reporting_window=DateWindow(**{"from": date(2026, 8, 30), "to": we}),
        review_count_week=20,
        review_count_corpus=100,
        top_themes=[
            PulseTheme(
                id="payments",
                label="Payments & UPI",
                count_week=10,
                avg_rating_week=2.5,
                trend="rising",
                summary="UPI failures rose.",
            )
        ],
        quotes=[
            PulseQuote(
                text="UPI payment failed twice during checkout this week.",
                review_id="r1",
                theme_id="payments",
                rating=1,
                date=we,
            )
        ],
        actions=[
            PulseAction(
                title="Investigate UPI",
                detail="Check gateway timeouts.",
                theme_id="payments",
            )
        ],
        body_word_count=40,
    )


def _settings(tmp_path: Path, *, google_doc_id: str | None = "DOC123") -> Settings:
    base = load_settings()
    return Settings(
        app=base.app,
        env=base.env.model_copy(
            update={
                "mcp_server_url": "https://mcp-server-production-f0ca.up.railway.app",
                "mcp_http_token": "test-token",
                "google_doc_id": google_doc_id,
            }
        ),
        root=tmp_path,
    )


MD = "# Weekly Pulse\n\nPayments issues rose.\n"


class TestResolveTools:
    def test_resolves_railway_tool_names(self):
        tools = [
            FakeTool("append_to_google_doc", lambda _: {}),
            FakeTool("create_email_draft", lambda _: {}),
            FakeTool("send_email", lambda _: {"should": "never"}),
        ]
        resolved = resolve_tools(tools)
        assert resolved["append_doc"].name == "append_to_google_doc"
        assert resolved["draft_email"].name == "create_email_draft"
        assert "send_email" not in resolved.values()

    def test_missing_draft_lists_tools(self):
        tools = [FakeTool("append_to_google_doc", lambda _: {})]
        with pytest.raises(PublishError, match="draft tool missing"):
            resolve_tools(tools, require_draft=True)


class TestPublishPulse:
    def test_happy_path_append_and_draft(self, tmp_path: Path):
        append = FakeTool(
            "append_to_google_doc",
            lambda inp: {
                "success": True,
                "documentId": inp["documentId"],
                "message": "ok",
            },
        )
        draft = FakeTool(
            "create_email_draft",
            lambda inp: {"success": True, "draftId": "DRAFT99"},
        )
        send = FakeTool("send_email", lambda _: {"success": True})

        settings = _settings(tmp_path)
        pulse = _minimal_pulse()
        result = publish_pulse(
            pulse,
            MD,
            settings,
            tools=[append, draft, send],
            registry_path=tmp_path / "doc_registry.json",
        )

        assert result.docs_ok is True
        assert result.gmail_ok is True
        assert result.doc_id == "DOC123"
        assert result.doc_url == "https://docs.google.com/document/d/DOC123/edit"
        assert result.draft_id == "DRAFT99"
        assert send.calls == []  # never send

        assert len(append.calls) == 1
        assert append.calls[0]["documentId"] == "DOC123"
        assert "Payments issues rose" in append.calls[0]["content"]
        assert "Weekly Review Pulse" in append.calls[0]["content"]

        assert len(draft.calls) == 1
        assert draft.calls[0]["to"] == [settings.app.delivery.recipient]
        assert "2026-09-05" in draft.calls[0]["subject"]
        assert "Dear Sir/Madam" in draft.calls[0]["body"]
        assert "UPI failures rose" in draft.calls[0]["body"]
        assert "DOC123" not in draft.calls[0]["body"]
        assert "http" not in draft.calls[0]["body"]

        registry = (tmp_path / "doc_registry.json").read_text(encoding="utf-8")
        assert "2026-09-05" in registry
        assert "DOC123" in registry

    def test_same_week_rerun_reuses_registry_doc(self, tmp_path: Path):
        append = FakeTool(
            "append_to_google_doc",
            lambda inp: {"success": True, "documentId": inp["documentId"]},
        )
        draft = FakeTool(
            "create_email_draft",
            lambda _: {"success": True, "draftId": "D2"},
        )
        settings = _settings(tmp_path, google_doc_id="DEFAULT_DOC")
        registry = tmp_path / "doc_registry.json"
        registry.write_text(
            '{"2026-09-05": "WEEK_DOC", "_default": "DEFAULT_DOC"}',
            encoding="utf-8",
        )

        publish_pulse(
            _minimal_pulse(),
            MD,
            settings,
            tools=[append, draft],
            registry_path=registry,
        )
        assert append.calls[0]["documentId"] == "WEEK_DOC"

    def test_docs_soft_fail_still_drafts_full_note(self, tmp_path: Path):
        append = FakeTool(
            "append_to_google_doc",
            lambda _: {"success": False, "error": {"message": "DOCUMENT_NOT_FOUND"}},
        )
        draft = FakeTool(
            "create_email_draft",
            lambda _: {"success": True, "draftId": "D3"},
        )
        settings = _settings(tmp_path)
        result = publish_pulse(
            _minimal_pulse(),
            MD,
            settings,
            tools=[append, draft],
            registry_path=tmp_path / "doc_registry.json",
        )
        assert result.docs_ok is False
        assert result.doc_url is None
        assert result.gmail_ok is True
        assert result.draft_id == "D3"
        assert any("Docs append failed" in w for w in result.warnings)
        assert "Dear Sir/Madam" in draft.calls[0]["body"]
        assert "UPI failures rose" in draft.calls[0]["body"]
        assert "http" not in draft.calls[0]["body"]
        assert "docs.google" not in draft.calls[0]["body"]

    def test_gmail_hard_fail(self, tmp_path: Path):
        append = FakeTool(
            "append_to_google_doc",
            lambda inp: {"success": True, "documentId": inp["documentId"]},
        )
        draft = FakeTool(
            "create_email_draft",
            lambda _: {"success": False, "error": {"message": "INVALID_EMAIL"}},
        )
        settings = _settings(tmp_path)
        with pytest.raises(PublishError, match="Gmail draft failed"):
            publish_pulse(
                _minimal_pulse(),
                MD,
                settings,
                tools=[append, draft],
                registry_path=tmp_path / "doc_registry.json",
            )

    def test_no_doc_id_skips_docs_still_drafts(self, tmp_path: Path):
        draft = FakeTool(
            "create_email_draft",
            lambda _: {"success": True, "draftId": "D4"},
        )
        settings = _settings(tmp_path, google_doc_id=None)
        result = publish_pulse(
            _minimal_pulse(),
            MD,
            settings,
            tools=[draft],
            registry_path=tmp_path / "empty_registry.json",
        )
        assert result.docs_ok is False
        assert result.gmail_ok is True
        assert any("GOOGLE_DOC_ID" in w for w in result.warnings)

    def test_never_invokes_send_email(self, tmp_path: Path):
        append = FakeTool(
            "append_to_google_doc",
            lambda inp: {"success": True, "documentId": inp["documentId"]},
        )
        draft = FakeTool(
            "create_email_draft",
            lambda _: {"success": True, "draftId": "D5"},
        )
        send = FakeTool("send_email", lambda _: {"success": True, "id": "SENT"})
        settings = _settings(tmp_path)
        publish_pulse(
            _minimal_pulse(),
            MD,
            settings,
            tools=[append, draft, send],
            registry_path=tmp_path / "reg.json",
        )
        assert send.calls == []

    def test_payload_is_note_not_corpus(self, tmp_path: Path):
        append = FakeTool(
            "append_to_google_doc",
            lambda inp: {"success": True, "documentId": inp["documentId"]},
        )
        draft = FakeTool(
            "create_email_draft",
            lambda _: {"success": True, "draftId": "D6"},
        )
        settings = _settings(tmp_path)
        publish_pulse(
            _minimal_pulse(),
            MD,
            settings,
            tools=[append, draft],
            registry_path=tmp_path / "reg.json",
        )
        blob = str(append.calls) + str(draft.calls)
        assert "review_ids" not in blob
        assert "corpus" not in blob.lower() or "Payments" in blob


    def test_append_doc_only_no_gmail(self, tmp_path: Path):
        append = FakeTool(
            "append_to_google_doc",
            lambda inp: {"success": True, "documentId": inp["documentId"]},
        )
        draft = FakeTool(
            "create_email_draft",
            lambda _: {"success": True, "draftId": "SHOULD_NOT"},
        )
        from src.publish import append_pulse_to_google_doc

        settings = _settings(tmp_path)
        result = append_pulse_to_google_doc(
            _minimal_pulse(),
            MD,
            settings,
            tools=[append, draft],
            registry_path=tmp_path / "reg.json",
        )
        assert result.docs_ok is True
        assert result.doc_url
        assert result.draft_id is None
        assert draft.calls == []
        assert len(append.calls) == 1


class TestParsePayload:
    def test_nested_content_block_string(self):
        from src.publish import _parse_tool_payload

        raw = (
            "[{'type': 'text', 'text': '{\"success\":true,\"message\":\"Email draft "
            "created successfully.\",\"draftId\":\"r1587435771316626431\"}', "
            "'id': 'lc_154b2f30-714f-4cbf-8026-72405311e67c'}]"
        )
        payload = _parse_tool_payload({"message": raw, "success": True})
        assert payload.get("draftId") == "r1587435771316626431"
        assert payload.get("success") is True


class TestEmailBody:
    def test_stakeholder_brief_without_links(self):
        pulse = _minimal_pulse()
        body = build_email_body(pulse, MD, "https://docs.google.com/document/d/X/edit", "full_note_plus_link")
        assert "Dear Sir/Madam" in body
        assert "Top themes" in body
        assert "Payments & UPI" in body
        assert "UPI failures rose" in body
        assert "Action items" in body
        assert "Investigate UPI" in body
        assert "Regards" in body
        assert "http" not in body
        assert "docs.google.com" not in body
        assert "Weekly Review Pulse — Groww — week ending" not in body.split("\n")[0]

    def test_link_only_also_omits_urls(self):
        pulse = _minimal_pulse()
        body = build_email_body(
            pulse, MD, "https://docs.google.com/document/d/X/edit", "link_only"
        )
        assert "Dear Sir/Madam" in body
        assert "document/d/X" not in body
        assert "http" not in body
        assert "UPI failures rose" in body
        assert "Regards" in body
