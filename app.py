import streamlit as st
from explainer.agent import analyze
from explainer.github import GithubRepositoryDataReader
from toyaikit.llm import OpenAIClient, GeminiClient, GeminiVertexClient
from toyaikit.chat.runners import RunnerCallback
import re


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


def main():
    st.set_page_config(
        page_title="Code Analyzer",
        page_icon="🔍",
        layout="wide"
    )
    
    st.title("🔍 GitHub Repository Code Analyzer")
    
    if 'repo_files' not in st.session_state:
        st.session_state.repo_files = None
    if 'llm_client' not in st.session_state:
        st.session_state.llm_client = None
    if 'conversation_messages' not in st.session_state:
        st.session_state.conversation_messages = None
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    
    if st.session_state.repo_files is None:
        col1, col2 = st.columns([1, 1])
        with col1:
            provider = st.selectbox("LLM Provider", ["OpenAI", "Gemini", "Gemini Vertex"], key="provider")
        with col2:
            if provider == "OpenAI":
                model_name = st.selectbox("Model", ["gpt-4o-mini", "gpt-4o"], key="model_openai")
            else:
                model_name = st.selectbox("Model", ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash"], key="model_gemini")
        
        github_url = st.text_input(
            "GitHub Repository URL",
            placeholder="https://github.com/alexeygrigorev/toyaikit"
        )
        
        if github_url:
            repo_owner, repo_name = parse_github_url(github_url)
            
            if repo_owner and repo_name:
                with st.spinner(f"Loading {repo_owner}/{repo_name}..."):
                    try:
                        # Initialize LLM Client based on selection
                        if provider == "OpenAI":
                            st.session_state.llm_client = OpenAIClient(model=model_name)
                        elif provider == "Gemini":
                            st.session_state.llm_client = GeminiClient(
                                model=model_name, 
                                api_key="AIzaSyCuJ1da65C-NOkxyy6xmiJHvqxbaY28ORk"
                            )
                        elif provider == "Gemini Vertex":
                            st.session_state.llm_client = GeminiVertexClient(
                                model=model_name,
                                project="autonomia-489716"
                            )

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
            st.info(f"📁 Repository loaded: {len(st.session_state.repo_files)} files")
        with col2:
            if st.button("Reset"):
                st.session_state.repo_files = None
                st.session_state.conversation_messages = None
                st.session_state.chat_history = []
                st.rerun()
        
        st.divider()
        
        question = st.text_area(
            "Ask a question about the codebase",
            placeholder="How does this work?",
            height=100
        )
        
        col1, col2 = st.columns([1, 5])
        with col1:
            analyze_btn = st.button("🔍 Analyze", type="primary", use_container_width=True)
        with col2:
            if st.session_state.conversation_messages:
                if st.button("🆕 New Conversation"):
                    st.session_state.conversation_messages = None
                    st.session_state.chat_history = []
                    st.rerun()
        
        if analyze_btn and question:
            status_container = st.empty()
            
            with st.spinner("Analyzing..."):
                try:
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
