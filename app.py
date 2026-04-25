import logging
import os
import re
import sys
from pathlib import Path

import google.generativeai as genai
import streamlit as st
from openai import OpenAI

from explainer.agent import analyze
from explainer.github import GithubRepositoryDataReader

logging.basicConfig(level=logging.INFO)

try:
    from toyaikit.chat.runners import RunnerCallback
    from toyaikit.llm import GeminiClient, GeminiVertexClient, OpenAIClient
except ModuleNotFoundError:
    local_toyaikit_root = Path(__file__).resolve().parent.parent / "toyaikit"
    if local_toyaikit_root.exists():
        sys.path.insert(0, str(local_toyaikit_root))
    from toyaikit.chat.runners import RunnerCallback
    from toyaikit.llm import GeminiClient, GeminiVertexClient, OpenAIClient


PROVIDER_MODELS = {
    "OpenAI": ["gpt-4o-mini", "gpt-4o"],
}

PROVIDERS = ["OpenAI", "Gemini", "Gemini Vertex"]


class StreamlitCallback(RunnerCallback):
    def __init__(self, status_container):
        self.status_container = status_container
        self.messages = []
    
    def on_function_call(self, function_call, result):
        func_name = function_call.name
        try:
            import json
            args = json.loads(function_call.arguments)
            args_str = ", ".join([f"{k}={repr(v)[:50]}..." if len(repr(v)) > 50 else f"{k}={repr(v)}" for k, v in args.items()])
        except Exception:
            args_str = str(function_call.arguments)[:100]
        
        msg = f"🔧 `{func_name}({args_str})`"
        self.messages.append(msg)
        self.status_container.markdown("\n\n".join(self.messages))
    
    def on_message(self, message):
        pass
    
    def on_reasoning(self, reasoning):
        if reasoning:
            msg = f"💭 *{reasoning}*"
            self.messages.append(msg)
            self.status_container.markdown("\n\n".join(self.messages))
    
    def on_response(self, response):
        pass


def parse_github_url(url: str):
    match = re.match(r'https://github\.com/([^/]+)/([^/]+)', url.strip())
    if match:
        return match.group(1), match.group(2)
    return None, None


def get_streamlit_secret(key: str, default=''):
    try:
        llm_section = st.secrets.get('llm', {})
        if key in llm_section:
            return llm_section[key]
        return st.secrets.get(key, default)
    except Exception:
        return default


@st.cache_data(show_spinner=False, ttl=3600)
def get_gemini_models(api_key: str) -> list[str]:
    if not api_key:
        return []

    genai.configure(api_key=api_key)
    models = []

    for model in genai.list_models():
        methods = getattr(model, 'supported_generation_methods', []) or []
        name = getattr(model, 'name', '')
        if 'generateContent' in methods and name.startswith('models/gemini'):
            models.append(name.replace('models/', '', 1))

    return sorted(set(models), reverse=True)


def load_gemini_models(api_key: str) -> tuple[list[str], str | None]:
    if not api_key:
        return [], None

    try:
        return get_gemini_models(api_key), None
    except Exception as exc:
        return [], str(exc)


def get_latest_pro_model(models: list[str]) -> str:
    pro_models = sorted(
        (model for model in models if 'pro' in model.lower()),
        key=lambda model: tuple(int(part) for part in re.findall(r'\d+', model)),
        reverse=True,
    )
    if pro_models:
        return pro_models[0]
    return models[0] if models else ''


import json

def save_chat(): Path('.private/chat.json').write_text(json.dumps(st.session_state.chat_history, default=str))
def load_chat():
    f = Path('.private/chat.json')
    return json.loads(f.read_text()) if f.exists() else []

def init_session_state():
    defaults = {
        'repo_files': None,
        'llm_client': None,
        'conversation_messages': None,
        'chat_history': load_chat(),
        'provider': get_streamlit_secret('provider', 'Gemini'),
        'openai_model': get_streamlit_secret('openai_model', PROVIDER_MODELS['OpenAI'][0]),
        'gemini_model': get_streamlit_secret('gemini_model', ''),
        'gemini_vertex_model': get_streamlit_secret('gemini_vertex_model', ''),
        'openai_api_key': get_streamlit_secret('OPENAI_API_KEY', os.getenv('OPENAI_API_KEY', '')),
        'gemini_api_key': get_streamlit_secret('GEMINI_API_KEY', os.getenv('GEMINI_API_KEY', '')),
        'gemini_vertex_project': get_streamlit_secret('GOOGLE_CLOUD_PROJECT', os.getenv('GOOGLE_CLOUD_PROJECT', '')),
        'gemini_vertex_location': get_streamlit_secret('GOOGLE_CLOUD_LOCATION', os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')),
        'active_llm_signature': None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_active_model() -> str:
    provider = st.session_state.provider
    if provider == 'OpenAI':
        return st.session_state.openai_model
    if provider == 'Gemini':
        return st.session_state.gemini_model
    return st.session_state.gemini_vertex_model


def get_llm_signature() -> tuple:
    provider = st.session_state.provider
    if provider == 'OpenAI':
        return (provider, st.session_state.openai_model)
    if provider == 'Gemini':
        return (provider, st.session_state.gemini_model)
    return (
        provider,
        st.session_state.gemini_vertex_model,
        st.session_state.gemini_vertex_project,
        st.session_state.gemini_vertex_location,
    )


def reset_conversation():
    st.session_state.conversation_messages = None
    st.session_state.chat_history = []
    save_chat()


def build_llm_client():
    provider = st.session_state.provider

    if provider == 'OpenAI':
        api_key = st.session_state.openai_api_key.strip()
        if not api_key:
            raise ValueError('OpenAI selected, but no API key was provided.')

        return OpenAIClient(
            model=st.session_state.openai_model,
            client=OpenAI(api_key=api_key),
        )

    if provider == 'Gemini':
        api_key = st.session_state.gemini_api_key.strip()
        if not api_key:
            raise ValueError('Gemini selected, but no API key was provided.')

        return GeminiClient(
            model=st.session_state.gemini_model,
            api_key=api_key,
        )

    project = st.session_state.gemini_vertex_project.strip()
    if not project:
        raise ValueError('Gemini Vertex selected, but no Google Cloud project was provided.')

    return GeminiVertexClient(
        model=st.session_state.gemini_vertex_model,
        project=project,
        location=st.session_state.gemini_vertex_location.strip() or 'us-central1',
    )


def render_llm_settings():
    with st.sidebar:
        st.header('LLM Settings')
        st.selectbox('Provider', PROVIDERS, key='provider')

        provider = st.session_state.provider

        if provider == 'OpenAI':
            st.selectbox('Model', PROVIDER_MODELS['OpenAI'], key='openai_model')
            st.text_input(
                'OpenAI API Key',
                key='openai_api_key',
                type='password',
                help='Used to create the OpenAI client for analysis requests.',
            )
        elif provider == 'Gemini':
            st.text_input(
                'Gemini API Key',
                key='gemini_api_key',
                type='password',
                help='Used for the direct Gemini API client.',
            )
            gemini_api_key = st.session_state.gemini_api_key.strip()
            gemini_models, gemini_error = load_gemini_models(gemini_api_key)
            latest_pro_model = get_latest_pro_model(gemini_models)
            if gemini_models:
                if st.session_state.gemini_model not in gemini_models:
                    st.session_state.gemini_model = latest_pro_model
                st.selectbox('Model', gemini_models, key='gemini_model')
            else:
                if gemini_error:
                    st.error(f'Failed to load Gemini models: {gemini_error}')
                elif gemini_api_key:
                    st.caption('No Gemini models were returned for the provided API key.')
                else:
                    st.caption('Provide a Gemini API key to load the available models.')
        else:
            st.text_input(
                'Gemini API Key',
                key='gemini_api_key',
                type='password',
                help='Used only to query the available Gemini models.',
            )
            st.text_input(
                'Google Cloud Project',
                key='gemini_vertex_project',
                help='Project ID for Vertex AI Gemini requests.',
            )
            st.text_input(
                'Vertex Location',
                key='gemini_vertex_location',
                help='Region for Vertex AI requests.',
            )
            gemini_api_key = st.session_state.gemini_api_key.strip()
            gemini_models, gemini_error = load_gemini_models(gemini_api_key)
            latest_pro_model = get_latest_pro_model(gemini_models)
            if gemini_models:
                if st.session_state.gemini_vertex_model not in gemini_models:
                    st.session_state.gemini_vertex_model = latest_pro_model
                st.selectbox('Model', gemini_models, key='gemini_vertex_model')
            else:
                if gemini_error:
                    st.error(f'Failed to load Gemini models: {gemini_error}')
                elif gemini_api_key:
                    st.caption('No Gemini models were returned for the provided API key.')
                else:
                    st.caption('Provide a Gemini API key to load the available models.')

        st.caption(f"Active provider: {provider} · model: {get_active_model()}")

        if st.button('Apply LLM Settings', use_container_width=True):
            new_signature = get_llm_signature()
            if st.session_state.active_llm_signature != new_signature:
                reset_conversation()
            st.session_state.llm_client = None
            st.session_state.active_llm_signature = new_signature
            st.success('LLM settings updated.')


def main():
    st.set_page_config(
        page_title="Code Analyzer",
        page_icon="🔍",
        layout="wide"
    )
    
    st.title("🔍 GitHub Repository Code Analyzer")

    init_session_state()
    render_llm_settings()
    
    if st.session_state.repo_files is None:
        github_url = st.text_input(
            "GitHub Repository URL",
            placeholder="https://github.com/alexeygrigorev/toyaikit"
        )
        
        if github_url:
            repo_owner, repo_name = parse_github_url(github_url)
            
            if repo_owner and repo_name:
                with st.spinner(f"Loading {repo_owner}/{repo_name}..."):
                    try:
                        reader = GithubRepositoryDataReader(
                            repo_owner=repo_owner,
                            repo_name=repo_name,
                            allowed_extensions=None
                        )
                        repo_files_list = reader.read()
                        st.session_state.repo_files = {f.filename: f.content for f in repo_files_list}
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
            else:
                st.error("Invalid GitHub URL format")
    else:
        col1, col2 = st.columns([4, 1])
        with col1:
            st.info(
                f"📁 Repository loaded: {len(st.session_state.repo_files)} files · "
                f"LLM: {st.session_state.provider} / {get_active_model()}"
            )
        with col2:
            if st.button("Reset"):
                st.session_state.repo_files = None
                reset_conversation()
                st.rerun()
        
        st.divider()
        
        question = st.text_area(
            "Ask a question about the codebase",
            value="How does this work?\n\nI need high level and low level analysis. And how does it compares with standard FOSS tools and corporate-grade tools.\n\nTabulate features.",
            height=150
        )
        
        col1, col2 = st.columns([1, 5])
        with col1:
            analyze_btn = st.button("🔍 Analyze", type="primary", use_container_width=True)
        with col2:
            if st.session_state.conversation_messages:
                if st.button("🆕 New Conversation"):
                    st.session_state.conversation_messages = None
                    st.session_state.chat_history = []
                    save_chat()
                    st.rerun()
        
        if analyze_btn and question:
            status_container = st.empty()
            
            with st.spinner("Analyzing..."):
                try:
                    current_signature = get_llm_signature()
                    if st.session_state.active_llm_signature != current_signature:
                        reset_conversation()
                    st.session_state.llm_client = build_llm_client()
                    st.session_state.active_llm_signature = current_signature

                    callback = StreamlitCallback(status_container)
                    
                    report = analyze(
                        question,
                        st.session_state.repo_files,
                        st.session_state.llm_client,
                        callback=callback,
                        previous_messages=st.session_state.conversation_messages
                    )
                    
                    st.session_state.conversation_messages = report.messages
                    st.session_state.chat_history.append({
                        'question': question,
                        'answer': report.answer,
                        'files': report.files_analyzed,
                        'tokens': report.tokens,
                        'cost': report.cost
                    })
                    save_chat()
                    
                    status_container.empty()
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Error: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())
        
        if st.session_state.chat_history:
            st.divider()
            
            for item in reversed(st.session_state.chat_history):
                with st.chat_message("user"):
                    st.markdown(item['question'])
                
                with st.chat_message("assistant"):
                    st.markdown(item['answer'])
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if item['files']:
                            with st.expander(f"📁 Files analyzed ({len(item['files'])})"):
                                for file in item['files']:
                                    st.text(f"  • {file}")
                    with col2:
                        if item.get('cost'):
                            cost = item['cost']
                            tokens = item.get('tokens')
                            with st.expander(f"💰 Cost: ${cost.total_cost:.4f}"):
                                if tokens:
                                    st.text(f"Input tokens: {tokens.input_tokens}")
                                    st.text(f"Output tokens: {tokens.output_tokens}")
                                st.text(f"Input cost: ${cost.input_cost:.4f}")
                                st.text(f"Output cost: ${cost.output_cost:.4f}")


if __name__ == "__main__":
    main()
