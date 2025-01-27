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
        
        # Definir cores para diferentes tipos de logs
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
        
    def start_processing(self, message="Processando..."):
        """Mostra um spinner enquanto processa"""
        self.spinner = Spinner('dots')
        return Live(self.spinner, console=self.console)
        
    def log(self, message: str, level: str = "INFO", show_timestamp=True):
        """Log com cores e timestamps opcionais"""
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
        """Limpa a última linha do terminal"""
        self.console.print("\033[A\033[K", end="")
            
    async def request_confirmation(self, message: str) -> bool:
        """Solicita confirmação do usuário de forma mais limpa"""
        self.console.print()  # Nova linha para limpar formatação
        return Confirm.ask(message, default=False)
            
    def _save_to_file(self, entry: dict):
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry) + "\n")
            
    def log_agent(self, message: str):
        """
        Exibe mensagem do 'Agente' em estilo ciano, sem timestamp.
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = {
            "timestamp": timestamp,
            "type": "AGENT",
            "content": message
        }
        self.messages.append(entry)
        self._save_to_file(entry)
        self.console.print(f"[dim]{timestamp}[/dim] [{self.log_styles['AGENT']}][Agente][/] {message}")
