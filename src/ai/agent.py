import asyncio
import google.generativeai as genai
from google.api_core import retry
import time
import json
import re 
from datetime import datetime
from core.terminal import UnifiedTerminal
from core.linux_interaction import LinuxInteraction
from prompts.main_context_prompt import SYSTEM_PROMPT, get_system_prompt
from ai.context_manager import ContextManager
from ai.rate_limiter import RateLimiter
from ai.deep_reasoning import DeepReasoning
from typing import Dict, Optional, Callable

def _extract_json(text: str) -> str:
    """Extract JSON from text, handling various formats"""
    # Remove leading/trailing whitespace
    text = text.strip()
    
    # Find JSON boundaries
    start = text.find('{')
    end = text.rfind('}') + 1
    
    if start >= 0 and end > 0:
        return text[start:end]
    
    raise ValueError("No valid JSON found in response")

class AIAgent:
    def __init__(self, config: dict):
        self.config = config
        genai.configure(api_key=self.config['api_key'])
        model_config = self.config.get('model', {})
        self.generation_config = genai.GenerationConfig(
            temperature=model_config.get('temperature', 0.7),
            top_p=model_config.get('top_p', 0.9),
            top_k=model_config.get('top_k', 40),
            max_output_tokens=model_config.get('max_output_tokens', 4096),
        )
        self.model = genai.GenerativeModel(
            model_config.get('name', 'gemini-2.0-flash-exp'),
            generation_config=self.generation_config 
        )
        self.chat = self.model.start_chat(history=[
            {"role": "user", "parts": [SYSTEM_PROMPT]},
            {"role": "model", "parts": ["System initialized with instructions. Ready to execute commands."]}
        ])
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
        self.system_prompt = get_system_prompt(config)
        
        self.current_task: Optional[asyncio.Task] = None
        self.terminal.set_interrupt_handler(self.handle_interrupt)
        
    def _initialize_chat(self):
        genai.configure(api_key=self.config['api_key'])
        
        model_config = self.config.get('model', {})
        
        model = genai.GenerativeModel(
            model_config.get('name', 'gemini-2.0-flash-exp'),
            generation_config=self.generation_config
        )
        
        return model.start_chat(history=[
            {"role": "user", "parts": [SYSTEM_PROMPT]},
            {"role": "model", "parts": ["System initialized with instructions. Ready to execute commands."]}
        ])
        
    def _needs_confirmation(self, risk_level: str) -> bool:
        """Determine if an action needs user confirmation based on config"""
        agent_config = self.config.get('agent', {})
        
        if not agent_config.get('require_confirmation', True):
            return False
            
        threshold = agent_config.get('risk_threshold', 'medium').lower()
        
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
                # Esperar antes de fazer a requisição
                await self.rate_limiter.wait_if_needed_async()  # Mudado para versão async
                
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
                        await asyncio.sleep(retry_delay)
                        continue
                elif attempt < max_attempts - 1:
                    self.terminal.log(
                        f"API error: {error_msg}. Retrying {attempt + 1}/{max_attempts}...",
                        "WARNING"
                    )
                    await asyncio.sleep(1)
                    continue
                
        raise last_error or Exception("Maximum retry attempts reached")
        
    def handle_interrupt(self):
        """Handler for command interruption"""
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()
        if hasattr(self.linux, 'current_process'):
            self.linux.interrupt_current_process()
            
    async def process_command(self, user_input: str):
        try:
            # Store current task
            self.current_task = asyncio.current_task()
            
            # Temp
            if hasattr(self, '_current_command') and self._current_command == user_input:
                return "Command already being processed. Please wait."
            
            self._current_command = user_input
            
            context = self.context_manager.get_current_context()
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            self.terminal.start_processing("Thinking...")
            
            prompt = f"""System: {self.system_prompt}
            Current context: {context}
            User command: {user_input}
            Timestamp: {current_time}
            
            Analyze the input and respond in the specified JSON format."""
            
            response_text = await self._send_message_with_retry(prompt)
            
            if not response_text:
                raise ValueError("Received empty response from the chat model.")
            
            self.terminal.stop_processing()
            
            async def execute_step(parsed_response):
                try:
                    # Temp
                    if hasattr(self, '_last_action') and self._last_action == parsed_response:
                        return "Action already completed.", False
                    
                    self._last_action = parsed_response
                    
                    # Check if deep reasoning is needed
                    should_activate = (
                        parsed_response.get("requires_deep_reasoning", False) or
                        self.deep_reasoning.should_activate(parsed_response)
                    )
                    
                    if should_activate:
                        reasoning_context = parsed_response.get("reasoning_context", {})
                        try:
                            deep_analysis = await self.deep_reasoning.deep_analyze(
                                reasoning_context.get("situation", user_input),
                                self.context_manager.get_current_context()
                            )
                            
                            # If deep_analysis returned error, continue with standard analysis
                            if deep_analysis.get("type") == "error":
                                self.terminal.log("Deep reasoning failed, continuing with standard analysis", "WARNING")
                                return await execute_step(parsed_response)
                            
                            # Send analysis to main model
                            analysis_prompt = f"""System: {self.system_prompt}
                            
                            A deep analysis has been performed. Based on this analysis, determine the best action to take:

                            Deep Reasoning Analysis:
                            {deep_analysis.get('analysis', '')}

                            Please analyze this synthesis and decide the next step, strictly following the specified response format."""

                            response = await self._send_message_with_retry(analysis_prompt)
                            if response:
                                try:
                                    clean_text = re.sub(r"```json\s*([\s\S]*?)```", r"\1", response)
                                    parsed = json.loads(_extract_json(clean_text))
                                    return await execute_step(parsed)
                                except Exception as e:
                                    self.terminal.log(f"Error parsing Deep Reasoning response: {str(e)}", "ERROR")
                                    # If error, continue with standard analysis
                                    return await execute_step(parsed_response)
                        except Exception as e:
                            self.terminal.log(f"Deep Reasoning failed: {str(e)}", "ERROR")
                            # If error, continue with standard analysis
                            return await execute_step(parsed_response)
                    
                    response_text = parsed_response.get("message") or parsed_response.get("analysis") or ""
                    should_continue = parsed_response.get("continue", False)
                    
                    if response_text:
                        self.terminal.log_agent(response_text)

                    # If there's no next_step or it's None, just return
                    if "next_step" not in parsed_response or parsed_response["next_step"] is None:
                        return response_text, should_continue

                    action = parsed_response["next_step"]
                    # If there's no command to execute, just return
                    if not action.get("command"):
                        return response_text, should_continue
                    
                    risk = action.get("risk", "medium").lower()
                    
                    if (action.get("requires_confirmation", False) and 
                        self._needs_confirmation(risk)):
                        confirmation = await self.terminal.request_confirmation(
                            f"Should I execute the command '{action['command']}'? "
                            f"(Risk: {risk})"
                        )
                        if not confirmation:
                            return "Operation canceled by user.", False

                    self.terminal.log(f"Executing: {action['command']}", "EXEC")
                    stdout, stderr, returncode = self.linux.run_command(action['command'])

                    self.terminal.stop_processing()
                    
                    if returncode != 0:
                        error_msg = f"Command returned code {returncode}: {stderr.strip() if stderr else 'No error message'}"
                        self.terminal.log(error_msg, "ERROR")

                        context_entry = {
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "type": "error",
                            "content": stderr if stderr else error_msg
                        }
                        self.context_manager.add_to_context(context_entry)
                        
                        self.deep_reasoning.record_result(success=False)
                        
                        if should_continue:
                            self.terminal.log("Analyzing result...", "INFO")
                            next_response_text = await self._send_message_with_retry(
                                f"""Analyze this error and decide the next step.
                                Command: {action['command']}
                                Return code: {returncode}
                                Error: {stderr if stderr else 'No error message'}"""
                            )
                            
                            if next_response_text:
                                try:
                                    clean_text = re.sub(r"```json\s*([\s\S]*?)```", r"\1", next_response_text)
                                    next_parsed = json.loads(_extract_json(clean_text))
                                    return await execute_step(next_parsed)
                                except Exception as e:
                                    self.terminal.log(f"Error parsing response: {str(e)}", "ERROR")
                                    return str(e), False
                        
                        return error_msg, should_continue
                        
                    if stdout.strip():
                        self.terminal.log(stdout.strip(), "OUTPUT")
                    else:
                        self.terminal.log(f"Command completed successfully", "INFO")

                    context_entry = {
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "type": "output",
                        "content": stdout if stdout.strip() else "Command completed successfully"
                    }
                    self.context_manager.add_to_context(context_entry)

                    # Sempre continuar se should_continue for True
                    if should_continue:
                        self.terminal.log("Analyzing result...", "INFO")
                        next_response_text = await self._send_message_with_retry(
                            f"""Analyze this result and determine the next step.
                            Command: {action['command']}
                            Return code: {returncode}
                            Output: {stdout if stdout.strip() else 'No output'}
                            Status: Command completed successfully

                            Based on this output, determine the next step."""
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

                    self.deep_reasoning.record_result(success=True)
                    return stdout if stdout.strip() else "Command completed successfully", should_continue
                    
                except Exception as e:
                    self.deep_reasoning.record_result(success=False)
                    self.terminal.log(f"Error in execute_step: {str(e)}", "ERROR")
                    return str(e), False

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
            return final_result.strip() if final_result else ""

        except asyncio.CancelledError:
            self.terminal.log("Command execution cancelled", "WARNING")
            return "Command cancelled by user"
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self.terminal.log(error_msg, "ERROR")
            return error_msg
        finally:
            self.current_task = None

    def _temp_configure_model(self, config: Dict) -> Dict:
        """
        Temporarily configures the model with new parameters and returns original configuration.
        """
        original_config = {
            "temperature": self.generation_config.temperature,
            "top_p": self.generation_config.top_p,
            "top_k": self.generation_config.top_k
        }
        self.generation_config.temperature = config.get("temperature", original_config["temperature"])
        self.generation_config.top_p = config.get("top_p", original_config["top_p"])
        self.generation_config.top_k = config.get("top_k", original_config["top_k"])
        return original_config

    def _restore_model_config(self, original_config: Dict):
        """
        Restores the model configuration to the previously saved settings.
        """
        self.generation_config.temperature = original_config["temperature"]
        self.generation_config.top_p = original_config["top_p"]
        self.generation_config.top_k = original_config["top_k"]
