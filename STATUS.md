# Project Status - April 24, 2026

## 1. Git Remote Migration
- **Original Origin**: `https://github.com/alexeygrigorev/code-explainer.git`
- **Current Origin**: `https://github.com/lgallindo/code-explainer.git`
- **Current Branch**: `feat/gemini-support` (all changes pushed upstream)

## 2. Implemented Features
- **LLM Provider Switching**: [app.py](app.py) now supports a dynamic UI to select between OpenAI, Gemini, and Gemini Vertex.
- **Change Policy**: Use minimal, targeted edits only. Anything beyond the requested scope should be proposed first.
- **Patch Approval Policy**: Do not apply patches over 10 lines without explicit approval. Show before/after code first for larger edits.
- **Dependency Policy**: Do not edit [pyproject.toml](pyproject.toml) directly. Use package manager commands such as `uv add`, `uv remove`, `poetry add`, or `poetry remove`.
- **Tooling Policy**: Do not use the Pylance MCP route.
- **Provider Credentials UI**:
    - OpenAI uses a password input in Streamlit and builds the client with the provided API key.
    - Gemini uses a password input in Streamlit and builds the client with the provided API key.
    - Gemini Vertex uses Streamlit inputs for project and location.
- **Gemini Support**:
    - `GeminiClient` is available through the provider selector.
    - `GeminiVertexClient` is available through the provider selector.
    - Gemini model lists are fetched from the Gemini API instead of using hardcoded guesses.
    - The app auto-selects the latest available Pro model when the current selection is missing.
- **Local toyaikit Integration**: Project linked to local source at `/Users/lucasgallindo/Desktop/toyaikit` via editable install.
- **Dependencies**: Installed `google-generativeai` and `google-cloud-aiplatform` in the `.venv`.

## 3. How to Run
```bash
source .venv/bin/activate
streamlit run app.py
```

## 4. Pending Items
- [ ] Verify tool calling (read_file, grep, etc.) works correctly with the Gemini response format.
- [ ] Update cost tracking logic in `toyaikit` for Gemini models.
- [ ] Monitor and tune prompts for Gemini-specific performance.
- [ ] Consider migrating from deprecated `google.generativeai` to `google.genai` in `toyaikit`.

## 5. Workflow Documentation
- Current provider/key/model selection behavior is documented in [docs/llm-selection-workflow.md](docs/llm-selection-workflow.md).
- Use that document as the baseline for upcoming automated tests before refactoring the workflow.
