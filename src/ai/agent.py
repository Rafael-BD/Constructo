import google.generativeai as genai
import json
import re  # (1) para remover blocos ```json
from datetime import datetime
from ..core.terminal import UnifiedTerminal
from ..core.linux_interaction import LinuxInteraction
from ..prompts.main_context import SYSTEM_PROMPT
from .context_manager import ContextManager

class AIAgent:
    def __init__(self, api_key: str):
        self.chat = self._initialize_chat(api_key)
        self.terminal = UnifiedTerminal()
        self.linux = LinuxInteraction()
        self.context_manager = ContextManager()
        
    def _initialize_chat(self, api_key: str):
        genai.configure(api_key=api_key)
        
        # Configurar o modelo com os parâmetros de geração
        model = genai.GenerativeModel(
            'gemini-2.0-flash-exp',
            generation_config=genai.GenerationConfig(
                temperature=0.9,
                top_p=1,
                top_k=1,
                max_output_tokens=2048,
            )
        )
        
        # Iniciar chat com instruções do sistema
        return model.start_chat(history=[
            {
                "role": "user",
                "parts": [SYSTEM_PROMPT]
            },
            {
                "role": "model",
                "parts": ["Sistema inicializado com instruções. Pronto para executar comandos."]
            }
        ])
        
    async def process_command(self, user_input: str, require_confirmation=True):
        try:
            context = self.context_manager.get_current_context()
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Usar 'as live' para encerrar o spinner ao sair do bloco:
            with self.terminal.start_processing("Processando...") as live:
                prompt = f"""Contexto atual: {context}
                Comando do usuário: {user_input}
                Timestamp: {current_time}
                
                Analise a entrada e responda no formato JSON especificado."""
                response = self.chat.send_message(prompt)
                response_text = response.text if response else None
            
            # Limpar a linha do spinner após sair do bloco
            self.terminal.clear_line()
            
            if not response_text:
                raise ValueError("Received empty response from the chat model.")
            
            async def execute_step(parsed_response):
                response_text = parsed_response.get("mensagem") or parsed_response.get("análise") or ""
                
                # Use log_agent para exibir mensagem do Agente em ciano sem timestamp
                if response_text:
                    self.terminal.log_agent(response_text)

                if "próximo_passo" in parsed_response and parsed_response["próximo_passo"].get("ação"):
                    if parsed_response["próximo_passo"].get("requer_confirmação", True) and require_confirmation:
                        confirmation = await self.terminal.request_confirmation(
                            f"Devo executar a ação '{parsed_response['próximo_passo']['ação']}'? "
                            f"(Risco: {parsed_response['próximo_passo']['risco']})"
                        )
                        if not confirmation:
                            return "Operação cancelada pelo usuário.", False

                    self.terminal.log(f"Executando: {parsed_response['próximo_passo']['ação']}", "EXEC")
                    stdout, stderr, returncode = self.linux.run_command(parsed_response['próximo_passo']['ação'])

                    # Unificar stdout e stderr para o agente receber todo o log
                    combined_result = ""
                    if stdout.strip():
                        combined_result += stdout.rstrip()  # remover newline extra
                    if stderr.strip():
                        combined_result += f"\n{stderr.strip()}"

                    # Se houve código de erro e stderr
                    if returncode != 0 and stderr.strip():
                        self.terminal.log(
                            f"Comando retornou código {returncode}: {stderr.strip()}",
                            "ERROR"
                        )

                    # Se houver algo para mostrar
                    if combined_result.strip():
                        self.terminal.log(combined_result, "OUTPUT", show_timestamp=False)
                        self.context_manager.add_to_context({
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "type": "output",
                            "content": combined_result
                        })

                        if parsed_response.get("continuar", False):
                            self.terminal.log("Analisando resultado...", "INFO")
                            next_response = self.chat.send_message(
                                f"Analise este resultado e decida o próximo passo:\n{combined_result}"
                            )
                            if next_response and next_response.text:
                                clean_text = re.sub(r"```json\s*([\s\S]*?)```", r"\1", next_response.text)
                                try:
                                    next_parsed = json.loads(_extract_json(clean_text))
                                    return await execute_step(next_parsed)
                                except json.JSONDecodeError:
                                    return clean_text.strip(), False

                    # Retorna vazio para evitar duplicar a mesma mensagem
                    return "", parsed_response.get("continuar", False)

                # Retorna vazio quando não há comando
                return "", parsed_response.get("continuar", False)

            def _extract_json(text: str) -> str:
                start = text.find('{')
                end = text.rfind('}') + 1
                if start >= 0 and end > 0:
                    return text[start:end]
                return text

            async def process_response(response_text: str):
                clean_text = re.sub(r"```json\s*([\s\S]*?)```", r"\1", response_text)
                json_str = _extract_json(clean_text)
                try:
                    parsed = json.loads(json_str)
                    result, should_continue = await execute_step(parsed)
                    if should_continue:
                        self.terminal.log("Continuando análise...", "INFO")
                        return await process_response(result)
                    return result
                except json.JSONDecodeError:
                    return clean_text.strip()

            final_result = await process_response(response_text)
            # Se final_result estiver vazio, não exibe "Processamento concluído."
            return final_result.strip() if final_result else ""

        except Exception as e:
            error_msg = f"Erro: {str(e)}"
            self.terminal.log(error_msg, "ERROR")
            return error_msg
