import subprocess
import signal
import os
import shlex 

class LinuxInteraction:
    
    def run_command(self, command: str, timeout: int = None):
        try:
            args = shlex.split(command)
            
            process = subprocess.Popen(
                args,            
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=os.setsid,
            )
            
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                returncode = process.returncode
                
                return stdout, stderr, returncode
                
            except subprocess.TimeoutExpired:
                # Kill the entire process group
                os.killpg(process.pid, signal.SIGTERM)
                return "", "Command interrupted by timeout.", 1
                
        except Exception as e:
            return "", str(e), 1

    def analyze_output(self, output: str):
        return f"Simple output analysis: {output[:50]}..."