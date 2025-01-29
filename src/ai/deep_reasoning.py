from typing import List, Dict, Any
import asyncio
from datetime import datetime
from .rate_limiter import RateLimiter
from ..prompts.deep_reasoning_prompts import PERSPECTIVE_ANALYSIS_PROMPT, SYNTHESIS_PROMPT
import json
import re
import traceback

class DeepReasoning:
    def __init__(self, agent):
        self.agent = agent
        self.config = agent.config.get('deep_reasoning', {})
        self.perspectives = self.config.get('perspectives', {})
        self.activation_triggers = self.config.get('activation_triggers', {})
        self.consecutive_failures = 0
        self.command_history = []
        
        # Verificar se os prompts foram importados corretamente
        if not PERSPECTIVE_ANALYSIS_PROMPT or not SYNTHESIS_PROMPT:
            raise ValueError("Deep Reasoning prompts not properly imported")
            
    def should_activate(self, situation_data: Dict) -> bool:
        """
        Determines if Deep Reasoning should be activated based on:
        1. Debug mode (forces activation)
        2. Explicit request from main agent
        3. Configured triggers from config.yaml
        """
        # First check debug mode
        if self.config.get('debug_mode', False):
            self.agent.terminal.log("Activating Deep Reasoning - Debug mode enabled", "DEBUG")
            return True
        
        # Then check if agent explicitly requested
        if situation_data.get("requires_deep_reasoning", False):
            self.agent.terminal.log("Activating Deep Reasoning - Explicitly requested by agent", "INFO")
            return True
        
        # Then check configured triggers
        triggers = self.activation_triggers
        
        # Check consecutive failures
        if self.consecutive_failures >= triggers.get('consecutive_failures', 2):
            self.agent.terminal.log(
                f"Activating Deep Reasoning - {self.consecutive_failures} consecutive failures",
                "INFO"
            )
            return True
        
        # Check risk level from next_step
        if (triggers.get('high_risk_commands', True) and 
            situation_data.get("next_step", {}).get("risk", "low") == "high"):
            self.agent.terminal.log("Activating Deep Reasoning - High risk command detected", "INFO")
            return True
        
        # Check complexity from reasoning_context
        reasoning_context = situation_data.get('reasoning_context', {})
        if (reasoning_context.get('complexity', 'low') == 'high' or
            reasoning_context.get('impact_scope', 'low') == 'high'):
            self.agent.terminal.log("Activating Deep Reasoning - High complexity/impact detected", "INFO")
            return True
            
        return False
        
    def record_result(self, success: bool):
        """Records success/failure to track consecutive failures"""
        if success:
            self.consecutive_failures = 0
            self.agent.terminal.log(f"Reset consecutive failures counter", "DEBUG")
        else:
            self.consecutive_failures += 1
            self.agent.terminal.log(
                f"Increased consecutive failures to {self.consecutive_failures}", 
                "DEBUG"
            )
            
    async def deep_analyze(self, situation: str, context: str) -> Dict[str, Any]:
        try:
            self.agent.terminal.start_deep_reasoning()
            
            # Log inicial dos parâmetros
            self.agent.terminal.log(
                f"\n{'='*50}\nStarting deep analysis with:\nSituation: {situation}\nContext: {context}\n{'='*50}\n",
                "DEBUG"
            )
            
            perspectives_results = []
            
            for perspective_name, perspective_cfg in self.perspectives.items():
                self.agent.terminal.log_deep_reasoning_step(
                    f"Analyzing with {perspective_name} perspective..."
                )
                
                try:
                    # Log da configuração
                    self.agent.terminal.log(
                        f"\n{'='*50}\nPerspective config for {perspective_name}:\n{json.dumps(perspective_cfg, indent=2)}\n{'='*50}\n",
                        "DEBUG"
                    )
                    
                    original_config = self.agent._temp_configure_model(perspective_cfg)
                    
                    formatted_prompt = PERSPECTIVE_ANALYSIS_PROMPT.format(
                        perspective=perspective_name,
                        situation=str(situation),
                        context=str(context)
                    )
                    
                    response = await self.agent._send_message_with_retry(formatted_prompt)
                    
                    # Log da resposta bruta
                    self.agent.terminal.log(
                        f"\n{'='*50}\nRaw response for {perspective_name}:\n{response}\n{'='*50}\n",
                        "DEBUG"
                    )
                    
                    if not response:
                        raise ValueError(f"Empty response received for {perspective_name}")
                    
                    # Limpar e extrair JSON
                    cleaned = response.strip()
                    cleaned = re.sub(r"```json\s*([\s\S]*?)```", r"\1", cleaned)
                    
                    # Log após limpeza inicial
                    self.agent.terminal.log(
                        f"\n{'='*50}\nCleaned response for {perspective_name}:\n{cleaned}\n{'='*50}\n",
                        "DEBUG"
                    )
                    
                    # Tentar encontrar JSON válido
                    if not cleaned.startswith("{"):
                        start_idx = cleaned.find("{")
                        if start_idx >= 0:
                            cleaned = cleaned[start_idx:]
                            # Log após ajuste do JSON
                            self.agent.terminal.log(
                                f"\n{'='*50}\nAdjusted JSON for {perspective_name}:\n{cleaned}\n{'='*50}\n",
                                "DEBUG"
                            )
                    
                    try:
                        parsed_json = json.loads(cleaned)
                        
                        # Log do JSON parseado
                        self.agent.terminal.log(
                            f"\n{'='*50}\nParsed JSON for {perspective_name}:\n{json.dumps(parsed_json, indent=2)}\n{'='*50}\n",
                            "DEBUG"
                        )
                        
                        # Verificar estrutura do JSON antes de usar
                        if not isinstance(parsed_json, dict):
                            raise ValueError(f"Parsed JSON is not a dictionary: {type(parsed_json)}")
                        
                        # Criar resultado com verificação de tipos
                        perspective_result = {
                            "perspective": perspective_name,
                            "analysis": parsed_json,  # Aqui pode estar o problema
                            "confidence": self._evaluate_confidence(parsed_json)
                        }
                        
                        # Log do resultado final da perspectiva
                        self.agent.terminal.log(
                            f"\n{'='*50}\nPerspective result for {perspective_name}:\n{json.dumps(perspective_result, indent=2)}\n{'='*50}\n",
                            "DEBUG"
                        )
                        
                        perspectives_results.append(perspective_result)
                        
                    except json.JSONDecodeError as je:
                        self.agent.terminal.log(
                            f"\n{'='*50}\nJSON decode error in {perspective_name}:\n"
                            f"Error: {str(je)}\n"
                            f"Position: {je.pos}\n"
                            f"Line: {je.lineno}, Column: {je.colno}\n"
                            f"Document: {je.doc}\n"
                            f"{'='*50}\n",
                            "ERROR"
                        )
                        raise
                        
                except Exception as e:
                    self.agent.terminal.log(
                        f"\n{'='*50}\nError in {perspective_name} analysis:\n"
                        f"Error type: {type(e).__name__}\n"
                        f"Error message: {str(e)}\n"
                        f"Traceback:\n{traceback.format_exc()}\n"
                        f"{'='*50}\n",
                        "ERROR"
                    )
                finally:
                    if original_config is not None:
                        self._restore_model_config(original_config)
            
            # Continue with available results
            if perspectives_results:
                self.agent.terminal.log_deep_reasoning_step("Synthesizing perspectives...")
                try:
                    final_analysis = await self._synthesize_perspectives(perspectives_results, situation)
                    return final_analysis
                except Exception as e:
                    error_log = (
                        f"\n{'='*50}\n"
                        f"Error in synthesis:\n"
                        f"Error type: {type(e).__name__}\n"
                        f"Error details: {str(e)}\n"
                        f"Full error: {repr(e)}\n\n"
                        f"Available perspectives:\n{json.dumps(perspectives_results, indent=2)}\n"
                        f"{'='*50}\n"
                    )
                    self.agent.terminal.log(error_log, "ERROR")
                    return {
                        "type": "analysis",
                        "message": "Partial analysis completed with some errors",
                        "analysis": str(perspectives_results),
                        "next_step": {
                            "action": "continue",
                            "risk": "medium",
                            "requires_confirmation": True
                        }
                    }
            
            return {
                "type": "response",
                "message": "Deep analysis encountered errors but will continue with standard processing",
                "next_step": {
                    "action": "continue",
                    "risk": "medium",
                    "requires_confirmation": True
                }
            }
            
        finally:
            self.agent.terminal.stop_processing()
    
    def _temp_configure_model(self, config: Dict) -> Dict:
        """
        Temporarily configures the model with new parameters
        Uses agent's model configuration methods
        """
        # Use agent's configuration method
        return self.agent._temp_configure_model({
            "temperature": config.get("temperature", 0.5),
            "top_p": config.get("top_p", 0.7),
            "top_k": config.get("top_k", 40)
        })
    
    def _restore_model_config(self, original_config: Dict):
        """
        Restores the original model configuration
        Uses agent's model configuration methods
        """
        # Use agent's restore method
        self.agent._restore_model_config(original_config)
    
    def _evaluate_confidence(self, response: Dict) -> float:
        """
        Avalia o nível de confiança da análise baseado em diversos fatores
        """
        # Log do que está sendo avaliado
        self.agent.terminal.log(
            f"\n{'='*50}\nEvaluating confidence for response:\n{json.dumps(response, indent=2)}\n{'='*50}\n",
            "DEBUG"
        )
        try:
            # Implementar lógica de avaliação de confiança
            return response.get("confidence_level", 0.7)
        except Exception as e:
            self.agent.terminal.log(f"Error evaluating confidence: {str(e)}", "ERROR")
            return 0.5
            
    def _extract_json(self, text: str) -> str:
        """Extract JSON from text, handling various formats"""
        # Remove leading/trailing whitespace
        text = text.strip()
        
        # Find JSON boundaries
        start = text.find('{')
        end = text.rfind('}') + 1
        
        if start >= 0 and end > 0:
            return text[start:end]
        
        raise ValueError("No valid JSON found in response")
    
    async def _synthesize_perspectives(self, perspectives_results: List[Dict], situation: str) -> Dict:
        """
        Synthesizes different perspectives into a final analysis
        """
        synthesis_prompt = self._create_synthesis_prompt(perspectives_results, situation)
        
        try:
            response = await self.agent._send_message_with_retry(synthesis_prompt)
            clean_text = re.sub(r"```json\s*([\s\S]*?)```", r"\1", response)
            clean_text = clean_text.strip()
            
            # Tenta encontrar o JSON válido na resposta
            if not clean_text.startswith("{"):
                start = clean_text.find("{")
                if start >= 0:
                    clean_text = clean_text[start:]
            
            try:
                return json.loads(clean_text)
            except json.JSONDecodeError:
                # Se falhar, retorna um formato válido com a resposta como string
                return {
                    "type": "analysis",
                    "message": "Synthesis completed with parsing errors",
                    "analysis": clean_text,
                    "next_step": {
                        "action": "continue",
                        "risk": "medium",
                        "requires_confirmation": True
                    }
                }
            
        except Exception as e:
            self.agent.terminal.log(f"Error in synthesis: {str(e)}", "ERROR")
            return {
                "type": "response",
                "message": f"Synthesis error: {str(e)}",
                "next_step": {
                    "action": "continue",
                    "risk": "medium",
                    "requires_confirmation": True
                }
            }
    
    def _create_synthesis_prompt(self, perspectives_results: List[Dict], situation: str) -> str:
        """
        Cria o prompt para sintetizar as diferentes perspectivas
        """
        return f"""Analise rigorosamente as perspectivas abaixo seguindo ESTRITAMENTE o formato solicitado.

Situação: {situation}

Perspectivas disponíveis:
{self._format_perspectives(perspectives_results)}

Seu DEVER é:
1. Combinar análises mantendo a estrutura JSON
2. Listar passos executáveis
3. Manter a sintaxe JSON válida
4. Usar apenas aspas duplas
5. Números sem aspas

Formato OBRIGATÓRIO:
{{
    "final_analysis": "Resumo conciso",
    "selected_approach": "Abordagem escolhida",
    "action_plan": ["Passo 1", "Passo 2", "Passo 3"],
    "risk_assessment": "Avaliação de risco final",
    "confidence_score": 75
}}"""

    def _format_perspectives(self, perspectives_results: List[Dict]) -> str:
        """
        Formata as perspectivas para inclusão no prompt de síntese
        """
        formatted = []
        for p in perspectives_results:
            formatted.append(f"Perspectiva {p['perspective']}:\n{p['analysis']}\n")
        return "\n".join(formatted)

    def _validate_json(self, json_str: str) -> Dict:
        """
        Validate and clean JSON string with multiple fallbacks
        """
        try:
            # First try direct parse
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            # Try removing markdown
            clean_text = re.sub(r"```json\s*([\s\S]*?)```", r"\1", json_str)
            clean_text = clean_text.strip()
            
            # Try fixing common issues
            clean_text = clean_text.replace("'", '"')  # Replace single quotes
            clean_text = re.sub(r"(\w+):", r'"\1":', clean_text)  # Add quotes to keys
            clean_text = re.sub(r":\s*(\w+)([,\}])", r':"\1"\2', clean_text)  # Add quotes to unquoted values
            
            try:
                return json.loads(clean_text)
            except json.JSONDecodeError:
                # If still failing, try to extract valid JSON portion
                start = clean_text.find('{')
                end = clean_text.rfind('}') + 1
                if start >= 0 and end > 0:
                    try:
                        return json.loads(clean_text[start:end])
                    except json.JSONDecodeError:
                        pass
                    
                # If all else fails, return error structure
                return {
                    "error": "Invalid JSON format",
                    "original": json_str[:100] + "..." if len(json_str) > 100 else json_str
                }