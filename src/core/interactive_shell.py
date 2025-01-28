import pexpect
import time
from typing import List, Tuple
import re
import os

class InteractiveShell:
    def __init__(self):
        self.sessions = {}
        self.prompts = {
            'msfconsole': r'msf\d*\s*>',  # Simplificado
            'sqlmap': r'\[.\]\s*$'
        }
        
    def start_session(self, program: str) -> str:
        session_id = f"{program}_{int(time.time())}"
        
        if program == 'msfconsole':
            try:
                # Configuração básica do ambiente
                env = os.environ.copy()
                env['TERM'] = 'xterm'
                
                # Iniciar Metasploit de forma mais simples
                session = pexpect.spawn(
                    '/usr/bin/msfconsole',  # Caminho completo
                    encoding='utf-8',
                    env=env,
                    timeout=60,
                    echo=False
                )
                
                # Aguardar inicialização com padrões mais flexíveis
                session.expect(['Metasploit', 'Framework', 'msf'], timeout=30)
                
                # Aguardar prompt
                index = session.expect([r'msf\d*\s*>', pexpect.TIMEOUT], timeout=30)
                if index == 0:
                    print("Metasploit iniciado com sucesso")
                    # Limpar buffer inicial
                    session.sendline('')
                    session.expect(r'msf\d*\s*>', timeout=10)
                    
                    self.sessions[session_id] = session
                    return session_id
                else:
                    print("Timeout aguardando prompt do Metasploit")
                    session.close()
                    return None
                    
            except Exception as e:
                print(f"Erro ao iniciar Metasploit: {str(e)}")
                return None
                
        else:
            session = pexpect.spawn(program, encoding='utf-8')
            
            # Aguardar prompt inicial
            if program in self.prompts:
                try:
                    session.expect(self.prompts[program], timeout=30)
                except pexpect.TIMEOUT:
                    print(f"Aviso: Timeout aguardando prompt inicial de {program}")
        
        self.sessions[session_id] = session
        return session_id
        
    def send_command(self, session_id: str, command: str, expect_patterns: List[str] = None) -> Tuple[str, int]:
        if session_id not in self.sessions:
            return "Sessão não encontrada", 1
            
        session = self.sessions[session_id]
        program = session_id.split('_')[0]
        
        if program == 'msfconsole':
            try:
                # Garantir que estamos no prompt
                session.sendline('')
                session.expect(r'msf\d*\s*>', timeout=10)
                
                # Enviar comando
                session.sendline(command)
                
                # Aguardar resposta com timeout maior
                index = session.expect([r'msf\d*\s*>', pexpect.TIMEOUT], timeout=120)
                
                output = session.before
                return self._clean_output(output, program), 0 if index == 0 else 1
                
            except pexpect.TIMEOUT:
                return "Timeout aguardando resposta", -1
            except pexpect.EOF:
                return "Programa encerrado", -2
                
        else:
            # ...existing code for other programs...
            pass
            
    def _clean_output(self, output: str, program: str) -> str:
        if not output:
            return ""
            
        # Limpar códigos ANSI e caracteres de controle
        output = re.sub(r'\x1b\[[0-9;]*[mGKH]', '', output)
        output = re.sub(r'[\x00-\x1F\x7F]', '', output)
        
        if program == 'msfconsole':
            # Remover linhas vazias e prompts
            lines = []
            for line in output.split('\n'):
                line = line.strip()
                if line and not re.match(r'^msf\d*\s*>', line):
                    lines.append(line)
            output = '\n'.join(lines)
            
        return output.strip()
    
    def close_session(self, session_id: str):
        """Encerra uma sessão"""
        if session_id in self.sessions:
            self.sessions[session_id].sendline('exit')
            self.sessions[session_id].close()
            del self.sessions[session_id]
