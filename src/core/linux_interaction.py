import subprocess
import shlex
# from .interactive_shell import InteractiveShell  # Desativado temporariamente

class LinuxInteraction:
    INTERACTIVE_COMMANDS = {
        'msfconsole': {
            'prompt_pattern': r'msf\d*\s*>\s*$',
            'error_patterns': ['error', 'Error', 'failed'],
            'expect_timeout': 60,
            'subcommands': ['search', 'use', 'set', 'show', 'run', 'exploit', 'back', 'exit']
        },
        'sqlmap': {
            'prompt_pattern': r'\[.\]\s*$',
            'error_patterns': ['error', 'Error', 'failed'],
            'expect_timeout': 30
        }
    }
    
    def __init__(self):
        # self.interactive_shell = InteractiveShell()  # Desativado temporariamente
        self.active_sessions = {}
    
    def is_interactive_command(self, command: str) -> bool:
        cmd = shlex.split(command)[0]
        return (cmd in self.INTERACTIVE_COMMANDS or 
                any(cmd in info.get('subcommands', []) 
                    for info in self.INTERACTIVE_COMMANDS.values()))
    
    def get_parent_session(self, command: str) -> str:
        """Identifica qual sessão interativa deve receber o comando"""
        cmd = shlex.split(command)[0]
        
        # Se é um comando principal, retorna ele mesmo
        if cmd in self.INTERACTIVE_COMMANDS:
            return cmd
            
        # Se é um subcomando, procura a qual programa pertence
        for program, info in self.INTERACTIVE_COMMANDS.items():
            if cmd in info.get('subcommands', []):
                return program
                
        return None
        
    def run_command(self, command: str, timeout: int = None):
        try:
            cmd = shlex.split(command)[0]
            parent_session = self.get_parent_session(command)
            
            if parent_session:
                # Desativar comandos interativos
                return "", f"Comando '{cmd}' não suportado: programas interativos estão desativados.", 1
            
            # Comandos não interativos executam normalmente
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
            return result.stdout, result.stderr, result.returncode
                
        except subprocess.TimeoutExpired:
            return "", "Comando interrompido por timeout.", 1

    def analyze_output(self, output: str):
        return f"Análise simples do output: {output[:50]}..."