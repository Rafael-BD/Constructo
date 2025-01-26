import sys
import datetime
from rich.console import Console
from rich.live import Live
from rich.table import Table
from queue import Queue
import threading

class LogTerminal:
    def __init__(self):
        self.logs = []
        self.console = Console()
        self.log_queue = Queue()
        self.running = True
        
    def start(self):
        """Inicia o terminal de logs em uma janela separada"""
        self.console.print("[bold green]Terminal de Logs Iniciado[/bold green]")
        
        with Live(self.generate_table(), refresh_per_second=4) as live:
            while self.running:
                if not self.log_queue.empty():
                    log = self.log_queue.get()
                    self.logs.append(log)
                    live.update(self.generate_table())

    def generate_table(self):
        table = Table()
        table.add_column("Timestamp")
        table.add_column("Tipo")
        table.add_column("Mensagem")
        
        for log in self.logs[-20:]:  # Mostrar apenas últimos 20 logs
            table.add_row(
                log["timestamp"],
                f"[{log['level_color']}]{log['level']}[/{log['level_color']}]",
                log["message"]
            )
        return table

    def add_log(self, message: str, level: str = "INFO"):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level_colors = {
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "COMMAND": "blue"
        }
        
        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "level_color": level_colors.get(level, "white"),
            "message": message
        }
        
        self.log_queue.put(log_entry)

    def stop(self):
        self.running = False