import asyncio
import datetime
from rich.console import Console
from rich.prompt import Confirm

class ChatTerminal:
    def __init__(self):
        self.chat_history = []
        self.console = Console()
        
    async def send_message(self, message: str, is_user: bool = True):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = {
            "timestamp": timestamp,
            "content": message,
            "type": "user" if is_user else "agent"
        }
        self.chat_history.append(entry)
        
        # Exibir mensagem formatada
        self.console.print(
            f"[{'green' if is_user else 'blue'}][{timestamp}] "
            f"{'Você' if is_user else 'Agente'}: {message}"
        )

    async def request_confirmation(self, message: str) -> bool:
        return Confirm.ask(message)

    def get_chat_history(self):
        return [
            {
                "role": entry["type"],
                "parts": [entry["content"]]
            }
            for entry in self.chat_history
        ]

    def clear_history(self):
        self.chat_history.clear()