import asyncio
from src.ai.agent import AIAgent
from src.utils.config import load_config
from rich.prompt import Prompt

async def main():
    config = load_config()
    agent = AIAgent(config['api_key'])
    
    print("Terminal de Chat Iniciado")
    while True:
        try:
            user_input = Prompt.ask(">>> ")
            if user_input.lower() == "exit":
                break
                
            response = await agent.process_command(user_input)
            
        except KeyboardInterrupt:
            print("\nEncerrando programa...")
            break
        except Exception as e:
            print(f"Erro: {e}")

if __name__ == "__main__":
    asyncio.run(main())