import subprocess

class LinuxInteraction:
    def run_command(self, command: str, timeout: int = None):
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
            return result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return "", "Comando interrompido por timeout."

    def analyze_output(self, output: str):
        return f"Análise simples do output: {output[:50]}..."