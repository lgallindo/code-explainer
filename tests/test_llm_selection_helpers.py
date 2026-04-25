from types import SimpleNamespace

import app


def test_get_streamlit_secret_prefers_llm_section(monkeypatch):
    monkeypatch.setattr(
        app.st,
        "secrets",
        {
            "llm": {"GEMINI_API_KEY": "nested-key"},
            "GEMINI_API_KEY": "top-level-key",
        },
        raising=False,
    )

    assert app.get_streamlit_secret("GEMINI_API_KEY", "fallback") == "nested-key"


def test_get_gemini_models_filters_and_normalizes(monkeypatch):
    configured = {}

    def fake_configure(*, api_key):
        configured["api_key"] = api_key

    models = [
        SimpleNamespace(
            name="models/gemini-2.5-pro",
            supported_generation_methods=["generateContent"],
        ),
        SimpleNamespace(
            name="models/gemini-2.5-flash",
            supported_generation_methods=["generateContent"],
        ),
        SimpleNamespace(
            name="models/text-embedding-004",
            supported_generation_methods=["embedContent"],
        ),
        SimpleNamespace(
            name="models/gemini-1.5-pro",
            supported_generation_methods=[],
        ),
    ]

    monkeypatch.setattr(app.genai, "configure", fake_configure)
    monkeypatch.setattr(app.genai, "list_models", lambda: models)

    app.get_gemini_models.clear()
    result = app.get_gemini_models("secret-key")

    assert configured["api_key"] == "secret-key"
    assert result == ["gemini-2.5-pro", "gemini-2.5-flash"]


def test_get_latest_pro_model_picks_highest_ranked_pro():
    models = ["gemini-1.5-pro", "gemini-2.0-flash", "gemini-2.5-pro"]

    assert app.get_latest_pro_model(models) == "gemini-2.5-pro"


def test_load_gemini_models_returns_error_message(monkeypatch):
    monkeypatch.setattr(app, "get_gemini_models", lambda api_key: (_ for _ in ()).throw(Exception("403 PermissionDenied")))

    models, error = app.load_gemini_models("bad-key")

    assert models == []
    assert error == "403 PermissionDenied"
