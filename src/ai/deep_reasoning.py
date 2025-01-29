from typing import List, Dict, Any
import asyncio
from datetime import datetime
from .rate_limiter import RateLimiter
from ..prompts.deep_reasoning_prompts import PERSPECTIVE_ANALYSIS_PROMPT, SYNTHESIS_PROMPT

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
        """
        Performs deep analysis using multiple perspectives
        """
        # Start deep reasoning visualization
        self.agent.terminal.start_deep_reasoning()
        
        perspectives_results = []
        for perspective_name, config in self.perspectives.items():
            self.agent.terminal.log_deep_reasoning_step(f"Analyzing with {perspective_name} perspective...")
            
            original_config = self._temp_configure_model(config)
            
            prompt = PERSPECTIVE_ANALYSIS_PROMPT.format(
                perspective=perspective_name,
                situation=situation,
                context=context
            )
            
            try:
                response = await self.agent._send_message_with_retry(prompt)
                perspectives_results.append({
                    "perspective": perspective_name,
                    "analysis": response,
                    "confidence": self._evaluate_confidence(response)
                })
            except Exception as e:
                self.agent.terminal.log(f"Error in {perspective_name} analysis: {str(e)}", "ERROR")
            
            self._restore_model_config(original_config)
        
        self.agent.terminal.log_deep_reasoning_step("Synthesizing perspectives...")
        final_analysis = await self._synthesize_perspectives(perspectives_results, situation)
        
        # Stop deep reasoning visualization
        self.agent.terminal.stop_processing()
        
        return final_analysis
    
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
            
    async def _synthesize_perspectives(self, perspectives_results: List[Dict], situation: str) -> Dict:
        """
        Sintetiza as diferentes perspectivas em uma análise final
        """
        synthesis_prompt = self._create_synthesis_prompt(perspectives_results, situation)
        
        try:
            final_analysis = await self.agent._send_message_with_retry(synthesis_prompt)
            return final_analysis
        except Exception as e:
            self.agent.terminal.log(f"Erro na síntese final: {str(e)}", "ERROR")
            return {
                "error": str(e),
                "partial_results": perspectives_results
            }
    
    def _create_synthesis_prompt(self, perspectives_results: List[Dict], situation: str) -> str:
        """
        Cria o prompt para sintetizar as diferentes perspectivas
        """
        return f"""Analise e sintetize as seguintes perspectivas para a situação:

Situação: {situation}

Perspectivas:
{self._format_perspectives(perspectives_results)}

Forneça uma análise final que:
1. Combine os insights mais valiosos de cada perspectiva
2. Identifique a melhor abordagem considerando risco vs. benefício
3. Proponha um plano de ação concreto

Responda em formato JSON com:
{{
    "final_analysis": "análise combinada",
    "selected_approach": "abordagem escolhida",
    "action_plan": ["passos detalhados"],
    "risk_assessment": "avaliação final de risco",
    "confidence_score": "0-100"
}}"""

    def _format_perspectives(self, perspectives_results: List[Dict]) -> str:
        """
        Formata as perspectivas para inclusão no prompt de síntese
        """
        formatted = []
        for p in perspectives_results:
            formatted.append(f"Perspectiva {p['perspective']}:\n{p['analysis']}\n")
        return "\n".join(formatted) 