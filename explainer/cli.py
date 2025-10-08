from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from explainer.agent import load_github_repo, analyze
from toyaikit.llm import OpenAIClient
from toyaikit.chat.runners import RunnerCallback


class RichDisplayCallback(RunnerCallback):
    """Callback to display analysis progress in rich console."""
    
    def __init__(self, console: Console):
        self.console = console
    
    def on_function_call(self, function_call, result):
        """Display function calls as they happen."""
        func_name = function_call.name
        try:
            import json
            args = json.loads(function_call.arguments)
            args_str = ", ".join([f"{k}={repr(v)}" for k, v in args.items()])
        except:
            args_str = function_call.arguments
        
        self.console.print(f"[dim]🔧 {func_name}({args_str})[/dim]")
    
    def on_message(self, message):
        """Display AI messages - not used here since we show final result."""
        pass
    
    def on_reasoning(self, reasoning):
        """Display reasoning if available."""
        if reasoning:
            self.console.print(f"[dim italic]💭 {reasoning}[/dim italic]")
    
    def on_response(self, response):
        """Handle response callback."""
        pass


class InteractiveCLI:
    def __init__(self):
        self.console = Console()
        self.repo_files = None
        self.llm_client = None
        self.last_files_analyzed = []
        
    def print_banner(self):
        banner = """
   ___          _        _____            _       _                 
  / __\___   __| | ___  /__   \_ __ __ _ (_)_ __ (_)_ __   __ _     
 / /  / _ \ / _` |/ _ \   / /\/ '__/ _` || | '_ \| | '_ \ / _` |    
/ /__| (_) | (_| |  __/  / /  | | | (_| || | | | | | | | | (_| |    
\____/\___/ \__,_|\___|  \/   |_|  \__,_|/ |_| |_|_|_| |_|\__, |    
                                       |__/               |___/     
        """
        self.console.print(banner, style="bold cyan")
        self.console.print("AI-Powered GitHub Repository Code Analyzer\n", style="bold yellow")
    
    def setup_repository(self):
        self.console.print(Panel("[bold]Repository Setup[/bold]", style="cyan"))
        
        repo_owner = Prompt.ask("[cyan]Enter GitHub repository owner[/cyan]")
        repo_name = Prompt.ask("[cyan]Enter GitHub repository name[/cyan]")
        
        extensions_input = Prompt.ask(
            "[cyan]File extensions to analyze (comma-separated, e.g., py,js,ts)[/cyan]",
            default="py,js,ts,jsx,tsx,java,go,rs,cpp,c,h"
        )
        
        allowed_extensions = [ext.strip() for ext in extensions_input.split(',')]
        
        model = Prompt.ask(
            "[cyan]OpenAI model[/cyan]",
            default="gpt-4o-mini"
        )
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            task = progress.add_task(f"[cyan]Downloading {repo_owner}/{repo_name}...", total=None)
            
            try:
                self.repo_files = load_github_repo(
                    repo_owner=repo_owner,
                    repo_name=repo_name,
                    allowed_extensions=allowed_extensions
                )
                self.llm_client = OpenAIClient(model=model)
                progress.update(task, completed=True)
                
                self.console.print(
                    f"\n[green]✓[/green] Successfully loaded {len(self.repo_files)} files from {repo_owner}/{repo_name}",
                    style="bold green"
                )
            except Exception as e:
                progress.update(task, completed=True)
                self.console.print(f"\n[red]✗[/red] Error: {str(e)}", style="bold red")
                return False
        
        return True
    
    def show_commands(self):
        table = Table(title="Available Commands", show_header=True, header_style="bold magenta")
        table.add_column("Command", style="cyan", width=15)
        table.add_column("Description", style="white")
        
        table.add_row("help", "Show this help message")
        table.add_row("files", "List analyzed files from last query")
        table.add_row("stats", "Show repository statistics")
        table.add_row("exit/quit", "Exit the program")
        table.add_row("<question>", "Ask any question about the codebase")
        
        self.console.print(table)
    
    def show_stats(self):
        if not self.repo_files:
            self.console.print("[red]No repository loaded[/red]")
            return
        
        table = Table(title="Repository Statistics", show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")
        
        table.add_row("Total Files", str(len(self.repo_files)))
        
        extensions = {}
        for filename in self.repo_files.keys():
            ext = filename.split('.')[-1] if '.' in filename else 'no-ext'
            extensions[ext] = extensions.get(ext, 0) + 1
        
        ext_summary = ', '.join([f"{ext}: {count}" for ext, count in sorted(extensions.items())])
        table.add_row("Files by Extension", ext_summary)
        
        self.console.print(table)
    
    def show_analyzed_files(self):
        if not self.last_files_analyzed:
            self.console.print("[yellow]No files have been analyzed yet[/yellow]")
            return
        
        table = Table(title="Files Analyzed in Last Query", show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=6)
        table.add_column("File Path", style="cyan")
        
        for idx, filepath in enumerate(self.last_files_analyzed, 1):
            table.add_row(str(idx), filepath)
        
        self.console.print(table)
    
    def ask_question(self, question: str):
        self.console.print("\n[cyan]Analyzing...[/cyan]\n")
        
        callback = RichDisplayCallback(self.console)
        
        try:
            report = analyze(
                question, 
                self.repo_files, 
                self.llm_client,
                callback=callback
            )
            self.last_files_analyzed = report.files_analyzed
            
            self.console.print()
            self.console.print(Panel(
                Markdown(report.answer),
                title="[bold cyan]Analysis Result[/bold cyan]",
                border_style="cyan"
            ))
            
            if report.files_analyzed:
                self.console.print(
                    f"\n[dim]Analyzed {len(report.files_analyzed)} file(s). Type 'files' to see the list.[/dim]"
                )
            
        except Exception as e:
            self.console.print(f"\n[red]✗[/red] Error: {str(e)}", style="bold red")
    
    def get_user_input(self) -> str:
        """Get user input, supporting multi-line paste and manual multi-line mode."""
        import sys
        
        # Try to read input with support for pasted multi-line content
        self.console.print("\n[bold cyan]➜[/bold cyan] ", end="")
        
        lines = []
        first_line = input().strip()
        
        # Check if user wants manual multi-line input (ends with \)
        if first_line.endswith('\\'):
            self.console.print("[dim]Multi-line mode (end with empty line)[/dim]")
            lines = [first_line[:-1]]  # Remove the trailing \
            
            while True:
                line = Prompt.ask("[bold cyan]...[/bold cyan]")
                if line.strip() == '':
                    break
                lines.append(line)
            
            return '\n'.join(lines)
        
        # Check if there's more input available (pasted content)
        lines = [first_line]
        
        # Read any additional lines that were pasted
        if sys.platform == 'win32':
            # Windows: check if there's input in the buffer
            import msvcrt
            while msvcrt.kbhit():
                char = msvcrt.getwche()
                if char == '\r':  # Enter key
                    char = '\n'
                if char == '\n':
                    if lines[-1]:  # Only add new line if current line has content
                        lines.append('')
                else:
                    lines[-1] += char
        else:
            # Unix-like: use select to check for available input
            import select
            while select.select([sys.stdin], [], [], 0)[0]:
                line = sys.stdin.readline()
                if not line:
                    break
                lines.append(line.rstrip('\n'))
        
        result = '\n'.join(lines).strip()
        return result
    
    def run(self):
        self.print_banner()
        
        if not self.setup_repository():
            return
        
        self.console.print("\n[bold green]Repository loaded successfully![/bold green]")
        self.console.print("Type 'help' for available commands or ask a question about the code.")
        self.console.print("[dim]Tip: Paste multi-line text directly, or end with \\ for manual multi-line mode[/dim]\n")
        
        while True:
            try:
                user_input = self.get_user_input()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ['exit', 'quit']:
                    self.console.print("[yellow]Goodbye![/yellow]")
                    break
                
                elif user_input.lower() == 'help':
                    self.show_commands()
                
                elif user_input.lower() == 'stats':
                    self.show_stats()
                
                elif user_input.lower() == 'files':
                    self.show_analyzed_files()
                
                else:
                    self.ask_question(user_input)
                    
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Use 'exit' or 'quit' to leave.[/yellow]")
            except Exception as e:
                self.console.print(f"[red]Error: {str(e)}[/red]")


def main():
    cli = InteractiveCLI()
    cli.run()


if __name__ == "__main__":
    main()
