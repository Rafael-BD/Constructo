from rich.console import Console, RenderableType
from rich.live import Live
from rich.spinner import Spinner
from rich.prompt import Confirm
from rich.panel import Panel
from rich.text import Text
from rich.console import Group
from datetime import datetime
import time
import json
import os
from pathlib import Path

class UnifiedTerminal:
    def __init__(self, log_file="logs/agent_history.log"):
        self.console = Console()
        self.log_file = log_file
        self.messages = []
        self.spinner = None
        self.live = None 
        
        # Create logs directory if it doesn't exist
        log_dir = os.path.dirname(self.log_file)
        if log_dir:
            Path(log_dir).mkdir(parents=True, exist_ok=True)
        
        self.log_styles = {
            "INPUT": "bold cyan",
            "EXEC": "bold yellow",
            "OUTPUT": "green",
            "ERROR": "bold red",
            "WARNING": "yellow",
            "SUCCESS": "bold green",
            "INFO": "blue",
            "AGENT": "bold cyan",
            "THINKING": "bold magenta",
            "ANALYZING": "bold blue",
            "DEEP_REASONING": "bold #FF69B4"  # Hot pink
        }
        
    def start_processing(self, message="Thinking...", style="THINKING"):
        """Shows a spinner while processing"""
        if self.live:
            self.stop_processing()
            
        self.spinner = Spinner('dots')
        style_color = self.log_styles.get(style)
        
        class SpinnerText:
            def __rich_console__(self, console, options):
                spinner_frame = self.spinner.render(time.time())
                text = Text()
                text.append(spinner_frame)
                text.append(" ")
                text.append(message)
                text.stylize(style_color)
                yield text
                
            def __init__(self, spinner):
                self.spinner = spinner
            
        self.live = Live(
            SpinnerText(self.spinner),
            console=self.console,
            transient=True,
            refresh_per_second=20
        )
        self.live.start()
        
    def start_deep_reasoning(self):
        """Shows deep reasoning header with spinner"""
        if self.live:
            self.stop_processing()
            
        self.spinner = Spinner('dots')
        style_color = self.log_styles.get("DEEP_REASONING")
        
        class ReasoningHeader:
            def __rich_console__(self, console, options):
                spinner_frame = self.spinner.render(time.time())
                text = Text()
                text.append(spinner_frame)
                text.append(" Deep Reasoning...")
                text.stylize(style_color)
                yield Panel(
                    text,
                    style=style_color,
                    expand=False
                )
                
            def __init__(self, spinner):
                self.spinner = spinner
            
        self.live = Live(
            ReasoningHeader(self.spinner),
            console=self.console,
            transient=False,
            refresh_per_second=20
        )
        self.live.start()
        
    def log_deep_reasoning_step(self, step: str):
        """Logs a deep reasoning step with dimmed style"""
        self.console.print(f"[dim]→ {step}[/dim]")
        
    def start_analysis(self):
        """Shows analyzing spinner"""
        self.start_processing("Analyzing result...", "ANALYZING")
        
    def stop_processing(self):
        """Stops the spinner and clears the line correctly"""
        if self.live:
            self.live.stop()
            self.live = None
        if self.spinner:
            self.spinner = None
        self.clear_line()
        self.console.print()
        
    def log(self, message: str, level: str = "INFO", show_timestamp=True):
        """Log with optional colors and timestamps"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = {
            "timestamp": timestamp,
            "type": level,
            "content": message
        }
        
        self.messages.append(entry)
        self._save_to_file(entry)
        
        if show_timestamp:
            self.console.print(f"[dim]{timestamp}[/dim] [{self.log_styles.get(level, 'white')}]{message}[/]")
        else:
            self.console.print(f"[{self.log_styles.get(level, 'white')}]{message}[/]")
            
    def clear_line(self):
        """Clears the last line of the terminal without using ANSI codes"""
        print("\r", end="")  # Return cursor to the beginning of the line
        print(" " * self.console.width, end="\r")  # Clear line with spaces
        
    def stop_spinner(self):
        """Stops the spinner and clears the line"""
        if self.spinner:
            self.clear_line()
            self.spinner = None
            
    async def request_confirmation(self, message: str) -> bool:
        """Requests user confirmation in a cleaner way"""
        self.console.print()  # New line to clear formatting
        return Confirm.ask(message, default=False)
            
    def _save_to_file(self, entry: dict):
        """Save log entry to file with error handling"""
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry) + "\n")
        except (PermissionError, OSError) as e:
            # If we can't write to file, just print warning and continue
            print(f"\nWarning: Could not write to log file: {str(e)}")
            # Try to write to user's home directory instead
            try:
                home_log = os.path.expanduser("~/constructo_agent.log")
                with open(home_log, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(entry) + "\n")
            except:
                # If that also fails, just skip logging to file
                pass
            
    def log_agent(self, message: str):
        """Displays 'Agent' message in cyan style with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = {
            "timestamp": timestamp,
            "type": "AGENT",
            "content": message
        }
        self.messages.append(entry)
        self._save_to_file(entry)
        
        # Clear previous line and print message
        self.clear_line()
        self.console.print(
            f"[dim]{timestamp}[/dim] [{self.log_styles['AGENT']}][Agent][/] {message}"
        )
