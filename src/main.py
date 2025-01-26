import asyncio
import os
import subprocess
from src.ai.agent import AIAgent
from src.utils.config import load_config

def open_terminal_window():
    """Tenta abrir um terminal com base nos terminais disponíveis no sistema"""
    terminals = [
        'xfce4-terminal',
        'konsole',
        'gnome-terminal',
        'xterm'  # fallback
    ]
    
    for terminal in terminals:
        try:
            subprocess.Popen([terminal, '--', 'python3', '-m', 'core.log_terminal'])
            return True
        except FileNotFoundError:
            continue
    
    print("Aviso: Não foi possível abrir uma janela de terminal. Logs serão exibidos no console.")
    return False

async def main():
    config = load_config()
    agent = AIAgent(config['api_key'])
    
    # Tentar abrir o terminal de logs
    open_terminal_window()
    
    print("Terminal de Chat Iniciado")
    while True:
        user_input = input(">>> ")
        if user_input.lower() == "exit":
            break
            
        response = await agent.process_command(user_input)
        print(f"Agente: {response}")

if __name__ == "__main__":
    asyncio.run(main())