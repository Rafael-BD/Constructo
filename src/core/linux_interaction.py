import subprocess
import signal
import os

class LinuxInteraction:
    # List of commands that can return non-zero codes without being an error
    KNOWN_NON_ERROR_CODES = {
        'nikto': [1],
        'hydra': [0, 1, 255], 
        'gobuster': [0, 1], 
        'dirb': [0, 1], 
    }
    
    def run_command(self, command: str, timeout: int = None):
        try:
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=os.setsid 
            )
            
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                returncode = process.returncode
                
                # Check if the return code is expected for the command
                cmd_base = command.split()[0]
                if cmd_base in self.KNOWN_NON_ERROR_CODES:
                    if returncode in self.KNOWN_NON_ERROR_CODES[cmd_base]:
                        returncode = 0  # Consider as success
                
                return stdout, stderr, returncode
                
            except subprocess.TimeoutExpired:
                # Kill the entire process group
                os.killpg(process.pid, signal.SIGTERM)
                return "", "Command interrupted by timeout.", 1
                
        except Exception as e:
            return "", str(e), 1

    def analyze_output(self, output: str):
        return f"Simple output analysis: {output[:50]}..."