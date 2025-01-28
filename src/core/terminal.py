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
        
    def start_processing(self, message="Processando..."):
        """Mostra um spinner enquanto processa"""
        if self.live:
            self.stop_processing()
            
        self.spinner = Spinner('dots')
        self.live = Live(self.spinner, console=self.console, transient=True)  # transient=True para auto-limpar
        self.live.start()
        
    def stop_processing(self):
        """Para o spinner e limpa a linha corretamente"""
        if self.live:
            self.live.stop()
            self.live = None
        if self.spinner:
            self.spinner = None
        self.clear_line()
        self.console.print()  # Nova linha limpa
        
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
        """Limpa a última linha do terminal sem usar códigos ANSI"""
        print("\r", end="")  # Retorna cursor para início da linha
        print(" " * self.console.width, end="\r")  # Limpa linha com espaços
        
    def stop_spinner(self):
        """Para o spinner e limpa a linha"""
        if self.spinner:
            self.clear_line()
            self.spinner = None
            
    async def request_confirmation(self, message: str) -> bool:
        """Solicita confirmação do usuário de forma mais limpa"""
        self.console.print()  # Nova linha para limpar formatação
        return Confirm.ask(message, default=False)
            
    def _save_to_file(self, entry: dict):
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry) + "\n")
            
    def log_agent(self, message: str):
        """Exibe mensagem do 'Agente' em estilo ciano com timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = {
            "timestamp": timestamp,
            "type": "AGENT",
            "content": message
        }
        self.messages.append(entry)
        self._save_to_file(entry)
        
        # Limpa linha anterior e imprime mensagem
        self.clear_line()
        self.console.print(
            f"[dim]{timestamp}[/dim] [{self.log_styles['AGENT']}][Agente][/] {message}"
        )
