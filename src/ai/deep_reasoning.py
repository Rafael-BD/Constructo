from typing import List, Dict, Any
import asyncio
from datetime import datetime
from .rate_limiter import RateLimiter
from ..prompts.deep_reasoning_prompts import PERSPECTIVE_ANALYSIS_PROMPT, SYNTHESIS_PROMPT
import json
import re

class DeepReasoning:
    def __init__(self, agent):
        self.agent = agent
        self.config = agent.config.get('deep_reasoning', {})
        self.perspectives = self.config.get('perspectives', {})
        self.activation_triggers = self.config.get('activation_triggers', {})
        self.consecutive_failures = 0
        self.command_history = []
        
    def should_activate(self, situation_data: Dict) -> bool:
        """
        Determines if Deep Reasoning should be activated based on multiple factors:
        
        1. Consecutive Failures:
           - Tracks failed commands/operations
           - Activates after N consecutive failures (default: 2)
        
        2. Command Risk Level:
           - Analyzes command risk (none/low/medium/high)
           - Automatically activates for high-risk commands
           - Considers command type and potential impact
        
        3. Situation Complexity:
           - Evaluates based on:
             * Number of steps in action plan
             * Dependencies between actions
             * Required privilege level
             * Potential impact scope
        
        4. Confidence Levels:
           - Monitors agent's confidence in decisions
           - Activates when confidence drops below threshold
           - Considers historical confidence trend
        
        5. Pattern Recognition:
           - Analyzes command history patterns
           - Identifies repeated failed approaches
           - Detects circular/ineffective strategies
        """
        # 1. Check consecutive failures
        if self._check_consecutive_failures():
            self.agent.terminal.log("Activating Deep Reasoning due to consecutive failures", "INFO")
            return True
            
        # 2. Analyze command risk level
        if self._check_risk_level(situation_data):
            self.agent.terminal.log("Activating Deep Reasoning due to high risk command", "INFO")
            return True
            
        # 3. Evaluate situation complexity
        if self._check_situation_complexity(situation_data):
            self.agent.terminal.log("Activating Deep Reasoning due to situation complexity", "INFO")
            return True
            
        # 4. Monitor confidence levels
        if self._check_confidence_levels(situation_data):
            self.agent.terminal.log("Activating Deep Reasoning due to low confidence", "INFO")
            return True
            
        # 5. Analyze command patterns
        if self._check_command_patterns(situation_data):
            self.agent.terminal.log("Activating Deep Reasoning due to detected pattern issues", "INFO")
            return True
            
        return False
        
    def _check_consecutive_failures(self) -> bool:
        """Checks if consecutive failures threshold is reached"""
        threshold = self.activation_triggers.get('consecutive_failures', 2)
        return self.consecutive_failures >= threshold
        
    def _check_risk_level(self, situation_data: Dict) -> bool:
        """Analyzes command risk level and type"""
        if not self.activation_triggers.get('high_risk_commands', True):
            return False
            
        risk_level = situation_data.get('risk_level', 'low').lower()
        command_type = situation_data.get('command_type', '')
        
        # High risk commands that always trigger deep reasoning
        high_risk_commands = ['rm', 'chmod', 'chown', 'dd', 'mkfs']
        
        return (
            risk_level == 'high' or
            any(cmd in command_type for cmd in high_risk_commands)
        )
        
    def _check_situation_complexity(self, situation_data: Dict) -> bool:
        """Evaluates situation complexity based on multiple factors"""
        if not self.activation_triggers.get('complex_situations', True):
            return False
            
        complexity_score = 0
        
        # Check number of steps in action plan
        action_plan = situation_data.get('action_plan', [])
        if len(action_plan) > 3:
            complexity_score += 1
            
        # Check for elevated privileges requirement
        if situation_data.get('requires_privileges', False):
            complexity_score += 1
            
        # Check impact scope
        impact_scope = situation_data.get('impact_scope', 'low')
        if impact_scope in ['medium', 'high']:
            complexity_score += 1
            
        return complexity_score >= 2
        
    def _check_confidence_levels(self, situation_data: Dict) -> bool:
        """Monitors confidence levels and trends"""
        threshold = self.activation_triggers.get('low_confidence', 0.6)
        current_confidence = situation_data.get('confidence', 1.0)
        
        return current_confidence < threshold
        
    def _check_command_patterns(self, situation_data: Dict) -> bool:
        """Analyzes command history for problematic patterns"""
        # Add command to history
        self.command_history.append(situation_data)
        
        # Keep only last 10 commands
        if len(self.command_history) > 10:
            self.command_history.pop(0)
            
        # Check for repeated failed commands
        command_counts = {}
        for cmd in self.command_history[-5:]:  # Look at last 5 commands
            command = cmd.get('command', '')
            if command:
                command_counts[command] = command_counts.get(command, 0) + 1
                
        # If same command tried more than twice recently
        return any(count > 2 for count in command_counts.values())
        
    def record_result(self, success: bool):
        """
        Records success/failure to track consecutive failures
        """
        if success:
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1
            
    async def deep_analyze(self, situation: str, context: str) -> Dict[str, Any]:
        try:
            self.agent.terminal.start_deep_reasoning()
            
            perspectives_results = []
            
            for perspective_name, perspective_cfg in self.perspectives.items():
                self.agent.terminal.log_deep_reasoning_step(
                    f"Analyzing with {perspective_name} perspective..."
                )
                
                original_config = None
                try:
                    # Salvar config anterior
                    original_config = self.agent._temp_configure_model(perspective_cfg)
                    
                    prompt = PERSPECTIVE_ANALYSIS_PROMPT.format(
                        perspective=perspective_name,
                        situation=situation,
                        context=context
                    )
                    
                    response = await self.agent._send_message_with_retry(prompt)
                    
                    # Limpar e extrair JSON removendo quebras de linha extras
                    cleaned = response.strip()
                    cleaned = re.sub(r"```json\s*([\s\S]*?)```", r"\1", cleaned)
                    
                    if not cleaned:
                        self.agent.terminal.log(
                            f"Empty response for {perspective_name}", "WARNING"
                        )
                        continue
                    
                    # DEBUG log para analisar resposta bruta
                    self.agent.terminal.log(
                        f"Raw response for {perspective_name}: {cleaned}",
                        "DEBUG"
                    )
                    
                    # Caso o JSON não comece corretamente, tentar buscar primeira chave
                    if not cleaned.startswith("{"):
                        start_idx = cleaned.find("{")
                        if start_idx >= 0:
                            cleaned = cleaned[start_idx:]
                    
                    try:
                        parsed_json = json.loads(cleaned)
                        perspectives_results.append({
                            "perspective": perspective_name,
                            "analysis": parsed_json,
                            "confidence": self._evaluate_confidence(parsed_json)
                        })
                    except json.JSONDecodeError as je:
                        # Log mais detalhado em caso de erro de parse
                        self.agent.terminal.log(
                            f"JSONDecodeError in {perspective_name} analysis: {str(je)}",
                            "ERROR"
                        )
                        self.agent.terminal.log(
                            f"Failed JSON: {cleaned[:200]}...", 
                            "DEBUG"
                        )
                        
                except Exception as e:
                    self.agent.terminal.log(
                        f"Error in {perspective_name} analysis: {str(e)}", "ERROR"
                    )
                finally:
                    # Restaurar config se existir
                    if original_config is not None:
                        self._restore_model_config(original_config)
            
            # Continue with available results
            if perspectives_results:
                self.agent.terminal.log_deep_reasoning_step("Synthesizing perspectives...")
                try:
                    final_analysis = await self._synthesize_perspectives(perspectives_results, situation)
                    return final_analysis
                except Exception as e:
                    self.agent.terminal.log(f"Error in synthesis: {str(e)}", "ERROR")
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
    
    def _evaluate_confidence(self, response: str) -> float:
        """
        Avalia o nível de confiança da análise baseado em diversos fatores
        """
        try:
            # Implementar lógica de avaliação de confiança
            # Por enquanto retorna um valor padrão
            return 0.7
        except:
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