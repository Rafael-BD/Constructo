from typing import List, Dict

class ContextManager:
    def __init__(self, max_context_length: int = 10):
        self.context_history: List[Dict] = []
        self.max_context_length = max_context_length
        
    def add_to_context(self, interaction: Dict):
        self.context_history.append(interaction)
        if len(self.context_history) > self.max_context_length:
            self.context_history.pop(0)
            
    def get_current_context(self) -> str:
        return "\n".join([
            f"[{item['timestamp']}] {item['type']}: {item['content']}"
            for item in self.context_history
        ])
