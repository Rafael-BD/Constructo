import asyncio
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from ai.agent import AIAgent
from utils.config import load_config
from rich.console import Console
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.shortcuts import set_title
from prompt_toolkit.styles import Style
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.clipboard import ClipboardData
from os.path import expanduser
from prompt_toolkit.application.current import get_app
import pyperclip

async def main():
    config = load_config()
    agent = AIAgent(config)
    console = Console()
    
    # Create key bindings
    kb = KeyBindings()
    
    @kb.add('escape', 'c')
    @kb.add('escape', 'C')
    def copy_selection(event):
        """Copy selection to clipboard."""
        data = event.current_buffer.copy_selection()
        if data:
            # Ensure data is a string
            if isinstance(data, ClipboardData):
                data = data.text
            # Copy to both internal and system clipboard
            event.app.clipboard.set_data(ClipboardData(text=data))
            pyperclip.copy(data)
            
    @kb.add('escape', 'v')
    @kb.add('escape', 'V')
    def paste_selection(event):
        """Paste from clipboard."""
        try:
            # Try system clipboard first
            text = pyperclip.paste()
            if not text:
                # Fallback to internal clipboard
                data = event.app.clipboard.get_data()
                if isinstance(data, ClipboardData):
                    text = data.text
            
            if text:
                # Insert text at cursor position
                event.current_buffer.insert_text(text)
                
        except Exception as e:
            console.print(f"[red]Error pasting: {str(e)}[/red]")
    
    # Initialize prompt session
    session = PromptSession(
        history=FileHistory(expanduser('~/.constructo_history')),
        auto_suggest=AutoSuggestFromHistory(),
        multiline=False,
        wrap_lines=True,
        style=Style.from_dict({'prompt': 'ansicyan bold'}),
        enable_history_search=True,
        include_default_pygments_style=True,
        key_bindings=kb
    )
    
    # Set terminal title
    set_title("Constructo Terminal")
    
    # Terminal startup messages
    console.print("[bold green]Chat Terminal Started[/bold green]")
    console.print("[dim]Terminal controls:[/dim]")
    console.print("[dim]- Use Alt+c/v (case insensitive) for copy/paste[/dim]")
    console.print("[dim]- Use standard terminal selection (mouse drag or Shift+arrows)[/dim]")
    console.print("[dim]- Use Ctrl+A/E to move to start/end of line[/dim]")
    console.print("[dim]- Use Ctrl+R to search command history[/dim]")
    console.print("[dim]- Use Up/Down arrows to navigate history[/dim]")
    
    while True:
        try:
            user_input = await session.prompt_async(
                ">>> ",
                complete_in_thread=True,
            )
            
            if user_input.lower().strip() == "exit":
                break
            elif user_input.strip():
                response = await agent.process_command(user_input)
                
        except KeyboardInterrupt:
            print("\nShutting down...")
            break
        except EOFError:
            break
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")

if __name__ == "__main__":
    asyncio.run(main())
