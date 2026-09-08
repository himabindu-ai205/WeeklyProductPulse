"""Phase 0: pytest discovers the suite (real pipeline tests land in later phases)."""


def test_phase0_config_loads():
    from src.config import load_settings

    settings = load_settings()
    assert settings.app.product_name == "Groww"
    assert settings.app.package_id == "com.nextbillion.groww"
    assert "com.nextbillion.groww" in settings.app.play_store_url
    assert settings.app.themes.max_total == 5
    assert settings.app.note.max_words == 250
    # Scaffold must run without a model key
    assert settings.env.groq_api_key is None or isinstance(settings.env.groq_api_key, str)
    assert settings.env.pulse_model == "openai/gpt-oss-120b" or isinstance(
        settings.env.pulse_model, str
    )


def test_phase0_fixtures_exist():
    from pathlib import Path

    root = Path(__file__).resolve().parent
    play = root / "fixtures" / "play_reviews_sample.csv"
    appstore = root / "fixtures" / "appstore_reviews_sample.csv"
    assert play.is_file()
    assert appstore.is_file()
    play_text = play.read_text(encoding="utf-8")
    assert "user@example.com" in play_text
    assert "Reviewer Name" in play_text
    app_text = appstore.read_text(encoding="utf-8")
    assert "Review ID" in app_text
    assert "Reviewer Nickname" in app_text
