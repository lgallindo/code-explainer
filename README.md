# Code Explainer

AI-powered GitHub repository analyzer that provides deep, thorough technical analysis of codebases.

## Features

- 🔍 Deep code analysis using AI
- 📁 Automatic file exploration and pattern matching
- 💬 Conversational interface for follow-up questions
- 💰 Cost tracking for API usage
- 🔧 File reading, grepping, and directory listing tools

## Installation

This project uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
# Install dependencies
uv sync
```

## Usage

### Running the Streamlit App

```bash
uv run streamlit run app.py
```

1. Enter a GitHub repository URL (e.g., `https://github.com/alexeygrigorev/toyaikit`)
2. Wait for the repository to load
3. Ask questions about the codebase
4. Continue the conversation or reset to start fresh

### Programmatic Usage

```python
from explainer.agent import analyze, load_github_repo
from toyaikit.llm import OpenAIClient

# Load repository
repo_files = load_github_repo('alexeygrigorev', 'toyaikit')

# Initialize LLM client
client = OpenAIClient(model='gpt-4o-mini')

# Analyze
report = analyze(
    question="How does the runner.loop work?",
    repo_files=repo_files,
    llm_client=client
)

print(report.answer)
print(f"Files analyzed: {report.files_analyzed}")
print(f"Cost: ${report.cost.total_cost:.4f}")

# Follow-up question
report2 = analyze(
    question="Can you show me an example?",
    repo_files=repo_files,
    llm_client=client,
    previous_messages=report.messages
)
```

## Environment Variables

Set your OpenAI API key:

```bash
export OPENAI_API_KEY=your-api-key-here
```

## Project Structure

```
code-explainer/
├── explainer/
│   ├── agent.py          # Core analysis engine with FileTools
│   └── github.py         # GitHub repository loader
├── app.py                # Streamlit web interface
└── pyproject.toml        # uv dependencies
```

## How It Works

The analyzer uses an AI agent with specialized tools:

- **list_files()**: Explore directory structure
- **read_file()**: Read complete file contents
- **grep()**: Search for patterns with context

The AI performs thorough analysis by:
1. Exploring the repository structure
2. Searching for relevant code patterns
3. Reading multiple files to understand context
4. Tracing execution flows with specific line references
5. Providing detailed technical explanations
