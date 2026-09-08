"""Weekly Review Pulse entrypoint."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

from .config import load_settings
from .archive import parse_week_ending


def _import_pipeline():
    """Lazy-import LLM/pipeline deps so ``--serve`` works with slim Railway deps."""
    from .agent.runner import orchestration_status_block, run_generate_validate
    from .cluster import cluster_reviews, write_cluster_artifacts
    from .ingest import EmptyCorpusError, IngestError, ingest_paths, ingest_exports_dir
    from .llm import create_chat_model
    from .publish import (
        PublishError,
        publish_pulse,
        update_pulse_artifact_with_publish,
    )
    from .redact import redact_from_artifacts
    from .schedule import week_already_published
    from .theme_math import top_n_themes

    return {
        "orchestration_status_block": orchestration_status_block,
        "run_generate_validate": run_generate_validate,
        "cluster_reviews": cluster_reviews,
        "write_cluster_artifacts": write_cluster_artifacts,
        "EmptyCorpusError": EmptyCorpusError,
        "IngestError": IngestError,
        "ingest_paths": ingest_paths,
        "ingest_exports_dir": ingest_exports_dir,
        "create_chat_model": create_chat_model,
        "PublishError": PublishError,
        "publish_pulse": publish_pulse,
        "update_pulse_artifact_with_publish": update_pulse_artifact_with_publish,
        "redact_from_artifacts": redact_from_artifacts,
        "week_already_published": week_already_published,
        "top_n_themes": top_n_themes,
    }


def _print_config() -> int:
    settings = load_settings()
    app = settings.app
    env = settings.env
    summary = {
        "phase": 6,
        "status": "config",
        "product_name": app.product_name,
        "package_id": app.package_id,
        "play_store_url": app.play_store_url,
        "root": str(settings.root),
        "windows": app.windows.model_dump(),
        "themes": {
            "max_total": app.themes.max_total,
            "highlight": app.themes.highlight,
            "seeds": [s.model_dump() for s in app.themes.seeds],
        },
        "note": app.note.model_dump(),
        "delivery": {
            "recipient": app.delivery.recipient,
            "doc_title": app.delivery.doc_title,
            "email_subject": app.delivery.email_subject,
            "email_body_mode": app.delivery.email_body_mode,
        },
        "limits": app.limits.model_dump(),
        "schedule": app.schedule.model_dump(),
        "env": {
            "pulse_model": env.pulse_model,
            "mcp_server_url": env.mcp_server_url,
            "mcp_http_token_set": bool(env.mcp_http_token),
            "google_doc_id_set": bool(env.google_doc_id),
            "docs_mcp_server": env.docs_mcp_server,
            "gmail_mcp_server": env.gmail_mcp_server,
            "langsmith_tracing": env.langsmith_tracing,
            "groq_api_key_set": bool(env.groq_api_key),
        },
    }
    print(json.dumps(summary, indent=2))
    return 0


def _ensure_exports(settings) -> Path:
    """If data/exports is empty, copy Play fixture so a local smoke run works."""
    exports = settings.root / "data" / "exports"
    exports.mkdir(parents=True, exist_ok=True)
    existing = [
        p
        for p in exports.iterdir()
        if p.is_file()
        and p.suffix.lower() in {".csv", ".json", ".jsonl"}
        and p.name not in {".gitkeep", "README.md"}
    ]
    if existing:
        return exports

    fixture = settings.root / "tests" / "fixtures" / "play_reviews_sample.csv"
    if fixture.is_file():
        dest = exports / fixture.name
        shutil.copy2(fixture, dest)
        print(f"[ingest] data/exports empty - copied fixture to {dest}")
    return exports


def _run_pipeline(
    paths: list[str] | None,
    *,
    skip_llm: bool,
    skip_publish: bool,
    once_per_week: bool = False,
    week_ending_override: date | None = None,
) -> int:
    deps = _import_pipeline()
    EmptyCorpusError = deps["EmptyCorpusError"]
    IngestError = deps["IngestError"]
    ingest_paths = deps["ingest_paths"]
    ingest_exports_dir = deps["ingest_exports_dir"]
    redact_from_artifacts = deps["redact_from_artifacts"]
    create_chat_model = deps["create_chat_model"]
    cluster_reviews = deps["cluster_reviews"]
    write_cluster_artifacts = deps["write_cluster_artifacts"]
    top_n_themes = deps["top_n_themes"]
    run_generate_validate = deps["run_generate_validate"]
    orchestration_status_block = deps["orchestration_status_block"]
    week_already_published = deps["week_already_published"]
    publish_pulse = deps["publish_pulse"]
    update_pulse_artifact_with_publish = deps["update_pulse_artifact_with_publish"]
    PublishError = deps["PublishError"]

    settings = load_settings()
    artifacts = settings.root / "data" / "artifacts"
    try:
        if paths:
            ingest_result = ingest_paths(
                [Path(path) for path in paths],
                settings.app,
                week_ending_override=week_ending_override,
                artifacts_dir=artifacts,
                write_artifacts=True,
            )
        else:
            _ensure_exports(settings)
            ingest_result = ingest_exports_dir(
                settings,
                write_artifacts=True,
                week_ending_override=week_ending_override,
            )

        print(
            f"[ingest] kept {ingest_result.report.rows_kept} "
            f"(week {ingest_result.report.review_count_week})",
            file=sys.stderr,
        )
        redact_result = redact_from_artifacts(artifacts, write_artifacts=True)
        print(
            f"[redact] {redact_result.report.reviews_out} reviews "
            f"(fields_touched={redact_result.report.fields_touched})",
            file=sys.stderr,
        )
    except EmptyCorpusError as e:
        print(f"[ingest] empty corpus: {e}", file=sys.stderr)
        return 2
    except (IngestError, FileNotFoundError, ValueError) as e:
        print(f"[pipeline] error: {e}", file=sys.stderr)
        return 1

    status: dict = {
        "phase": 6,
        "status": "ingest_redact_ok",
        "ingest": {
            "rows_kept": ingest_result.report.rows_kept,
            "week_ending": ingest_result.report.week_ending,
            "corpus": {
                "from": ingest_result.report.corpus_from,
                "to": ingest_result.report.corpus_to,
            },
            "reporting": {
                "from": ingest_result.report.reporting_from,
                "to": ingest_result.report.reporting_to,
                "count": ingest_result.report.review_count_week,
                "window_note": ingest_result.report.window_note,
            },
            "skipped_appstore": ingest_result.report.files_skipped_appstore,
            "dropped": {
                "empty_text": ingest_result.report.rows_dropped_empty_text,
                "short_text": ingest_result.report.rows_dropped_short_text,
                "non_english": ingest_result.report.rows_dropped_non_english,
                "bad_date": ingest_result.report.rows_dropped_bad_date,
                "outside_window": ingest_result.report.rows_dropped_outside_window,
                "duplicate": ingest_result.report.rows_dropped_duplicate,
            },
        },
        "redact": {
            "reviews_out": redact_result.report.reviews_out,
            "fields_touched": redact_result.report.fields_touched,
            "replacements": redact_result.report.replacements,
        },
        "artifacts": str(artifacts),
    }

    llm = None if skip_llm else create_chat_model(settings)
    if llm is None:
        status["status"] = "ingest_redact_ok_llm_skipped"
        status["llm"] = {
            "ran": False,
            "reason": "skip_llm flag" if skip_llm else "GROQ_API_KEY not set",
        }
        print(json.dumps(status, indent=2))
        return 0

    try:
        corpus_from = ingest_result.corpus_from
        corpus_to = ingest_result.corpus_to
        reporting_from = ingest_result.reporting_from
        reporting_to = ingest_result.reporting_to
        week_ending = ingest_result.week_ending

        print(
            f"[cluster] {len(redact_result.reviews)} redacted reviews → themes…",
            file=sys.stderr,
        )
        themes = cluster_reviews(
            llm,
            redact_result.reviews,
            settings.app,
            corpus_from=corpus_from,
            corpus_to=corpus_to,
            reporting_from=reporting_from,
            reporting_to=reporting_to,
        )
        write_cluster_artifacts(themes, artifacts)
        print(
            f"[cluster] {len(themes)} themes: "
            + ", ".join(f"{t.id}={t.count_week}" for t in themes),
            file=sys.stderr,
        )

        top = top_n_themes(themes, settings.app.themes.highlight)
        print(f"[generate] top themes: {[t.id for t in top]}", file=sys.stderr)

        orch = run_generate_validate(
            llm,
            top,
            themes,
            redact_result.reviews,
            settings.app,
            corpus_from=corpus_from,
            corpus_to=corpus_to,
            reporting_from=reporting_from,
            reporting_to=reporting_to,
            week_ending=week_ending,
            window_note=ingest_result.window_note,
            review_count_corpus=len(redact_result.reviews),
            artifacts_dir=artifacts,
            publish_fn=None,  # publish runs only after validate_ok below
        )
        print(
            f"[validate] {orch.status} attempts={orch.attempts} "
            f"failures={orch.validation.failures if orch.validation else []}",
            file=sys.stderr,
        )

        status["llm"] = {"ran": True, "model": settings.env.pulse_model}
        status["cluster"] = {
            "theme_count": len(themes),
            "themes": [
                {
                    "id": t.id,
                    "label": t.label,
                    "count_week": t.count_week,
                    "trend": t.trend,
                }
                for t in themes
            ],
        }
        status["orchestration"] = orchestration_status_block(orch)

        if orch.status != "passed":
            status["status"] = orch.status
            print(json.dumps(status, indent=2))
            return 3

        status["status"] = "validate_ok"
        exit_code = 0

        # Phase 6 — MCP publish only after validate passes
        do_publish = not skip_publish
        skip_reason: str | None = None
        if skip_publish:
            skip_reason = "skip_publish flag"
        elif once_per_week and orch.pulse is not None:
            week_key = orch.pulse.week_ending.isoformat()
            registry_file = settings.root / "data" / "state" / "doc_registry.json"
            if week_already_published(registry_file, week_key):
                do_publish = False
                skip_reason = f"once_per_week: {week_key} already in doc_registry"
        if do_publish and not settings.env.mcp_http_token:
            do_publish = False
            skip_reason = "MCP_HTTP_TOKEN not set — skipped Docs/Gmail publish"

        if not do_publish:
            status["publish"] = {"ran": False, "reason": skip_reason}
            print(f"[publish] skipped ({skip_reason})", file=sys.stderr)
        else:
            assert orch.pulse is not None and orch.md is not None
            print(
                f"[publish] MCP {settings.env.mcp_server_url}/mcp …",
                file=sys.stderr,
            )
            try:
                pub = publish_pulse(orch.pulse, orch.md, settings)
                update_pulse_artifact_with_publish(artifacts, orch.pulse, pub)
                status["publish"] = pub.to_dict()
                status["status"] = "publish_ok"
                print(
                    f"[publish] draft_id={pub.draft_id} doc_url={pub.doc_url} "
                    f"warnings={pub.warnings}",
                    file=sys.stderr,
                )
            except PublishError as e:
                status["status"] = "publish_failed"
                status["publish"] = {"ran": True, "error": str(e)}
                print(f"[publish] failed: {e}", file=sys.stderr)
                print(json.dumps(status, indent=2))
                return 4

    except Exception as e:
        print(f"[pipeline] LLM stage error: {e}", file=sys.stderr)
        status["status"] = "llm_failed"
        status["llm"] = {"ran": True, "error": str(e)}
        print(json.dumps(status, indent=2))
        return 1

    print(json.dumps(status, indent=2))
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Weekly Review Pulse")
    parser.add_argument(
        "--config-only",
        action="store_true",
        help="Print loaded config and exit (Phase 0 behaviour)",
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Stop after ingest+redact (no cluster/generate/validate)",
    )
    parser.add_argument(
        "--skip-publish",
        action="store_true",
        help="Stop after validate (no Docs/Gmail MCP publish)",
    )
    parser.add_argument(
        "--once-per-week",
        action="store_true",
        help="Skip Docs/Gmail if this week_ending is already in doc_registry",
    )
    parser.add_argument(
        "--week-ending",
        default=None,
        metavar="YYYY-MM-DD",
        help="Override reporting week end (for regenerating a past week into history)",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Serve the local Stitch dashboard (http://127.0.0.1:8080/)",
    )
    parser.add_argument(
        "--backend-only",
        action="store_true",
        help="With --serve: JSON API only (no static frontend)",
    )
    parser.add_argument("--host", default=None, help="Dashboard bind host")
    parser.add_argument("--port", type=int, default=None, help="Dashboard bind port")
    parser.add_argument(
        "exports",
        nargs="*",
        help="Optional export file paths (default: data/exports/)",
    )
    args = parser.parse_args(argv)

    if args.config_only:
        return _print_config()
    if args.serve:
        from .web import serve

        return serve(host=args.host, port=args.port, backend_only=args.backend_only)

    week_override: date | None = None
    if args.week_ending:
        week_override = parse_week_ending(args.week_ending)
        if week_override is None:
            print(f"Invalid --week-ending: {args.week_ending}", file=sys.stderr)
            return 1

    return _run_pipeline(
        args.exports or None,
        skip_llm=args.skip_llm,
        skip_publish=args.skip_publish,
        once_per_week=args.once_per_week,
        week_ending_override=week_override,
    )


if __name__ == "__main__":
    sys.exit(main())
