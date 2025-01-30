import subprocess
import signal
import os
import shlex 
import re
import sys

class LinuxInteraction:
    def run_command(self, command: str) -> tuple:
        """
        Execute a command and return its output
        Returns: (stdout, stderr, return_code)
        """
        try:
            # Parse command to handle redirections
            redirect_match = re.search(r'(.*?)(?:\s*>\s*(\S+))?$', command)
            if not redirect_match:
                return "", "Invalid command format", 1
                
            base_command = redirect_match.group(1)
            output_file = redirect_match.group(2)
            
            # Execute command and capture output
            process = subprocess.Popen(
                base_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=True,
                preexec_fn=os.setsid,
                env=os.environ.copy()
            )
            
            # Capture output and wait for completion
            stdout, stderr = process.communicate()
            return_code = process.returncode
            
            # If there's redirection
            if output_file:
                try:
                    # Ensure parent directory exists
                    output_dir = os.path.dirname(output_file)
                    if output_dir and not os.path.exists(output_dir):
                        os.makedirs(output_dir, mode=0o777)
                    elif output_dir:
                        os.chmod(output_dir, 0o777)
                    
                    # Write to file
                    with open(output_file, 'w') as f:
                        f.write(stdout)
                    os.chmod(output_file, 0o666)
                    
                    return f"Output saved to {output_file}" + (f":\n{stdout}" if stdout.strip() else ""), stderr, return_code
                except Exception as e:
                    return "", f"Error writing to file: {str(e)}", 1
            
            # Return command output
            if stdout or not stderr: 
                return stdout, stderr, return_code
            else:
                return "", stderr, return_code
            
        except Exception as e:
            return "", f"Error executing command: {str(e)}", 1