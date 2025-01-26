import google.generativeai as genai
import json
from datetime import datetime
from ..core.chat_terminal import ChatTerminal
from ..core.log_terminal import LogTerminal
from ..core.linux_interaction import LinuxInteraction
from ..prompts.main_context import SYSTEM_PROMPT
from .context_manager import ContextManager

class AIAgent:
    def __init__(self, api_key: str):
        self.chat = self._initialize_chat(api_key)
        self.chat_terminal = ChatTerminal()
        self.log_terminal = LogTerminal()
        self.linux = LinuxInteraction()
        self.context_manager = ContextManager()
        
    def _initialize_chat(self, api_key: str):
        genai.configure(api_key=api_key)
        
        # Configurar o modelo com os parâmetros de geração
        model = genai.GenerativeModel(
            'gemini-1.5-pro',
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
            # Preparar mensagem com contexto atual
            context = self.context_manager.get_current_context()
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            message = {
                "command": user_input,
                "context": context,
                "timestamp": current_time
            }
            
            # Enviar mensagem e obter resposta
            response = await self.chat.send_message(json.dumps(message))
            response_text = response.text
            
            try:
                parsed_response = json.loads(response_text)
            except json.JSONDecodeError:
                parsed_response = {
                    "análise": "Não foi possível analisar a resposta",
                    "ação": response_text,
                    "risco": "médio",
                    "requer_confirmação": True
                }
            
            # Registrar no histórico
            self.context_manager.add_to_context({
                "timestamp": current_time,
                "type": "system",
                "content": parsed_response["análise"]
            })
            
            # Verificar necessidade de confirmação
            if parsed_response["requer_confirmação"] and require_confirmation:
                confirmation = await self.chat_terminal.request_confirmation(
                    f"Devo executar a ação '{parsed_response['ação']}'? (Risco: {parsed_response['risco']})"
                )
                if not confirmation:
                    return "Operação cancelada pelo usuário."
            
            # Executar comando e registrar resultado
            stdout, stderr = self.linux.run_command(parsed_response["ação"])
            result = stdout if stdout else stderr
            
            self.log_terminal.add_log(
                f"Comando executado: {parsed_response['ação']}\nResultado: {result}",
                "COMMAND"
            )
            
            return result
            
        except Exception as e:
            error_msg = f"Erro ao processar comando: {str(e)}"
            self.log_terminal.add_log(error_msg, "ERROR")
            return error_msg
