from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.prompt import Confirm
from datetime import datetime
import json
import os

class UnifiedTerminal:
    def __init__(self, log_file="agent_history.log"):
        self.console = Console()
        self.log_file = log_file
        self.messages = []
        self.spinner = None
        self.live = None 
        
        self.log_styles = {
            "INPUT": "bold cyan",
            "EXEC": "bold yellow",
            "OUTPUT": "green",
            "ERROR": "bold red",
            "WARNING": "yellow",
            "SUCCESS": "bold green",
            "INFO": "blue",
            "AGENT": "bold cyan"
        }
        
    def start_processing(self, message="Processing..."):
        """Shows a spinner while processing"""
        if self.live:
            self.stop_processing()
            
        self.spinner = Spinner('dots')
        self.live = Live(self.spinner, console=self.console, transient=True)  # transient=True to auto-clear
        self.live.start()
        
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
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry) + "\n")
            
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
