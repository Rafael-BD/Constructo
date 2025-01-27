from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from datetime import datetime
import json
import os

class UnifiedTerminal:
    def __init__(self, log_file="agent_history.log"):
        self.console = Console()
        self.log_file = log_file
        self.messages = []
        self.layout = Layout()
        
        self._setup_layout()
        
    def _setup_layout(self):
        self.layout.split_column(
            Layout(name="chat", ratio=2),
            Layout(name="logs", ratio=1)
        )
        
    def _generate_display(self):
        # Chat history
        chat_table = Table.grid()
        chat_table.add_column(style="cyan", justify="right")
        chat_table.add_column(style="white")
        
        for msg in self.messages[-10:]:
            prefix = f"[{msg['timestamp']}] [{msg['type']}]"
            chat_table.add_row(prefix, msg['content'])
            
        # Current logs
        log_table = Table.grid()
        log_table.add_column()
        
        self.layout["chat"].update(Panel(chat_table, title="Chat History"))
        self.layout["logs"].update(Panel(log_table, title="Live Logs"))
        
        return self.layout
        
    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = {
            "timestamp": timestamp,
            "type": level,
            "content": message
        }
        
        self.messages.append(entry)
        self._save_to_file(entry)
        
        # Atualizar display
        with Live(self._generate_display(), refresh_per_second=4):
            self.console.print(f"[{level}] {message}")
            
    def _save_to_file(self, entry: dict):
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry) + "\n")
            
    def load_history(self):
        if os.path.exists(self.log_file):
            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        self.messages.append(entry)
                    except json.JSONDecodeError:
                        continue
