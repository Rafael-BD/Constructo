import google.generativeai as genai
import json
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
            self.terminal.log(f"Processando comando: {user_input}", "INPUT")
            
            # Preparar mensagem com contexto atual
            context = self.context_manager.get_current_context()
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Formatar mensagem para o modelo
            prompt = f"""Contexto atual: {context}
Comando do usuário: {user_input}
Timestamp: {current_time}

Analise o comando e responda no formato JSON especificado no prompt do sistema."""
            
            # Enviar mensagem e obter resposta
            response = self.chat.send_message(prompt)
            response_text = response.text if response else None
            
            if response_text is None:
                raise ValueError("Received empty response from the chat model.")
            
            try:
                # Tentar encontrar o JSON na resposta
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                if json_start >= 0 and json_end > 0:
                    json_str = response_text[json_start:json_end]
                    parsed_response = json.loads(json_str)
                else:
                    raise json.JSONDecodeError("No JSON found", response_text, 0)
                    
            except json.JSONDecodeError:
                # Fallback para comando simples
                parsed_response = {
                    "análise": "Processando comando direto",
                    "ação": user_input,
                    "risco": "médio",
                    "requer_confirmação": True
                }
            
            # Registrar no histórico
            self.context_manager.add_to_context({
                "timestamp": current_time,
                "type": "system",
                "content": parsed_response.get("análise", "Análise não disponível")
            })
            
            # Verificar necessidade de confirmação
            if parsed_response.get("requer_confirmação", True) and require_confirmation:
                confirmation = await self.terminal.request_confirmation(
                    f"Devo executar a ação '{parsed_response.get('ação', 'Ação não disponível')}'? (Risco: {parsed_response.get('risco', 'desconhecido')})"
                )
                if not confirmation:
                    return "Operação cancelada pelo usuário."
            
            # Executar comando e registrar resultado
            self.terminal.log(f"Executando comando: {parsed_response.get('ação', '')}", "EXEC")
            stdout, stderr = self.linux.run_command(parsed_response.get("ação", ""))
            result = stdout if stdout else stderr
            
            # Registrar resultado no contexto
            self.context_manager.add_to_context({
                "timestamp": current_time,
                "type": "output",
                "content": result
            })
            
            self.terminal.log(f"Resultado do comando:\n{result}", "OUTPUT")
            
            return result
            
        except Exception as e:
            error_msg = f"Erro ao processar comando: {str(e)}"
            self.terminal.log(error_msg, "ERROR")
            return error_msg
