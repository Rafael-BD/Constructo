from typing import List, Dict, Any
import asyncio
from datetime import datetime
from ai.rate_limiter import RateLimiter
from prompts.deep_reasoning_prompts import PERSPECTIVE_ANALYSIS_PROMPT, SYNTHESIS_PROMPT, get_synthesis_prompt
import json
import re
import traceback
import google.generativeai as genai


class DeepReasoning:
    def __init__(self, agent):
        """Initialize Deep Reasoning with agent configuration"""
        self.agent = agent
        self.config = agent.config.get('deep_reasoning', {})
        self.perspectives = self.config.get('perspectives', {})
        self.activation_triggers = self.config.get('activation_triggers', {})
        self.consecutive_failures = 0
        self.command_history = []
        self.language = agent.config.get('agent', {}).get('language', 'en-US')
        
        # Create separate model for Deep Reasoning but use the same rate limiter
        self.model = genai.GenerativeModel(
            self.agent.config.get('model', {}).get('name', 'gemini-2.0-flash-exp')
        )
        # Use agent's rate limiter
        self.rate_limiter = self.agent.rate_limiter
        
        # Check if prompts were imported correctly
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
            return True
        
        # Then check configured triggers
        triggers = self.activation_triggers
        
        # Check consecutive failures
        if self.consecutive_failures >= triggers.get('consecutive_failures', 2):
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
        else:
            self.consecutive_failures += 1
            
    async def _send_message(self, prompt: str, config: Dict = None) -> str:
        """Send message using dedicated Deep Reasoning model"""
        max_attempts = self.agent.retry_config.get('max_attempts', 3)
        retry_delay = self.agent.retry_config.get('delay_between_retries', 10)
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                await self.rate_limiter.wait_if_needed_async()
                
                if config:
                    generation_config = genai.GenerationConfig(**config)
                else:
                    generation_config = self.agent.generation_config
                
                response = self.model.generate_content(
                    prompt,
                    generation_config=generation_config
                )
                
                if response and response.text:
                    return response.text
                raise ValueError("Empty response from API")
                
            except Exception as e:
                last_error = e
                error_msg = str(e)
                
                if "429" in error_msg or "quota" in error_msg.lower():
                    if attempt < max_attempts - 1:
                        self.agent.terminal.log(
                            f"Rate limit reached in Deep Reasoning. Waiting {retry_delay}s before retry {attempt + 1}/{max_attempts}",
                            "WARNING"
                        )
                        await asyncio.sleep(retry_delay)
                        continue
                elif attempt < max_attempts - 1:
                    self.agent.terminal.log(
                        f"Deep Reasoning API error: {error_msg}. Retrying {attempt + 1}/{max_attempts}...",
                        "WARNING"
                    )
                    await asyncio.sleep(1)
                    continue
                
        raise last_error or Exception("Maximum retry attempts reached")

    async def deep_analyze(self, situation: str, context: str) -> Dict[str, Any]:
        try:
            self.agent.terminal.start_deep_reasoning()
            perspectives_results = []
            
            for perspective_name, perspective_cfg in self.perspectives.items():
                self.agent.terminal.log_deep_reasoning_step(
                    f"Analyzing with {perspective_name} perspective..."
                )
                
                try:
                    formatted_prompt = PERSPECTIVE_ANALYSIS_PROMPT.format(
                        perspective=perspective_name,
                        situation=str(situation),
                        context=str(context)
                    )
                    
                    response = await self._send_message(formatted_prompt, perspective_cfg)
                    
                    if not response:
                        raise ValueError(f"Empty response received for {perspective_name}")
                    
                    # Log perspective
                    self.agent.terminal._save_to_file({
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                        "type": f"PERSPECTIVE_{perspective_name.upper()}",
                        "content": response
                    })
                    
                    perspective_result = {
                        "perspective": perspective_name,
                        "analysis": response
                    }
                    
                    perspectives_results.append(perspective_result)
                    
                except Exception as e:
                    self.agent.terminal.log(
                        f"Error in {perspective_name} analysis: {str(e)}", 
                        "ERROR"
                    )
            
            # Continue with available results
            if perspectives_results:
                self.agent.terminal.log_deep_reasoning_step("Synthesizing perspectives...")
                try:
                    final_analysis = await self._synthesize_perspectives(perspectives_results, situation)
                    
                    # Log final synthesis
                    self.agent.terminal._save_to_file({
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                        "type": "DEEP_REASONING_SYNTHESIS",
                        "content": final_analysis["analysis"]
                    })
                    
                    # Return analysis without message to terminal
                    return {
                        "type": "analysis",
                        "analysis": final_analysis["analysis"],
                        "next_step": None
                    }
                    
                except Exception as e:
                    error_log = f"Error in synthesis: {str(e)}"
                    self.agent.terminal.log(error_log, "ERROR")
                    return {
                        "type": "analysis",
                        "message": "Based on this deep reasoning synthesis, please analyze and suggest the next steps.",
                        "analysis": str(perspectives_results),
                        "next_step": None
                    }
            
            return {
                "type": "response",
                "message": "Based on the deep analysis performed, please evaluate the results and determine the best action to take.",
                "next_step": None
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
        Synthesizes different perspectives into a final analysis with streaming
        """
        synthesis_prompt = self._create_synthesis_prompt(perspectives_results, situation)
        
        try:
            # Stop the spinner before starting synthesis
            self.agent.terminal.stop_processing()
            
            # Start synthesis streaming with line break
            self.agent.terminal.log("\nThinking through all perspectives...", "DIM", show_timestamp=False)
            await asyncio.sleep(0.5)  # Pause for visual separation
            
            # Use shared rate limiter
            await self.rate_limiter.wait_if_needed_async()
            
            response = self.model.generate_content(
                synthesis_prompt,
                stream=True,
                generation_config=self.agent.generation_config
            )
            
            full_response = ""
            current_line = ""
            buffer = ""
            last_char = " "
            
            for chunk in response:
                if hasattr(chunk, 'text') and chunk.text:
                    text = chunk.text.replace('\r', '')  # Remove carriage returns
                    
                    # Remove duplicate lines
                    if text in full_response:
                        continue
                        
                    full_response += text
                    
                    # Process text character by character
                    for char in text:
                        buffer += char
                        
                        # Handle line breaks
                        if char == '\n':
                            if buffer.strip() and buffer.strip() not in current_line:
                                if current_line:
                                    self.agent.terminal.log(current_line.rstrip(), "DIM", show_timestamp=False)
                                current_line = buffer
                                buffer = ""
                                await asyncio.sleep(0.02)
                        # Handle sentence endings
                        elif char in ['.', '!', '?'] and last_char not in ['.', '!', '?']:
                            self.agent.terminal.log(buffer, "DIM", show_timestamp=False, end="")
                            buffer = ""
                            await asyncio.sleep(0.1)
                        # Handle other punctuation
                        elif char in [',', ';', ':'] and last_char not in [',', ';', ':']:
                            self.agent.terminal.log(buffer, "DIM", show_timestamp=False, end="")
                            buffer = ""
                            await asyncio.sleep(0.05)
                        # Regular character printing
                        elif len(buffer) > 2:  # Print in small word chunks
                            self.agent.terminal.log(buffer, "DIM", show_timestamp=False, end="")
                            buffer = ""
                            await asyncio.sleep(0.01)
                        
                        last_char = char
            
            # Print any remaining text
            if buffer.strip():
                self.agent.terminal.log(buffer.rstrip(), "DIM", show_timestamp=False)
            if current_line.strip():
                self.agent.terminal.log(current_line.rstrip(), "DIM", show_timestamp=False)
            
            # Add final line break
            self.agent.terminal.log("", show_timestamp=False)
            
            return {
                "type": "analysis",
                "analysis": full_response,
                "next_step": None
            }
            
        except Exception as e:
            error_msg = f"\nError in synthesis: {str(e)}"
            self.agent.terminal.log(error_msg, "ERROR")
            
            error_response = "Based on the deep analysis performed, please evaluate the results and determine the next action."
            
            return {
                "type": "response",
                "message": error_response,
                "next_step": None
            }
    
    def _create_synthesis_prompt(self, perspectives_results: List[Dict], situation: str) -> str:
        """Creates the prompt to synthesize different perspectives"""
        return get_synthesis_prompt(self.language).format(
            situation=situation,
            perspectives=self._format_perspectives(perspectives_results)
        )

    def _format_perspectives(self, perspectives_results: List[Dict]) -> str:
        """
        Formats perspectives for inclusion in synthesis prompt
        """
        formatted = []
        for p in perspectives_results:
            formatted.append(f"Perspective {p['perspective']}:\n{p['analysis']}\n")
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