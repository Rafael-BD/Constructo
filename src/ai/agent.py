import google.generativeai as genai
import json
import re  # (1) to remove ```json blocks
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
        
        model = genai.GenerativeModel(
            'gemini-2.0-flash-exp',
            generation_config=genai.GenerationConfig(
                temperature=0.9,
                top_p=1,
                top_k=1,
                max_output_tokens=2048,
            )
        )
        
        # Start chat with system instructions
        return model.start_chat(history=[
            {
                "role": "user",
                "parts": [SYSTEM_PROMPT]
            },
            {
                "role": "model",
                "parts": ["System initialized with instructions. Ready to execute commands."]
            }
        ])
        
    async def process_command(self, user_input: str, require_confirmation=True):
        try:
            context = self.context_manager.get_current_context()
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Start processing with spinner
            self.terminal.start_processing("Processing...")
            
            prompt = f"""Current context: {context}
            User command: {user_input}
            Timestamp: {current_time}
            
            Analyze the input and respond in the specified JSON format."""
            
            response = self.chat.send_message(prompt)
            response_text = response.text if response else None
            
            # Stop spinner and clear
            self.terminal.stop_processing()
            
            if not response_text:
                raise ValueError("Received empty response from the chat model.")
            
            async def execute_step(parsed_response):
                response_text = parsed_response.get("message") or parsed_response.get("analysis") or ""
                
                # Use log_agent to display Agent message in cyan without timestamp
                if response_text:
                    self.terminal.log_agent(response_text)

                if "next_step" in parsed_response and parsed_response["next_step"].get("action"):
                    if parsed_response["next_step"].get("requires_confirmation", True) and require_confirmation:
                        confirmation = await self.terminal.request_confirmation(
                            f"Should I execute the action '{parsed_response['next_step']['action']}'? "
                            f"(Risk: {parsed_response['next_step']['risk']})"
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
                            next_response = self.chat.send_message(
                                f"Analyze this result and decide the next step:\n{combined_result}"
                            )
                            if next_response and next_response.text:
                                clean_text = re.sub(r"```json\s*([\s\S]*?)```", r"\1", next_response.text)
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
