"""Local Stitch dashboard server."""

from pathlib import Path

from src.web import FRONTEND, ARTIFACTS


def test_frontend_files_exist():
    assert (FRONTEND / "index.html").is_file()
    assert (FRONTEND / "js" / "app.js").is_file()
    assert (FRONTEND / "css" / "app.css").is_file()
    html = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert "Weekly Review Pulse" in html
    assert "Fee context" not in html
    js = (FRONTEND / "js" / "app.js").read_text(encoding="utf-8")
    assert "Fee context" not in js
    assert "Create email draft" in js


def test_artifacts_dir_is_under_repo():
    assert ARTIFACTS == Path(__file__).resolve().parents[1] / "data" / "artifacts"
