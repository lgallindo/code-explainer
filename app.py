import streamlit as st
from explainer.agent import load_github_repo, analyze
from toyaikit.llm import OpenAIClient
from toyaikit.chat.runners import RunnerCallback
import time


class StreamlitCallback(RunnerCallback):
    """Callback to display analysis progress in Streamlit."""
    
    def __init__(self, status_container):
        self.status_container = status_container
        self.messages = []
    
    def on_function_call(self, function_call, result):
        """Display function calls as they happen."""
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
        """Display AI messages."""
        pass
    
    def on_reasoning(self, reasoning):
        """Display reasoning if available."""
        if reasoning:
            msg = f"💭 *{reasoning}*"
            self.messages.append(msg)
            self.status_container.markdown("\n\n".join(self.messages))
    
    def on_response(self, response):
        """Handle response callback."""
        pass


def main():
    st.set_page_config(
        page_title="Code Analyzer",
        page_icon="🔍",
        layout="wide"
    )
    
    st.title("🔍 GitHub Repository Code Analyzer")
    st.markdown("Analyze code repositories with AI-powered tools")
    
    # Initialize session state
    if 'repo_files' not in st.session_state:
        st.session_state.repo_files = None
    if 'llm_client' not in st.session_state:
        st.session_state.llm_client = None
    if 'conversation_messages' not in st.session_state:
        st.session_state.conversation_messages = None
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    
    # Sidebar for repository setup
    with st.sidebar:
        st.header("📦 Repository Setup")
        
        repo_owner = st.text_input("Repository Owner", placeholder="e.g., openai")
        repo_name = st.text_input("Repository Name", placeholder="e.g., openai-python")
        
        extensions_input = st.text_input(
            "File Extensions (comma-separated)",
            value="py,js,ts,jsx,tsx,java,go,rs,cpp,c,h"
        )
        
        model = st.selectbox(
            "OpenAI Model",
            ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"],
            index=0
        )
        
        if st.button("Load Repository", type="primary"):
            if not repo_owner or not repo_name:
                st.error("Please enter both repository owner and name")
            else:
                with st.spinner(f"Downloading {repo_owner}/{repo_name}..."):
                    try:
                        allowed_extensions = [ext.strip() for ext in extensions_input.split(',')]
                        st.session_state.repo_files = load_github_repo(
                            repo_owner=repo_owner,
                            repo_name=repo_name,
                            allowed_extensions=allowed_extensions
                        )
                        st.session_state.llm_client = OpenAIClient(model=model)
                        st.session_state.conversation_messages = None
                        st.session_state.chat_history = []
                        st.success(f"✅ Loaded {len(st.session_state.repo_files)} files")
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
        
        # Show repository stats if loaded
        if st.session_state.repo_files:
            st.divider()
            st.subheader("📊 Repository Stats")
            st.metric("Total Files", len(st.session_state.repo_files))
            
            # File extension breakdown
            extensions = {}
            for filename in st.session_state.repo_files.keys():
                ext = filename.split('.')[-1] if '.' in filename else 'no-ext'
                extensions[ext] = extensions.get(ext, 0) + 1
            
            with st.expander("File Types"):
                for ext, count in sorted(extensions.items(), key=lambda x: x[1], reverse=True)[:10]:
                    st.text(f"{ext}: {count}")
        
        # Conversation controls
        if st.session_state.repo_files:
            st.divider()
            st.subheader("💬 Conversation")
            
            if st.session_state.conversation_messages:
                st.info(f"🔗 Continuing conversation ({len(st.session_state.chat_history)} messages)")
                if st.button("🆕 Start New Chat"):
                    st.session_state.conversation_messages = None
                    st.session_state.chat_history = []
                    st.rerun()
            else:
                st.info("💭 New conversation")
    
    # Main content area
    if not st.session_state.repo_files:
        st.info("👈 Please load a repository from the sidebar to begin")
    else:
        # Question input
        st.subheader("❓ Ask a Question")
        
        question = st.text_area(
            "Enter your question about the codebase",
            placeholder="Examples:\n- How do agents communicate with each other?\n- What design patterns are used?\n- Can you show me an example? (follow-up)",
            height=150,
            key="question_input"
        )
        
        col1, col2 = st.columns([1, 5])
        with col1:
            analyze_btn = st.button("🔍 Analyze", type="primary", use_container_width=True)
        
        if analyze_btn and question:
            # Create containers for status and result
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
                    
                    # Update conversation messages for next turn
                    st.session_state.conversation_messages = report.messages
                    
                    # Add to chat history
                    st.session_state.chat_history.append({
                        'question': question,
                        'answer': report.answer,
                        'files': report.files_analyzed,
                        'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
                    })
                    
                    # Clear status
                    status_container.empty()
                    
                    # Clear question input
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())
        
        # Display chat history
        if st.session_state.chat_history:
            st.divider()
            st.subheader("💬 Chat History")
            
            for idx, item in enumerate(reversed(st.session_state.chat_history)):
                with st.container():
                    st.markdown(f"**🕒 {item['timestamp']}**")
                    
                    # Question
                    with st.chat_message("user"):
                        st.markdown(item['question'])
                    
                    # Answer
                    with st.chat_message("assistant"):
                        st.markdown(item['answer'])
                        
                        if item['files']:
                            with st.expander(f"📁 Files Analyzed ({len(item['files'])})"):
                                for file in item['files']:
                                    st.text(f"  • {file}")
                    
                    if idx < len(st.session_state.chat_history) - 1:
                        st.divider()


if __name__ == "__main__":
    main()
