from contextlib import nullcontext
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app


class SessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


@pytest.fixture
def streamlit_harness(monkeypatch):
    calls = {
        "headers": [],
        "selectboxes": [],
        "text_inputs": [],
        "captions": [],
        "errors": [],
        "buttons": [],
        "button_values": {},
    }

    state = SessionState()

    def header(label):
        calls["headers"].append(label)

    def selectbox(label, options, key=None, **kwargs):
        options = list(options)
        calls["selectboxes"].append({"label": label, "options": options, "key": key})
        if key is not None and key not in state and options:
            state[key] = options[0]
        return state.get(key)

    def text_input(label, key=None, **kwargs):
        calls["text_inputs"].append({"label": label, "key": key, "kwargs": kwargs})
        if key is not None and key not in state:
            state[key] = ""
        return state.get(key, "")

    def caption(message):
        calls["captions"].append(message)

    def error(message):
        calls["errors"].append(message)

    def button(label, key=None, **kwargs):
        calls["buttons"].append({"label": label, "key": key})
        lookup_key = key or label
        return calls["button_values"].get(lookup_key, False)

    monkeypatch.setattr(app.st, "session_state", state, raising=False)
    monkeypatch.setattr(app.st, "sidebar", nullcontext(), raising=False)
    monkeypatch.setattr(app.st, "header", header, raising=False)
    monkeypatch.setattr(app.st, "selectbox", selectbox, raising=False)
    monkeypatch.setattr(app.st, "text_input", text_input, raising=False)
    monkeypatch.setattr(app.st, "caption", caption, raising=False)
    monkeypatch.setattr(app.st, "error", error, raising=False)
    monkeypatch.setattr(app.st, "button", button, raising=False)

    return state, calls
