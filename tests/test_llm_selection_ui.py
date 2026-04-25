import app
from streamlit.testing.v1 import AppTest


def test_render_llm_settings_with_secrets_loaded_gemini_key_shows_model_dropdown(
    monkeypatch, streamlit_harness
):
    state, calls = streamlit_harness
    state.provider = "Gemini"
    state.gemini_api_key = "secret-key"
    state.gemini_model = ""

    monkeypatch.setattr(app, "get_gemini_models", lambda api_key: ["gemini-2.5-pro", "gemini-2.0-flash"])

    app.render_llm_settings()

    model_selectboxes = [item for item in calls["selectboxes"] if item["key"] == "gemini_model"]
    assert model_selectboxes
    assert state.gemini_model == "gemini-2.5-pro"


def test_render_llm_settings_without_gemini_key_shows_no_model_dropdown(
    monkeypatch, streamlit_harness
):
    state, calls = streamlit_harness
    state.provider = "Gemini"
    state.gemini_api_key = ""
    state.gemini_model = ""

    monkeypatch.setattr(app, "get_gemini_models", lambda api_key: [])

    app.render_llm_settings()

    model_selectboxes = [item for item in calls["selectboxes"] if item["key"] == "gemini_model"]
    assert model_selectboxes == []
    assert "Provide a Gemini API key to load the available models." in calls["captions"]


def test_render_llm_settings_auto_selects_latest_pro_when_current_missing(
    monkeypatch, streamlit_harness
):
    state, calls = streamlit_harness
    state.provider = "Gemini"
    state.gemini_api_key = "secret-key"
    state.gemini_model = "gemini-1.0-pro"

    monkeypatch.setattr(app, "get_gemini_models", lambda api_key: ["gemini-2.5-pro", "gemini-2.0-flash"])

    app.render_llm_settings()

    assert any(item["key"] == "gemini_model" for item in calls["selectboxes"])
    assert state.gemini_model == "gemini-2.5-pro"


def test_render_llm_settings_shows_gemini_api_error(monkeypatch, streamlit_harness):
    state, calls = streamlit_harness
    state.provider = "Gemini"
    state.gemini_api_key = "bad-key"
    state.gemini_model = ""

    monkeypatch.setattr(app, "load_gemini_models", lambda api_key: ([], "403 PermissionDenied: leaked key"))

    app.render_llm_settings()

    assert calls["errors"] == ["Failed to load Gemini models: 403 PermissionDenied: leaked key"]


def test_streamlit_interface_allows_typing_gemini_key_and_selecting_model():
    test_script = """
import app

app.get_gemini_models = lambda api_key: [
    \"gemini-2.5-pro\",
    \"gemini-2.0-flash\",
] if api_key == \"typed-key\" else []

app.main()
"""

    at = AppTest.from_string(test_script)
    at.run()

    assert at.selectbox(key="provider").value == "Gemini"
    assert len([widget for widget in at.selectbox if widget.key == "gemini_model"]) == 0

    at.text_input(key="gemini_api_key").set_value("typed-key")
    at.run()

    assert at.selectbox(key="gemini_model").value == "gemini-2.5-pro"

    at.selectbox(key="gemini_model").select("gemini-2.0-flash")
    at.run()

    assert at.selectbox(key="gemini_model").value == "gemini-2.0-flash"
