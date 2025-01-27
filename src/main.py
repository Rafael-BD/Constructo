import asyncio
from src.ai.agent import AIAgent
from src.utils.config import load_config
from rich.prompt import Prompt
from rich.console import Console

async def main():
    config = load_config()
    agent = AIAgent(config['api_key'])
    console = Console()
    
    console.print("[bold green]Terminal de Chat Iniciado[/bold green]")
    while True:
        try:
            user_input = Prompt.ask(">>> ")
            if user_input.lower() == "exit":
                break

            # Chamamos o agente, mas não imprimimos a resposta aqui
            response = await agent.process_command(user_input)
            # Caso deseje, poderia exibir apenas erros ou msgs específicas:
            # if response and "Erro:" in response:
            #     console.print(response)
            
        except KeyboardInterrupt:
            print("\nEncerrando programa...")
            break
        except Exception as e:
            console.print(f"[bold red]Erro:[/bold red] {e}")

if __name__ == "__main__":
    asyncio.run(main())