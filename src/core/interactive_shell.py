import pexpect
import time
from typing import List, Tuple
import re
import os

class InteractiveShell:
    def __init__(self):
        self.sessions = {}
        self.prompts = {
            'msfconsole': r'msf\d*\s*>',
            'sqlmap': r'\[.\]\s*$'
        }
        
    def start_session(self, program: str) -> str:
        session_id = f"{program}_{int(time.time())}"
        
        if program == 'msfconsole':
            try:
                # Basic environment configuration
                env = os.environ.copy()
                env['TERM'] = 'xterm'
                
                # Start Metasploit in a simpler way
                session = pexpect.spawn(
                    '/usr/bin/msfconsole',  # Full path
                    encoding='utf-8',
                    env=env,
                    timeout=60,
                    echo=False
                )
                
                # Wait for initialization with more flexible patterns
                session.expect(['Metasploit', 'Framework', 'msf'], timeout=30)
                
                # Wait for prompt
                index = session.expect([r'msf\d*\s*>', pexpect.TIMEOUT], timeout=30)
                if index == 0:
                    print("Metasploit started successfully")
                    # Clear initial buffer
                    session.sendline('')
                    session.expect(r'msf\d*\s*>', timeout=10)
                    
                    self.sessions[session_id] = session
                    return session_id
                else:
                    print("Timeout waiting for Metasploit prompt")
                    session.close()
                    return None
                    
            except Exception as e:
                print(f"Error starting Metasploit: {str(e)}")
                return None
                
        else:
            session = pexpect.spawn(program, encoding='utf-8')
            
            # Wait for initial prompt
            if program in self.prompts:
                try:
                    session.expect(self.prompts[program], timeout=30)
                except pexpect.TIMEOUT:
                    print(f"Warning: Timeout waiting for initial prompt of {program}")
        
        self.sessions[session_id] = session
        return session_id
        
    def send_command(self, session_id: str, command: str, expect_patterns: List[str] = None) -> Tuple[str, int]:
        if session_id not in self.sessions:
            return "Session not found", 1
            
        session = self.sessions[session_id]
        program = session_id.split('_')[0]
        
        if program == 'msfconsole':
            try:
                # Ensure we are at the prompt
                session.sendline('')
                session.expect(r'msf\d*\s*>', timeout=10)
                
                # Send command
                session.sendline(command)
                
                # Wait for response with long timeout
                index = session.expect([r'msf\d*\s*>', pexpect.TIMEOUT], timeout=120)
                
                output = session.before
                return self._clean_output(output, program), 0 if index == 0 else 1
                
            except pexpect.TIMEOUT:
                return "Timeout waiting for response", -1
            except pexpect.EOF:
                return "Program terminated", -2
                
        else:
            pass
            
    def _clean_output(self, output: str, program: str) -> str:
        if not output:
            return ""
            
        # Clean ANSI codes and control characters
        output = re.sub(r'\x1b\[[0-9;]*[mGKH]', '', output)
        output = re.sub(r'[\x00-\x1F\x7F]', '', output)
        
        if program == 'msfconsole':
            # Remove empty lines and prompts
            lines = []
            for line in output.split('\n'):
                line = line.strip()
                if line and not re.match(r'^msf\d*\s*>', line):
                    lines.append(line)
            output = '\n'.join(lines)
            
        return output.strip()
    
    def close_session(self, session_id: str):
        """Closes a session"""
        if session_id in self.sessions:
            self.sessions[session_id].sendline('exit')
            self.sessions[session_id].close()
            del self.sessions[session_id]
