import asyncio
from src.ai.agent import AIAgent
from src.utils.config import load_config
from rich.prompt import Prompt
from rich.console import Console

async def main():
    config = load_config()
    agent = AIAgent(config)
    console = Console()
    
    console.print("[bold green]Chat Terminal Started[/bold green]")
    while True:
        try:
            user_input = Prompt.ask(">>> ")
            if user_input.lower() == "exit":
                break

            response = await agent.process_command(user_input)
            
        except KeyboardInterrupt:
            print("\nShutting down...")
            break
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")

if __name__ == "__main__":
    asyncio.run(main())
