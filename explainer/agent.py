import re
from dataclasses import dataclass
from explainer.github import GithubRepositoryDataReader


@dataclass
class AnalysisReport:
    """
    Container for code analysis results.
    
    Attributes:
        answer: The AI-generated answer to the analysis question
        files_analyzed: List of file paths that were examined during analysis
        messages: All conversation messages for continuing the chat
    """
    answer: str
    files_analyzed: list[str]
    messages: list = None


class FileTools:
    """
    Tools for reading and searching files in a repository.
    
    This class provides file access and grep functionality for code analysis.
    All analyzed files are automatically tracked.
    
    Attributes:
        repo_files: Dictionary mapping file paths to their contents
        files_analyzed: Set of file paths that have been accessed
    """
    
    def __init__(self, repo_files: dict[str, str]):
        """
        Initialize FileTools with repository files.
        
        Args:
            repo_files: Dictionary mapping file paths to file contents
        """
        self.repo_files = repo_files
        self.files_analyzed = set()
    
    def read_file(self, file_path: str) -> str:
        """
        Read the complete contents of a file in the repository.
        
        This method retrieves the full text content of a specified file and
        automatically tracks it in the files_analyzed set.
        
        Args:
            file_path: The relative path to the file within the repository
                      (e.g., 'src/main.py' or 'README.md')
        
        Returns:
            str: The complete file contents as a string, or an error message
                if the file is not found. Error messages include a sample of
                available files to help with discovery.
        
        Example:
            >>> tools = FileTools(repo_files)
            >>> content = tools.read_file('src/utils.py')
            >>> print(content)
            import os
            def helper():
                ...
        """
        if file_path not in self.repo_files:
            available = list(self.repo_files.keys())[:10]
            return f"Error: File {file_path} not found. Available files: {', '.join(available)}..."
        
        self.files_analyzed.add(file_path)
        return self.repo_files[file_path]
    
    def list_files(self, directory: str = "") -> str:
        """
        List files and directories in a specified folder.
        
        This method shows only the immediate contents (files and subdirectories)
        of the specified directory, without recursing into subdirectories.
        Useful for exploring the repository structure step by step.
        
        Args:
            directory: The directory path to list. Use empty string "" or omit
                      for the root directory. Can be specified with or without
                      trailing slash (e.g., 'src' or 'src/' both work).
                      Examples: '', 'src', 'docs/', 'lib/utils'
        
        Returns:
            str: Formatted listing showing:
                - Directory path being listed
                - Subdirectories (marked with trailing /)
                - Files in that directory
                - Count of items found
                
                Returns error message if directory doesn't exist.
        
        Example:
            >>> tools = FileTools(repo_files)
            >>> # List root directory
            >>> print(tools.list_files())
            Directory: /
            
            Directories:
              src/
              docs/
              tests/
            
            Files:
              README.md
              setup.py
              .gitignore
            
            Total: 6 items (3 directories, 3 files)
            
            >>> # List specific directory
            >>> print(tools.list_files('src'))
            Directory: src/
            
            Directories:
              utils/
              models/
            
            Files:
              __init__.py
              main.py
              config.py
            
            Total: 5 items (2 directories, 3 files)
            
            >>> # List nested directory
            >>> print(tools.list_files('src/utils'))
            Directory: src/utils/
            
            Files:
              __init__.py
              helpers.py
              validators.py
            
            Total: 3 items (0 directories, 3 files)
        
        Notes:
            - Only shows immediate children, not recursive contents
            - Directories are always shown with trailing slash
            - Items are sorted alphabetically within their category
            - Does not track files as analyzed (use read_file for that)
        """
        # Normalize directory path
        dir_path = directory.rstrip('/') if directory else ""
        
        # Build prefix for matching
        if dir_path:
            prefix = dir_path + '/'
        else:
            prefix = ""
        
        files_in_dir = []
        subdirs = set()
        
        for filepath in self.repo_files.keys():
            # Check if file is in this directory
            if filepath.startswith(prefix):
                # Get the relative path from this directory
                relative = filepath[len(prefix):]
                
                # Check if it's a direct child (no more slashes) or in a subdirectory
                if '/' in relative:
                    # It's in a subdirectory
                    subdir = relative.split('/')[0]
                    subdirs.add(subdir)
                else:
                    # It's a direct file
                    files_in_dir.append(relative)
        
        if not files_in_dir and not subdirs:
            # Check if directory exists at all
            dir_exists = any(
                fp.startswith(prefix) or (not prefix and True)
                for fp in self.repo_files.keys()
            )
            if not dir_exists and dir_path:
                available_dirs = self._get_available_directories()[:10]
                return f"Error: Directory '{dir_path}' not found. Available directories: {', '.join(available_dirs)}..."
            
        # Format output
        display_path = dir_path + '/' if dir_path else '/'
        result = [f"Directory: {display_path}\n"]
        
        # List subdirectories
        if subdirs:
            result.append("Directories:")
            for subdir in sorted(subdirs):
                result.append(f"  {subdir}/")
            result.append("")
        
        # List files
        if files_in_dir:
            result.append("Files:")
            for file in sorted(files_in_dir):
                result.append(f"  {file}")
            result.append("")
        
        # Summary
        total = len(subdirs) + len(files_in_dir)
        result.append(f"Total: {total} items ({len(subdirs)} directories, {len(files_in_dir)} files)")
        
        return '\n'.join(result)
    
    def _get_available_directories(self) -> list[str]:
        """Get a list of all available directories in the repository."""
        dirs = set()
        for filepath in self.repo_files.keys():
            parts = filepath.split('/')
            for i in range(len(parts) - 1):
                dir_path = '/'.join(parts[:i+1])
                dirs.add(dir_path)
        return sorted(dirs)
    
    def grep(self, pattern: str, file_path: str = None, context_lines: int = 3) -> str:
        """
        Search for a regex pattern across repository files with context.
        
        This method performs a case-insensitive regular expression search across
        repository files and returns matching lines with surrounding context.
        Results include file paths, line numbers, and highlighted match lines.
        
        Args:
            pattern: Regular expression pattern to search for. Supports full
                    Python regex syntax (e.g., 'class\\s+\\w+', 'def.*init',
                    'import.*requests'). Special regex characters should be
                    escaped with backslashes.
            
            file_path: Optional specific file to search within. If None, searches
                      across all files in the repository. Must be a valid path
                      from repo_files keys.
            
            context_lines: Number of lines to show before and after each match
                          for context. Default is 3. Set to 0 for matches only.
        
        Returns:
            str: Formatted search results with the following structure:
                - File path header for each file with matches
                - Line numbers prefixed with '>' for match lines, ' ' for context
                - Line content with original formatting preserved
                
                Returns "No matches found for pattern: <pattern>" if no matches exist.
                Returns error message if regex pattern is invalid.
        
        Raises:
            No exceptions are raised; errors are returned as formatted strings.
        
        Example:
            >>> tools = FileTools(repo_files)
            >>> results = tools.grep(r'class\\s+\\w+Agent', context_lines=2)
            >>> print(results)
            
            src/agent.py:
              10: from dataclasses import dataclass
              11: 
            > 12: class CodeAnalysisAgent:
              13:     def __init__(self):
              14:         self.tools = []
            
            >>> results = tools.grep('def analyze', file_path='src/agent.py', context_lines=1)
            >>> print(results)
            
            src/agent.py:
              24:     
            > 25:     def analyze(self, question: str):
              26:         return self.llm.query(question)
        
        Notes:
            - Search is case-insensitive by default
            - All files containing matches are automatically added to files_analyzed
            - Pattern matching uses Python's re.compile() with re.IGNORECASE flag
            - Context lines are clamped to valid line ranges (won't exceed file bounds)
        """
        try:
            regex = re.compile(pattern, re.IGNORECASE)
            results = []
            
            # Determine which files to search
            files_to_search = {file_path: self.repo_files[file_path]} if file_path else self.repo_files
            
            for filepath, content in files_to_search.items():
                lines = content.split('\n')
                matches = []
                
                # Find all matching line numbers
                for i, line in enumerate(lines, 1):
                    if regex.search(line):
                        matches.append(i)
                
                if matches:
                    self.files_analyzed.add(filepath)
                    
                    # For each match, add context lines
                    for match_line in matches:
                        start = max(1, match_line - context_lines)
                        end = min(len(lines), match_line + context_lines)
                        
                        results.append(f"\n{filepath}:")
                        for line_num in range(start, end + 1):
                            prefix = ">" if line_num == match_line else " "
                            results.append(f"{prefix} {line_num}: {lines[line_num - 1]}")
            
            if not results:
                return f"No matches found for pattern: {pattern}"
            
            return '\n'.join(results)
            
        except re.error as e:
            return f"Invalid regex pattern: {e}"
        except Exception as e:
            return f"Error during grep: {str(e)}"


def analyze(question: str, repo_files: dict[str, str], llm_client, developer_prompt: str = None, callback = None, previous_messages: list = None) -> AnalysisReport:
    """
    Analyze a codebase to answer questions using AI and file tools.
    
    This function creates a FileTools instance, configures an AI agent with file
    access capabilities, and processes a natural language question about the codebase.
    The AI can read files and search for patterns to understand the code structure.
    
    Args:
        question: Natural language question about the codebase. Examples:
                 - "How do agents communicate with each other?"
                 - "What design patterns are used in this project?"
                 - "How does the authentication system work?"
        
        repo_files: Dictionary mapping file paths to their contents. Should contain
                   all relevant source files from the repository.
        
        llm_client: LLM client instance (e.g., OpenAIClient) that implements
                   send_request() method compatible with toyaikit responses API.
        
        developer_prompt: Optional custom system prompt for the AI. If None, uses
                         a default prompt that instructs the AI to use file tools
                         for thorough code analysis. Custom prompts should describe
                         available tools and analysis methodology.
        
        callback: Optional RunnerCallback instance to receive real-time updates
                 about function calls, messages, and reasoning during analysis.
                 Useful for displaying progress in interactive applications.
        
        previous_messages: Optional list of previous conversation messages to maintain
                          context across multiple questions. Allows for follow-up questions
                          and conversational interactions.
    
    Returns:
        AnalysisReport: Contains three fields:
            - answer: The AI's detailed response to the question
            - files_analyzed: Sorted list of file paths that were examined
            - messages: All messages from this conversation turn (for continuing chat)
    
    Example:
        >>> from toyaikit.llm import OpenAIClient
        >>> from explainer.github import GithubRepositoryDataReader
        >>> 
        >>> reader = GithubRepositoryDataReader("owner", "repo", allowed_extensions=["py"])
        >>> files = {f.filename: f.content for f in reader.read()}
        >>> client = OpenAIClient(model="gpt-4o-mini")
        >>> 
        >>> # First question
        >>> report = analyze(
        ...     question="How does error handling work in this codebase?",
        ...     repo_files=files,
        ...     llm_client=client
        ... )
        >>> print(report.answer)
        >>> 
        >>> # Follow-up question using previous messages
        >>> report2 = analyze(
        ...     question="Can you show me an example?",
        ...     repo_files=files,
        ...     llm_client=client,
        ...     previous_messages=report.messages
        ... )
    
    Notes:
        - The AI has access to read_file(), grep(), and list_files() tools
        - Analysis is thorough: the AI explores multiple files to build understanding
        - File tracking is automatic: all accessed files appear in files_analyzed
        - Uses OpenAI Responses API format via toyaikit.chat.runners.OpenAIResponsesRunner
        - Supports conversational context via previous_messages parameter
    """
    from toyaikit.tools import Tools
    from toyaikit.chat.runners import OpenAIResponsesRunner
    
    file_tools = FileTools(repo_files)
    
    tools = Tools()
    tools.add_tools(file_tools)
    
    if developer_prompt is None:
        # Get top-level directory listing
        root_listing = file_tools.list_files("")
        
        developer_prompt = f"""You are a code analysis assistant. Your task is to analyze a GitHub repository and answer questions about the codebase with DEEP, THOROUGH technical details.

You have access to the following tools:
- list_files(directory: str = ""): List files and directories in a folder. Use "" for root, or specify a path like "src" or "docs/"
- read_file(file_path: str): Read the complete contents of a file
- grep(pattern: str, file_path: str = None, context_lines: int = 3): Search for patterns in files with context

Repository structure (top level):
{root_listing}

CRITICAL ANALYSIS REQUIREMENTS:
1. BE EXTREMELY THOROUGH - superficial answers are NOT acceptable
2. READ THE ACTUAL SOURCE CODE - don't make assumptions
3. Trace through FULL execution paths showing exactly how code works
4. Include SPECIFIC implementation details:
   - Exact class/function names with line references
   - Data structures and their transformations
   - Control flow and logic paths
   - Important variables and their roles
5. Show the COMPLETE picture of how components interact
6. Use grep extensively to find all related code
7. Read multiple related files to understand the full context

ANALYSIS WORKFLOW (MANDATORY):
1. Use list_files() to explore directory structure
2. Use grep() to find ALL relevant classes, functions, and patterns
3. Read ALL files that are involved in the feature/functionality
4. Trace the execution flow step by step with code references
5. Explain internal mechanisms with technical precision
6. Provide code snippets showing key implementation details

Your answer MUST include:
- Specific file paths and line numbers
- Actual code snippets from the repository
- Detailed explanation of internal implementation
- Step-by-step execution flow
- How data flows through the system

DO NOT provide generic or high-level explanations. The user wants DEEP technical analysis with specific implementation details."""
    
    runner = OpenAIResponsesRunner(
        tools=tools,
        developer_prompt=developer_prompt,
        llm_client=llm_client
    )
    
    messages = runner.loop(
        prompt=question,
        previous_messages=previous_messages,
        callback=callback
    )
    
    # Extract the final answer from messages
    final_answer = ""
    for msg in reversed(messages):
        # Handle both dict and object responses
        if hasattr(msg, 'get'):
            # It's a dict
            if msg.get("type") == "message":
                content = msg.get("content", [])
                if content and len(content) > 0:
                    if isinstance(content[0], dict):
                        final_answer = content[0].get("text", "")
                    else:
                        final_answer = content[0].text if hasattr(content[0], 'text') else str(content[0])
                    break
        elif hasattr(msg, 'type'):
            # It's an object (ResponseOutputMessage)
            if msg.type == "message":
                content = msg.content if hasattr(msg, 'content') else []
                if content and len(content) > 0:
                    # Handle ResponseOutputText objects
                    if hasattr(content[0], 'text'):
                        final_answer = content[0].text
                    elif isinstance(content[0], dict):
                        final_answer = content[0].get("text", "")
                    else:
                        final_answer = str(content[0])
                    break
    
    return AnalysisReport(
        answer=final_answer,
        files_analyzed=sorted(list(file_tools.files_analyzed)),
        messages=messages
    )


def load_github_repo(repo_owner: str, repo_name: str, allowed_extensions: list[str] = None) -> dict[str, str]:
    """
    Download and load files from a GitHub repository.
    
    This is a convenience function that wraps GithubRepositoryDataReader to
    download a repository and convert it to the dict format needed by analyze().
    
    Args:
        repo_owner: GitHub username or organization (e.g., 'microsoft', 'openai')
        repo_name: Repository name (e.g., 'vscode', 'openai-python')
        allowed_extensions: Optional list of file extensions to include
                           (e.g., ['py', 'js', 'ts']). If None, includes all files.
    
    Returns:
        dict[str, str]: Dictionary mapping file paths to their contents
    
    Example:
        >>> repo_files = load_github_repo('psf', 'requests', allowed_extensions=['py'])
        >>> print(f"Loaded {len(repo_files)} Python files")
        >>> 
        >>> from toyaikit.llm import OpenAIClient
        >>> report = analyze("How does session management work?", repo_files, OpenAIClient())
    """
    reader = GithubRepositoryDataReader(
        repo_owner=repo_owner,
        repo_name=repo_name,
        allowed_extensions=allowed_extensions
    )
    repo_files_list = reader.read()
    return {f.filename: f.content for f in repo_files_list}

