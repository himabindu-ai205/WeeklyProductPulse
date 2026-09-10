"""Phase 6 — publish pulse via remote Google Workspace MCP (Railway).

MCP server: https://github.com/himabindu-ai205/MCP-Server
Deployed Streamable HTTP: ``{MCP_SERVER_URL}/mcp`` with ``Authorization: Bearer``.

Exposed tools we use:
  - ``append_to_google_doc`` — append pulse markdown to an existing Doc
  - ``create_email_draft`` — Gmail draft only (never ``send_email``)

This module never imports Google client libraries.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence

from .config import Settings
from .schemas import Pulse


class McpTool(Protocol):
    name: str

    def invoke(self, input: dict[str, Any]) -> Any: ...


@dataclass
class PublishResult:
    doc_id: str | None = None
    doc_url: str | None = None
    draft_id: str | None = None
    docs_ok: bool = False
    gmail_ok: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PublishError(RuntimeError):
    """Hard publish failure (e.g. draft tool missing or Gmail draft failed)."""


def _parse_tool_payload(raw: Any) -> dict[str, Any]:
    """Normalize LangChain / MCP tool return values into a dict envelope."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        # Unwrap common adapter shapes: {"content": [...]} / nested success payloads
        if "content" in raw and not any(
            k in raw for k in ("success", "draftId", "documentId", "error")
        ):
            return _parse_tool_payload(raw["content"])
        # Nested JSON string inside message from failed top-level parse
        msg = raw.get("message")
        if isinstance(msg, str) and ("draftId" in msg or "documentId" in msg or '"success"' in msg):
            nested = _extract_json_object(msg)
            if nested:
                return {**raw, **nested}
        return raw
    if isinstance(raw, (list, tuple)):
        # MCP content blocks: [{"type":"text","text":"{...}"}]
        texts: list[str] = []
        for item in raw:
            if isinstance(item, dict) and "text" in item:
                texts.append(str(item["text"]))
            else:
                texts.append(str(item))
        for text in texts:
            data = _extract_json_object(text)
            if data:
                return data
        return {"message": "\n".join(texts), "success": True} if texts else {}

    text = raw if isinstance(raw, str) else str(raw)
    text = text.strip()
    if not text:
        return {}
    data = _extract_json_object(text)
    if data:
        return data
    return {"message": text, "success": True}


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """Best-effort extract a JSON object from tool output text / repr."""
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
        if isinstance(data, list):
            return _parse_tool_payload(data) or None
    except json.JSONDecodeError:
        pass

    # Python-repr content blocks from some adapters
    if "draftId" in text or "documentId" in text or '"success"' in text:
        m = re.search(r"\{[^{}]*\"(?:success|draftId|documentId)\"[^{}]*\}", text)
        if m:
            try:
                data = json.loads(m.group(0))
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass
        # Escape-heavy nested JSON inside a text field
        m = re.search(r"\{(?:[^{}]|\\.)*\}", text)
        if m:
            candidate = m.group(0)
            # Unescape common \\ \" sequences if double-encoded
            for attempt in (candidate, candidate.encode().decode("unicode_escape")):
                try:
                    data = json.loads(attempt)
                    if isinstance(data, dict):
                        return data
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue

    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    return None


def resolve_tools(
    tools: Sequence[Any],
    *,
    require_draft: bool = True,
) -> dict[str, Any]:
    """Resolve MCP tools by capability name (not hardcoded beyond known names)."""
    by_name = {getattr(t, "name", ""): t for t in tools}
    resolved: dict[str, Any] = {}

    # Prefer exact names from the Railway google-workspace MCP server
    if "append_to_google_doc" in by_name:
        resolved["append_doc"] = by_name["append_to_google_doc"]
    else:
        for name, tool in by_name.items():
            if "append" in name.lower() and "doc" in name.lower():
                resolved["append_doc"] = tool
                break

    if "create_email_draft" in by_name:
        resolved["draft_email"] = by_name["create_email_draft"]
    else:
        for name, tool in by_name.items():
            n = name.lower()
            if "draft" in n and ("email" in n or "gmail" in n or "mail" in n):
                resolved["draft_email"] = tool
                break

    # Explicitly ignore send_email — never auto-send
    if require_draft and "draft_email" not in resolved:
        raise PublishError(
            "MCP draft tool missing. Exposed tools: "
            + ", ".join(sorted(by_name.keys()) or ["(none)"])
        )
    return resolved


def load_doc_registry(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def save_doc_registry(path: Path, registry: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, indent=2), encoding="utf-8")


def build_email_body(pulse: Pulse, md: str, doc_url: str | None, mode: str) -> str:
    """Stakeholder email body (themes + actions). No Doc/dashboard links."""
    _ = md
    _ = doc_url
    _ = mode
    week = pulse.week_ending.isoformat()
    avg = (
        f"{pulse.avg_rating_week:.1f}★"
        if pulse.avg_rating_week is not None
        else "n/a"
    )

    theme_blocks: list[str] = []
    for i, t in enumerate(pulse.top_themes, start=1):
        summary = (t.summary or "").strip() or "No summary available."
        theme_blocks.append(f"{i}. {t.label}\n   {summary}")

    action_blocks: list[str] = []
    for i, a in enumerate(pulse.actions, start=1):
        detail = (a.detail or "").strip()
        if detail:
            action_blocks.append(f"{i}. {a.title}\n   {detail}")
        else:
            action_blocks.append(f"{i}. {a.title}")

    themes_section = "\n\n".join(theme_blocks) if theme_blocks else "No themes available."
    actions_section = "\n\n".join(action_blocks) if action_blocks else "No action items available."

    return (
        f"Dear Sir/Madam,\n\n"
        f"Please find the highlights of the Weekly Review Pulse for {pulse.product_name} "
        f"for the week ending {week}.\n\n"
        f"Snapshot: average rating {avg} · {pulse.review_count_week} Play Store reviews\n\n"
        f"Top themes\n"
        f"{themes_section}\n\n"
        f"Action items\n"
        f"{actions_section}\n\n"
        f"Regards\n"
        f"Weekly Review Pulse\n"
    )


def doc_url_for_id(document_id: str) -> str:
    return f"https://docs.google.com/document/d/{document_id}/edit"


def _call_tool(tool: Any, payload: dict[str, Any]) -> Any:
    """Invoke a LangChain tool, preferring sync then async (MCP adapters)."""
    invoke = getattr(tool, "invoke", None)
    ainvoke = getattr(tool, "ainvoke", None)

    if invoke is not None:
        try:
            return invoke(payload)
        except Exception as e:  # noqa: BLE001
            msg = str(e).lower()
            # langchain_mcp_adapters StructuredTool is async-only
            if ainvoke is None or (
                "sync" not in msg and "ainvoke" not in msg and "coroutine" not in msg
            ):
                raise

    if ainvoke is None:
        raise PublishError(
            f"Tool {getattr(tool, 'name', tool)!r} has neither invoke nor ainvoke"
        )

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(ainvoke(payload))

    # Already inside an event loop — run ainvoke on a worker thread's loop
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(ainvoke(payload))).result()


async def load_mcp_tools_async(settings: Settings) -> list[Any]:
    """Connect to the Railway Streamable HTTP MCP and list tools."""
    url = (settings.env.mcp_server_url or "").rstrip("/")
    if not url.endswith("/mcp"):
        url = f"{url}/mcp"
    token = settings.env.mcp_http_token
    if not token:
        raise PublishError("MCP_HTTP_TOKEN is required to call the Railway MCP server")

    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient(
        {
            "google-workspace": {
                "transport": "streamable_http",
                "url": url,
                "headers": {"Authorization": f"Bearer {token}"},
            }
        }
    )
    return await client.get_tools()


def load_mcp_tools(settings: Settings) -> list[Any]:
    return asyncio.run(load_mcp_tools_async(settings))


def publish_doc(
    tools: dict[str, Any],
    *,
    document_id: str,
    content: str,
) -> tuple[str | None, str | None, str | None]:
    """Append content to an existing Google Doc via MCP.

    Returns (document_id, doc_url, error_message).
    """
    tool = tools.get("append_doc")
    if tool is None:
        return None, None, "append_to_google_doc tool not available"
    try:
        raw = _call_tool(tool, {"documentId": document_id, "content": content})
        payload = _parse_tool_payload(raw)
        if payload.get("success") is False:
            err = payload.get("error") or {}
            msg = err.get("message") if isinstance(err, dict) else str(payload)
            return None, None, msg or "append_to_google_doc failed"
        doc_id = payload.get("documentId") or document_id
        return str(doc_id), doc_url_for_id(str(doc_id)), None
    except Exception as e:  # noqa: BLE001
        return None, None, str(e)


def draft_email(
    tools: dict[str, Any],
    *,
    to: str,
    subject: str,
    body: str,
) -> tuple[str | None, str | None]:
    """Create a Gmail draft via MCP. Returns (draft_id, error_message)."""
    tool = tools.get("draft_email")
    if tool is None:
        return None, "create_email_draft tool not available"
    try:
        raw = _call_tool(
            tool,
            {
                "to": [to],
                "subject": subject,
                "body": body,
            },
        )
        payload = _parse_tool_payload(raw)
        if payload.get("success") is False:
            err = payload.get("error") or {}
            msg = err.get("message") if isinstance(err, dict) else str(payload)
            return None, msg or "create_email_draft failed"
        draft_id = payload.get("draftId") or payload.get("draft_id")
        if not draft_id:
            # Last-resort: pull id from raw text if envelope nesting confused the parser
            m = re.search(r'"draftId"\s*:\s*"([^"]+)"', str(raw))
            if m:
                draft_id = m.group(1)
        if not draft_id:
            return None, f"draft created but no draftId in response: {payload}"
        return str(draft_id), None
    except Exception as e:  # noqa: BLE001
        return None, str(e)


def build_doc_append_content(md: str, *, week_key: str, doc_title: str) -> str:
    """Build Docs append payload: week separator + pulse body (no duplicate H1)."""
    body = (md or "").rstrip()
    title_line = f"# {doc_title.format(week_ending=week_key)}"
    if body.lstrip().startswith("# Weekly Review Pulse"):
        return f"\n\n---\n\n{body}\n"
    return f"\n\n---\n\n{title_line}\n\n{body}\n"


def publish_pulse(
    pulse: Pulse,
    md: str,
    settings: Settings,
    *,
    tools: Sequence[Any] | None = None,
    registry_path: Path | None = None,
    load_tools_fn: Callable[[Settings], list[Any]] | None = None,
) -> PublishResult:
    """Publish Docs append + Gmail draft after validation passed.

    Error policy (architecture §13 / Phase 6):
    - Docs failure → warn, continue with full-note draft, ``doc_url=null``
    - Gmail draft failure → hard fail (``PublishError``)
    """
    result = PublishResult()
    app = settings.app
    week_key = pulse.week_ending.isoformat()

    registry_file = registry_path or (settings.root / "data" / "state" / "doc_registry.json")
    registry = load_doc_registry(registry_file)

    # This MCP server cannot create Docs — use configured or registry id
    document_id = (
        registry.get(week_key)
        or settings.env.google_doc_id
        or registry.get("_default")
    )

    loader = load_tools_fn or load_mcp_tools
    mcp_tools = list(tools) if tools is not None else loader(settings)
    resolved = resolve_tools(mcp_tools, require_draft=True)

    # --- Docs (soft-fail) ---
    if not document_id:
        result.warnings.append(
            "No GOOGLE_DOC_ID / registry entry — skipped Docs append. "
            "Create a Doc once and set GOOGLE_DOC_ID in .env."
        )
    else:
        content = build_doc_append_content(
            md, week_key=week_key, doc_title=app.delivery.doc_title
        )
        doc_id, doc_url, err = publish_doc(
            resolved, document_id=document_id, content=content
        )
        if err:
            result.warnings.append(f"Docs append failed: {err}")
        else:
            result.docs_ok = True
            result.doc_id = doc_id
            result.doc_url = doc_url
            registry[week_key] = str(doc_id)
            if settings.env.google_doc_id:
                registry["_default"] = settings.env.google_doc_id
            save_doc_registry(registry_file, registry)

    # --- Gmail draft (hard-fail) ---
    subject = app.delivery.email_subject.format(week_ending=week_key)
    body = build_email_body(
        pulse, md, result.doc_url, app.delivery.email_body_mode
    )
    draft_id, err = draft_email(
        resolved,
        to=app.delivery.recipient,
        subject=subject,
        body=body,
    )
    if err:
        result.errors.append(err)
        raise PublishError(f"Gmail draft failed: {err}")
    result.gmail_ok = True
    result.draft_id = draft_id

    # Persist ids onto pulse artifact if present
    return result


def append_pulse_to_google_doc(
    pulse: Pulse,
    md: str,
    settings: Settings,
    *,
    tools: Sequence[Any] | None = None,
    registry_path: Path | None = None,
    load_tools_fn: Callable[[Settings], list[Any]] | None = None,
) -> PublishResult:
    """Append pulse markdown to the configured Google Doc only (no Gmail draft).

    Uses ``GOOGLE_DOC_ID`` / registry — never creates a new Drive file.
    Hard-fails if the Doc id is missing or append fails (for UI / API callers).
    """
    result = PublishResult()
    app = settings.app
    week_key = pulse.week_ending.isoformat()

    registry_file = registry_path or (settings.root / "data" / "state" / "doc_registry.json")
    registry = load_doc_registry(registry_file)

    document_id = (
        registry.get(week_key)
        or settings.env.google_doc_id
        or registry.get("_default")
    )
    if not document_id:
        raise PublishError(
            "No GOOGLE_DOC_ID configured. Create a Doc once and set GOOGLE_DOC_ID in .env."
        )

    loader = load_tools_fn or load_mcp_tools
    mcp_tools = list(tools) if tools is not None else loader(settings)
    resolved = resolve_tools(mcp_tools, require_draft=False)
    if "append_doc" not in resolved:
        names = sorted(getattr(t, "name", "") for t in mcp_tools)
        raise PublishError(
            "MCP append_to_google_doc tool missing. Exposed tools: "
            + ", ".join(names or ["(none)"])
        )

    content = build_doc_append_content(
        md, week_key=week_key, doc_title=app.delivery.doc_title
    )
    doc_id, doc_url, err = publish_doc(
        resolved, document_id=document_id, content=content
    )
    if err:
        raise PublishError(f"Docs append failed: {err}")

    result.docs_ok = True
    result.doc_id = doc_id
    result.doc_url = doc_url
    registry[week_key] = str(doc_id)
    if settings.env.google_doc_id:
        registry["_default"] = settings.env.google_doc_id
    save_doc_registry(registry_file, registry)
    return result


def update_pulse_artifact_with_publish(
    artifacts_dir: Path,
    pulse: Pulse,
    publish: PublishResult,
) -> Pulse:
    """Write doc_url / draft_id back into pulse.json (latest + history)."""
    updated = pulse.model_copy(
        update={
            "doc_url": publish.doc_url if publish.doc_url is not None else pulse.doc_url,
            "draft_id": publish.draft_id if publish.draft_id is not None else pulse.draft_id,
        }
    )
    path = artifacts_dir / "pulse.json"
    path.write_text(
        json.dumps(updated.model_dump(mode="json"), indent=2), encoding="utf-8"
    )
    report_path = artifacts_dir / "publish_report.json"
    report_path.write_text(json.dumps(publish.to_dict(), indent=2), encoding="utf-8")
    try:
        from .archive import archive_pulse

        md_path = artifacts_dir / "pulse.md"
        md = md_path.read_text(encoding="utf-8") if md_path.is_file() else ""
        hist_md = (
            artifacts_dir
            / "history"
            / updated.week_ending.isoformat()
            / "pulse.md"
        )
        if hist_md.is_file():
            md = hist_md.read_text(encoding="utf-8")
        archive_pulse(updated, md, artifacts_dir, update_latest=True)
    except Exception:  # noqa: BLE001
        pass
    return updated
