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
        
    def _initialize_chat(self):
        genai.configure(api_key=self.config['api_key'])
        
        # Get model configuration
        model_config = self.config.get('model', {})
        
        model = genai.GenerativeModel(
            model_config.get('name', 'gemini-2.0-flash-exp'),
            generation_config=genai.GenerationConfig(
                temperature=model_config.get('temperature', 0.7),
                top_p=model_config.get('top_p', 0.9),
                top_k=model_config.get('top_k', 40),
                max_output_tokens=model_config.get('max_output_tokens', 4096),
            )
        )
        
        return model.start_chat(history=[
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
        
        for attempt in range(max_attempts):
            try:
                # Wait for rate limiting if needed
                self.rate_limiter.wait_if_needed()
                
                # Send message
                response = self.chat.send_message(message)
                return response.text if response else None
                
            except Exception as e:
                error_msg = str(e)
                
                # Check if it's a rate limit error
                if "429" in error_msg or "quota" in error_msg.lower():
                    if attempt < max_attempts - 1:
                        self.terminal.log(
                            f"Rate limit reached. Waiting {retry_delay}s before retry {attempt + 1}/{max_attempts}",
                            "WARNING"
                        )
                        time.sleep(retry_delay)
                        continue
                        
                # If it's the last attempt or not a rate limit error, raise
                raise
        
        raise Exception("Maximum retry attempts reached")
        
    async def process_command(self, user_input: str):
        try:
            context = self.context_manager.get_current_context()
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Start processing with spinner
            self.terminal.start_processing("Processing...")
            
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
                response_text = parsed_response.get("message") or parsed_response.get("analysis") or ""
                
                # Use log_agent to display Agent message in cyan without timestamp
                if response_text:
                    self.terminal.log_agent(response_text)

                if "next_step" in parsed_response and parsed_response["next_step"].get("action"):
                    action = parsed_response["next_step"]
                    risk = action.get("risk", "medium").lower()
                    
                    # Check if confirmation is needed based on config
                    if action.get("requires_confirmation", True) and self._needs_confirmation(risk):
                        confirmation = await self.terminal.request_confirmation(
                            f"Should I execute the action '{action['action']}'? "
                            f"(Risk: {risk})"
                        )
                        if not confirmation:
                            return "Operation canceled by user.", False

                    self.terminal.log(f"Executing: {parsed_response['next_step']['action']}", "EXEC")
                    stdout, stderr, returncode = self.linux.run_command(parsed_response['next_step']['action'])

                    # Combine stdout and stderr for the agent to receive the entire log
                    combined_result = ""
                    if stdout.strip():
                        combined_result += stdout.rstrip()
                    if stderr.strip():
                        combined_result += f"\n{stderr.strip()}"

                    if returncode != 0 and stderr.strip():
                        self.terminal.log(
                            f"Command returned code {returncode}: {stderr.strip()}",
                            "ERROR"
                        )

                    # If there is something to show
                    if combined_result.strip():
                        self.terminal.log(combined_result, "OUTPUT", show_timestamp=False)
                        self.context_manager.add_to_context({
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "type": "output",
                            "content": combined_result
                        })

                        if parsed_response.get("continue", False):
                            self.terminal.log("Analyzing result...", "INFO")
                            next_response_text = await self._send_message_with_retry(
                                f"Analyze this result and decide the next step:\n{combined_result}"
                            )
                            if next_response_text:
                                clean_text = re.sub(r"```json\s*([\s\S]*?)```", r"\1", next_response_text)
                                try:
                                    next_parsed = json.loads(_extract_json(clean_text))
                                    return await execute_step(next_parsed)
                                except json.JSONDecodeError:
                                    return clean_text.strip(), False

                    # Return empty to avoid duplicating the same message
                    return "", parsed_response.get("continue", False)

                # Return empty when there is no command
                return "", parsed_response.get("continue", False)

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
                        self.terminal.log("Continuing analysis...", "INFO")
                        return await process_response(result)
                    return result
                except json.JSONDecodeError:
                    return clean_text.strip()

            final_result = await process_response(response_text)
            # If final_result is empty, do not display "Processing completed."
            return final_result.strip() if final_result else ""

        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self.terminal.log(error_msg, "ERROR")
            return error_msg
