import app


def test_init_session_state_loads_defaults_from_secrets(monkeypatch, streamlit_harness):
    state, _ = streamlit_harness

    monkeypatch.setattr(
        app.st,
        "secrets",
        {
            "llm": {
                "provider": "Gemini",
                "gemini_model": "gemini-2.5-pro",
                "GEMINI_API_KEY": "secret-gemini-key",
                "GOOGLE_CLOUD_PROJECT": "demo-project",
            }
        },
        raising=False,
    )
    monkeypatch.setattr(app.os, "getenv", lambda key, default="": default)

    app.init_session_state()

    assert state.provider == "Gemini"
    assert state.gemini_model == "gemini-2.5-pro"
    assert state.gemini_api_key == "secret-gemini-key"
    assert state.gemini_vertex_project == "demo-project"
