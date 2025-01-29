import asyncio
import google.generativeai as genai
from google.api_core import retry
import time
import json
import re 
from datetime import datetime
from ..core.terminal import UnifiedTerminal
from ..core.linux_interaction import LinuxInteraction
from ..prompts.main_context import SYSTEM_PROMPT
from .context_manager import ContextManager
from .rate_limiter import RateLimiter
from .deep_reasoning import DeepReasoning
from typing import Dict

class AIAgent:
    def __init__(self, config: dict):
        self.config = config
        self.chat = self._initialize_chat()
        self.terminal = UnifiedTerminal()
        self.linux = LinuxInteraction()
        self.context_manager = ContextManager()
        
        # Initialize rate limiter
        api_config = config.get('api', {}).get('rate_limit', {})
        self.rate_limiter = RateLimiter(
            requests_per_minute=api_config.get('requests_per_minute', 30),
            delay_between_requests=api_config.get('delay_between_requests', 0.5)
        )
        
        # Retry configuration
        self.retry_config = config.get('api', {}).get('retry', {})
        
        # Risk level weights for comparison
        self.risk_levels = {
            "none": 0,
            "low": 1,
            "medium": 2,
            "high": 3
        }
        
        self.deep_reasoning = DeepReasoning(self)
        
        # Set default balanced configuration
        model_config = config.get('model', {}).get('default_config', {})
        self.default_config = {
            "temperature": model_config.get('temperature', 0.5),
            "top_p": model_config.get('top_p', 0.7),
            "top_k": model_config.get('top_k', 40)
        }
        
        # Store original config before applying default balanced configuration
        self.original_config = self._temp_configure_model(self.default_config)
        
    def _initialize_chat(self):
        genai.configure(api_key=self.config['api_key'])
        
        # Get model configuration
        model_config = self.config.get('model', {})
        default_config = model_config.get('default_config', {})
        
        # Store configuration for later use
        self.generation_config = genai.GenerationConfig(
            temperature=default_config.get('temperature', 0.5),
            top_p=default_config.get('top_p', 0.7),
            top_k=default_config.get('top_k', 40),
            max_output_tokens=model_config.get('max_output_tokens', 8096),
        )
        
        # Create model with initial config
        self.model = genai.GenerativeModel(
            model_config.get('name', 'gemini-2.0-flash-exp'),
            generation_config=self.generation_config
        )
        
        # Start chat session
        return self.model.start_chat(history=[
            {"role": "user", "parts": [SYSTEM_PROMPT]},
            {"role": "model", "parts": ["System initialized with instructions. Ready to execute commands."]}
        ])
        
    def _needs_confirmation(self, risk_level: str) -> bool:
        """Determine if an action needs user confirmation based on config"""
        security_config = self.config.get('security', {})
        
        # If confirmations are disabled globally
        if not security_config.get('require_confirmation', True):
            return False
            
        # Get configured risk threshold
        threshold = security_config.get('risk_threshold', 'medium').lower()
        
        # Compare risk levels
        action_risk = self.risk_levels.get(risk_level.lower(), 0)
        threshold_risk = self.risk_levels.get(threshold, 2)  # default to medium
        
        return action_risk > threshold_risk
        
    async def _send_message_with_retry(self, message: str) -> str:
        """Send message to API with retry logic"""
        max_attempts = self.retry_config.get('max_attempts', 3)
        retry_delay = self.retry_config.get('delay_between_retries', 10)
        last_error = None
        
        for attempt in range(max_attempts):
            try:
                self.rate_limiter.wait_if_needed()
                response = self.chat.send_message(message)
                if response and response.text:
                    return response.text
                raise ValueError("Empty response from API")
                
            except Exception as e:
                last_error = e
                error_msg = str(e)
                
                if "429" in error_msg or "quota" in error_msg.lower():
                    if attempt < max_attempts - 1:
                        self.terminal.log(
                            f"Rate limit reached. Waiting {retry_delay}s before retry {attempt + 1}/{max_attempts}",
                            "WARNING"
                        )
                        await asyncio.sleep(retry_delay)  # Use asyncio.sleep instead of time.sleep
                        continue
                elif attempt < max_attempts - 1:
                    self.terminal.log(
                        f"API error: {error_msg}. Retrying {attempt + 1}/{max_attempts}...",
                        "WARNING"
                    )
                    await asyncio.sleep(1)
                    continue
                
        raise last_error or Exception("Maximum retry attempts reached")
        
    async def process_command(self, user_input: str):
        try:
            context = self.context_manager.get_current_context()
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Start thinking spinner
            self.terminal.start_processing()
            
            prompt = f"""Current context: {context}
            User command: {user_input}
            Timestamp: {current_time}
            
            Analyze the input and respond in the specified JSON format."""
            
            # Use retry logic for API calls
            response_text = await self._send_message_with_retry(prompt)
            
            if not response_text:
                raise ValueError("Received empty response from the chat model.")
            
            # Stop spinner and clear
            self.terminal.stop_processing()
            
            async def execute_step(parsed_response):
                try:
                    # Check if deep reasoning is requested by the agent
                    if parsed_response.get("requires_deep_reasoning", False):
                        reasoning_context = parsed_response.get("reasoning_context", {})
                        deep_analysis = await self.deep_reasoning.deep_analyze(
                            reasoning_context.get("situation", user_input),
                            self.context_manager.get_current_context()
                        )
                        # Merge deep analysis results with original response
                        parsed_response.update({
                            "analysis": deep_analysis.get("final_analysis"),
                            "next_step": {
                                "action": deep_analysis.get("selected_approach"),
                                "risk": deep_analysis.get("risk_assessment", "medium"),
                                "requires_confirmation": True
                            }
                        })
                    
                    # Check automatic triggers for deep reasoning
                    elif self.deep_reasoning.should_activate(parsed_response):
                        deep_analysis = await self.deep_reasoning.deep_analyze(
                            user_input,
                            self.context_manager.get_current_context()
                        )
                        # Update response with deep analysis results
                        parsed_response.update(deep_analysis)
                    
                    # Continue with normal execution
                    response_text = parsed_response.get("message") or parsed_response.get("analysis") or ""
                    should_continue = parsed_response.get("continue", False)
                    
                    if response_text:
                        self.terminal.log_agent(response_text)

                    if "next_step" not in parsed_response or not parsed_response["next_step"].get("action"):
                        return response_text, should_continue

                    action = parsed_response["next_step"]
                    risk = action.get("risk", "medium").lower()
                    
                    if action.get("requires_confirmation", True) and self._needs_confirmation(risk):
                        confirmation = await self.terminal.request_confirmation(
                            f"Should I execute the action '{action['action']}'? "
                            f"(Risk: {risk})"
                        )
                        if not confirmation:
                            return "Operation canceled by user.", False

                    self.terminal.log(f"Executing: {action['action']}", "EXEC")
                    stdout, stderr, returncode = self.linux.run_command(action['action'])

                    # Combine output and handle empty results better
                    outputs = []
                    if stdout.strip():
                        outputs.append(stdout.strip())
                    if stderr.strip():
                        outputs.append(stderr.strip())
                    
                    combined_result = "\n".join(outputs)
                    
                    # Always add to context, even if empty or error
                    context_entry = {
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "type": "output" if returncode == 0 else "error",
                        "content": combined_result or f"Command completed with code {returncode}"
                    }
                    self.context_manager.add_to_context(context_entry)

                    if returncode != 0:
                        error_msg = f"Command returned code {returncode}: {stderr.strip() if stderr else 'No error message'}"
                        self.terminal.log(error_msg, "ERROR")

                        # Continue mesmo após o erro para permitir resposta ao usuário
                        combined_result = error_msg

                    if combined_result:
                        self.terminal.log(combined_result, "OUTPUT", show_timestamp=False)

                    # Always continue if flagged, even with empty result
                    if should_continue:
                        self.terminal.log("Analyzing result...", "INFO")
                        next_response_text = await self._send_message_with_retry(
                            f"""Analyze this result and decide the next step.
                            Command: {action['action']}
                            Return code: {returncode}
                            Output: {combined_result}"""
                        )
                        
                        if next_response_text:
                            try:
                                clean_text = re.sub(r"```json\s*([\s\S]*?)```", r"\1", next_response_text)
                                next_parsed = json.loads(_extract_json(clean_text))
                                return await execute_step(next_parsed)
                            except json.JSONDecodeError:
                                return clean_text.strip(), False
                            except Exception as e:
                                self.terminal.log(f"Error in continuation: {str(e)}", "ERROR")
                                return str(e), False

                    # Record success/failure for deep reasoning
                    self.deep_reasoning.record_result(success=(returncode == 0))
                    
                    return response_text, should_continue
                    
                except Exception as e:
                    self.terminal.log(f"Error in execute_step: {str(e)}", "ERROR")
                    self.deep_reasoning.record_result(success=False)
                    return str(e), False

            def _extract_json(text: str) -> str:
                start = text.find('{')
                end = text.rfind('}') + 1
                if start >= 0 and end > 0:
                    return text[start:end]
                return text

            async def process_response(response_text: str):
                try:
                    clean_text = re.sub(r"```json\s*([\s\S]*?)```", r"\1", response_text)
                    json_str = _extract_json(clean_text)
                    parsed = json.loads(json_str)
                    
                    result, should_continue = await execute_step(parsed)
                    
                    if should_continue and result: 
                        return await process_response(result)
                    return result
                except json.JSONDecodeError:
                    return clean_text.strip()
                except Exception as e:
                    self.terminal.log(f"Error in process_response: {str(e)}", "ERROR")
                    return str(e)

            final_result = await process_response(response_text)
            # If final_result is empty, do not display "Processing completed."
            return final_result.strip() if final_result else ""

        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self.terminal.log(error_msg, "ERROR")
            return error_msg

    async def _analyze_with_deep_reasoning(self, situation: str) -> Dict:
        """
        Ativa o módulo de Deep Reasoning para análise profunda
        """
        context = self.context_manager.get_current_context()
        return await self.deep_reasoning.deep_analyze(situation, context)

    def _temp_configure_model(self, config: Dict) -> Dict:
        """
        Temporarily configures the model with new parameters and returns original configuration
        """
        original_config = {
            "temperature": self.generation_config.temperature,
            "top_p": self.generation_config.top_p,
            "top_k": self.generation_config.top_k
        }
        
        # Create new generation config
        self.generation_config = genai.GenerationConfig(
            temperature=config.get("temperature", original_config["temperature"]),
            top_p=config.get("top_p", original_config["top_p"]),
            top_k=config.get("top_k", original_config["top_k"]),
            max_output_tokens=self.generation_config.max_output_tokens
        )
        
        # Create new model instance with updated config
        self.model = genai.GenerativeModel(
            self.config.get('model', {}).get('name', 'gemini-2.0-flash-exp'),
            generation_config=self.generation_config
        )
        
        # Update chat session with new model
        history = self.chat.history
        self.chat = self.model.start_chat(history=history)
        
        return original_config

    def _restore_model_config(self, original_config: Dict):
        """
        Restores the original model configuration
        """
        self.generation_config = genai.GenerationConfig(
            temperature=original_config["temperature"],
            top_p=original_config["top_p"],
            top_k=original_config["top_k"],
            max_output_tokens=self.generation_config.max_output_tokens
        )
        
        # Create new model instance with original config
        self.model = genai.GenerativeModel(
            self.config.get('model', {}).get('name', 'gemini-2.0-flash-exp'),
            generation_config=self.generation_config
        )
        
        # Update chat session with new model
        history = self.chat.history
        self.chat = self.model.start_chat(history=history)
