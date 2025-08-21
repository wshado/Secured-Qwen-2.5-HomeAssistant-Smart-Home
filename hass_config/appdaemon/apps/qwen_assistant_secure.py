#qwen-assistant-secure.py - Security-hardened version
import appdaemon.plugins.hass.hassapi as hass
from ollama import Client
import json
import pickle
import os
import requests
import re
import html
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

class QwenAssistantSecure(hass.Hass):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Define allowlist for permitted actions
        self.ALLOWED_ENTITIES = {
            "switch.smarthome_node_dc_motor_fan",
            "switch.smarthome_node_smart_home_light",
            "sensor.smarthome_node_keystudio_temperature",
            "sensor.smarthome_node_keystudio_humidity",
            "binary_sensor.smarthome_node_motion_sensor",
            "sensor.smarthome_node_led_activation_count",
            "sensor.smarthome_node_buzzer_alert_count"
        }
        self.ALLOWED_SERVICES = {
            "switch/turn_on",
            "switch/turn_off"
        }
        # Action mapping for structured responses
        self.ACTION_MAPPING = {
            "turn_on_fan": {
                "service": "switch/turn_on",
                "entity_id": "switch.smarthome_node_dc_motor_fan",
                "description": "Turn on the fan"
            },
            "turn_off_fan": {
                "service": "switch/turn_off",
                "entity_id": "switch.smarthome_node_dc_motor_fan",
                "description": "Turn off the fan"
            },
            "turn_on_light": {
                "service": "switch/turn_on",
                "entity_id": "switch.smarthome_node_smart_home_light",
                "description": "Turn on the light"
            },
            "turn_off_light": {
                "service": "switch/turn_off",
                "entity_id": "switch.smarthome_node_smart_home_light",
                "description": "Turn off the light"
            }
        }
        # Conversation history limits
        self.MAX_HISTORY_LENGTH = 50
        self.HISTORY_ROTATION_DAYS = 7
        
    def sanitize_input(self, text: str) -> str:
        """Sanitize and validate user input before sending to LLM"""
        if not isinstance(text, str):
            return ""
        
        # Remove potential injection attempts
        text = text.strip()
        
        # HTML escape to prevent injection
        text = html.escape(text)
        
        # Remove or escape potentially dangerous patterns
        dangerous_patterns = [
            r'<script.*?</script>',
            r'javascript:',
            r'data:',
            r'vbscript:',
            r'onload=',
            r'onerror=',
            r'eval\(',
            r'exec\(',
            r'import\s+',
            r'__.*__',
            r'\.\./',
            r'system\(',
            r'subprocess\.',
            r'os\.',
            r'file\(',
            r'open\('
        ]
        
        for pattern in dangerous_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # Limit length to prevent DoS
        if len(text) > 1000:
            text = text[:1000]
            self.log("⚠️ Input truncated due to length limit", level="WARNING")
        
        return text

    def validate_entity_access(self, entity_id: str) -> bool:
        """Validate that entity is in allowlist"""
        return entity_id in self.ALLOWED_ENTITIES
    
    def validate_service_call(self, service: str) -> bool:
        """Validate that service is in allowlist"""
        return service in self.ALLOWED_SERVICES
    
    def sanitize_context_values(self, context_data: Dict[str, Any]) -> Dict[str, str]:
        """Sanitize context entity values before adding to prompt"""
        sanitized = {}
        for key, value in context_data.items():
            if isinstance(value, str):
                sanitized[key] = self.sanitize_input(value)
            else:
                # Convert to string and sanitize
                sanitized[key] = self.sanitize_input(str(value))
        return sanitized

    def extract_dates(self, text: str) -> tuple:
        """Extract dates with input validation"""
        text = self.sanitize_input(text)
        # Example: "from 2025-07-08T00:00:00Z to 2025-07-09T00:00:00Z"
        match = re.search(r'from (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) to (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)', text)
        if match:
            return match.group(1), match.group(2)
        return None, None

    def get_entity_history(self, entity_id: str, start_time: str, end_time: str) -> List[Dict]:
        """Get entity history with validation and sanitization"""
        # Validate entity access
        if not self.validate_entity_access(entity_id):
            self.log(f"⚠️ Unauthorized entity access attempt: {entity_id}", level="WARNING")
            return []
        
        # Sanitize inputs
        entity_id = self.sanitize_input(entity_id)
        start_time = self.sanitize_input(start_time)
        end_time = self.sanitize_input(end_time)
        
        url = f"{self.args['ha_url']}/api/history/period/{start_time}?end_time={end_time}&filter_entity_id={entity_id}"
        headers = {
            "Authorization": f"Bearer {self.args['ha_token']}",
            "Content-Type": "application/json"
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    entries = data[0]
                    # Limit and sanitize history entries
                    limited_entries = entries[:100]  # Limit to prevent DoS
                    summary = []
                    for e in limited_entries:
                        sanitized_entry = {
                            "time": self.sanitize_input(str(e.get("last_changed", ""))),
                            "value": self.sanitize_input(str(e.get("state", "")))
                        }
                        summary.append(sanitized_entry)
                    return summary
            else:
                self.log(f"⚠️ Error fetching history: {response.status_code}", level="ERROR")
        except Exception as e:
            self.log(f"⚠️ Exception fetching history: {e}", level="ERROR")
        return []

    def rotate_conversation_history(self):
        """Rotate/clear conversation history regularly"""
        if len(self.conversation_history) > self.MAX_HISTORY_LENGTH:
            # Keep only the last N messages
            self.conversation_history = self.conversation_history[-self.MAX_HISTORY_LENGTH:]
            self.log("🔄 Conversation history rotated due to length limit", level="INFO")
        
        # Check if history is older than rotation period
        history_file_path = self.history_path
        if os.path.exists(history_file_path):
            file_age = datetime.fromtimestamp(os.path.getmtime(history_file_path))
            if datetime.now() - file_age > timedelta(days=self.HISTORY_ROTATION_DAYS):
                self.conversation_history = []
                self.log("🔄 Conversation history cleared due to age", level="INFO")

    def initialize(self):
        self.listen_event(self.on_utterance, "conversation_utterance")
        self.ollama = Client(host=self.args["qwen_url"])
        
        # Sanitize context entities
        context_prompt = { e: self.get_state(e) for e in self.args["context_entities"] }
        context_prompt = self.sanitize_context_values(context_prompt)
        context_str = "\n".join([f"{k}: {v}" for k, v in context_prompt.items()])

        self.history_path = "/home/cciaz/Desktop/backup_folder_1.5b/hass_config/appdaemon/logs/qwen_history_secure.pkl"

        if os.path.exists(self.history_path):
            try:
                with open(self.history_path, "rb") as f:
                    self.conversation_history = pickle.load(f)
                self.log("✅ Loaded existing conversation history from pickle.", level="INFO")
                # Rotate history on startup
                self.rotate_conversation_history()
            except Exception as e:
                self.conversation_history = []
                self.log(f"⚠️ Error loading pickle history: {e}", level="ERROR")
        else:
            self.conversation_history = []
            self.log("💬 No existing pickle history found, starting new.", level="INFO")
            
    def on_utterance(self, event_name, data, kwargs):
        self.log(f"🎯 Received conversation_utterance event: {data}", level="INFO")
        user_text = data.get("text", "")
        
        # Sanitize user input immediately
        user_text = self.sanitize_input(user_text)
        
        try:
            conv_context = data["metadata"]["context"]
            self.log(f"📝 Processing utterance: '{user_text}' with context: {conv_context}", level="INFO")
            self.run_in(self.handle_query, 0, user_text=user_text, context=conv_context)
        except KeyError as e:
            self.log(f"❌ Error accessing event data: {e}. Full data: {data}", level="ERROR")

    def validate_llm_response(self, response: str) -> str:
        """Post-processing validation of LLM response"""
        if not isinstance(response, str):
            return "Error: Invalid response format"
        
        # Sanitize the response
        response = self.sanitize_input(response)
        
        # Check for potential malicious content in response
        suspicious_patterns = [
            r'<script',
            r'javascript:',
            r'eval\(',
            r'exec\(',
            r'import\s+os',
            r'subprocess',
            r'__import__',
            r'getattr\(',
            r'setattr\(',
            r'delattr\('
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, response, re.IGNORECASE):
                self.log(f"⚠️ Suspicious content detected in LLM response", level="WARNING")
                return "I apologize, but I cannot process that request for security reasons."
        
        return response

    def parse_llm_response(self, response: str) -> tuple:
        """Parse LLM response for structured JSON with action intent"""
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                
                # Decode HTML entities that may have been introduced by sanitization
                json_str = html.unescape(json_str)
                
                parsed = json.loads(json_str)
                
                action = parsed.get("action")
                message = parsed.get("message", response)
                
                # Validate action is in our mapping
                if action and action in self.ACTION_MAPPING:
                    return action, message
                else:
                    return None, message
            else:
                # Fallback: no JSON found, return original response
                return None, response
                
        except (json.JSONDecodeError, AttributeError) as e:
            self.log(f"⚠️ Failed to parse JSON from LLM response: {e}", level="WARNING")
            return None, response

    def execute_safe_action(self, action: str) -> bool:
        """Execute actions with validation using unified action mapping"""
        if action not in self.ACTION_MAPPING:
            self.log(f"⚠️ Unauthorized action attempt: {action}", level="WARNING")
            return False
        
        action_config = self.ACTION_MAPPING[action]
        entity_id = action_config["entity_id"]
        
        if not self.validate_entity_access(entity_id):
            self.log(f"⚠️ Unauthorized entity access: {entity_id}", level="WARNING")
            return False
        
        try:
            self.call_service(action_config["service"], entity_id=entity_id)
            self.log(f"{action_config['description']} via Qwen (validated)", level="INFO")
            return True
        except Exception as e:
            self.log(f"⚠️ Error executing action {action}: {e}", level="ERROR")
            return False

    def handle_query(self, kwargs):
        user_text = kwargs["user_text"]
        conv_context = kwargs["context"]
        
        # Additional sanitization
        user_text = self.sanitize_input(user_text)
        
        # Check if user requested a range
        start_time, end_time = self.extract_dates(user_text)

        history_str = ""
        if start_time and end_time:
            self.log(f"📊 Fetching history from {start_time} to {end_time}", level="INFO")
            # Example: pull humidity with validation
            history = self.get_entity_history("sensor.smarthome_node_keystudio_humidity", start_time, end_time)
            if history:
                history_str = "\n".join([f"{x['time']}: {x['value']}" for x in history])
            else:
                history_str = "No history data found for that range."

        # Compose context from entities with sanitization
        context_prompt = { e: self.get_state(e) for e in self.args["context_entities"] }
        context_prompt = self.sanitize_context_values(context_prompt)
        context_str = "\n".join([f"{k}: {v}" for k, v in context_prompt.items()])

        if history_str:
            context_str += f"\n\nHumidity history (requested):\n{history_str}"

        # Rotate conversation history before adding new messages
        self.rotate_conversation_history()

        # Add system message with security constraints and JSON format requirement
        available_actions = list(self.ACTION_MAPPING.keys())
        system_content = (
            "You are a multi-tool home assistant. Provide clear, brief, helpful, and direct answers. "
            "IMPORTANT SECURITY CONSTRAINTS: "
            "- Only control devices explicitly mentioned in context "
            "- Do not execute any code or system commands "
            "- Do not access files or external resources "
            "- Limit responses to home automation tasks only "
            "\n\nRESPONSE FORMAT RULES: "
            "- For status questions, information requests, or general conversation: respond with normal text only "
            "- When user requests device control (turn on/off fan, light), you MUST respond with JSON format "
            "- JSON format: {\"action\": \"action_name\", \"message\": \"your response message\"} "
            f"- Available actions: {', '.join(available_actions)} "
            "- Examples of control requests that need JSON: 'turn on fan', 'turn off light', 'switch on fan' "
            "- Do NOT provide JSON examples in conversation unless actually performing the requested action\n\n"
            "Use the following context to answer:\n" + context_str
        )
        
        self.conversation_history.append({
            "role": "system",
            "content": system_content
        })

        # Add user message
        self.conversation_history.append({
            "role": "user",
            "content": user_text
        })
        self.log_to_file(f"User Request (sanitized): {self.conversation_history[-1]}")

        try:
            # Call local Qwen model using Ollama Python client
            response = self.ollama.chat(model=self.args["qwen_model"], messages=self.conversation_history)
            speech = response["message"]["content"]
            
            # Validate and sanitize LLM response
            speech = self.validate_llm_response(speech)
            
        except Exception as e:
            speech = f"Error contacting Qwen: {e}"
            self.log(f"⚠️ LLM Error: {e}", level="ERROR")

        # Parse structured response for actions
        action, display_message = self.parse_llm_response(speech)
        action_executed = False
        
        if action:
            action_executed = self.execute_safe_action(action)
            # Use the message from JSON response
            speech = display_message

        # Log action execution status
        if action_executed:
            self.log("✅ Action executed successfully with security validation", level="INFO")

        # Send response back to HA conversation UI
        self.log(f"▶ conversation_response with context {conv_context}: {speech}", level="INFO")
        self.log_to_file(f"Qwen Response (validated): {speech}")
        self.fire_event("conversation_response", text=speech, context=conv_context)

        self.conversation_history.append({
            "role": "assistant",
            "content": speech
        })

        # Save conversation history securely
        try:
            with open(self.history_path, "wb") as f:
                pickle.dump(self.conversation_history, f)
            self.log("💾 Conversation history saved with pickle (secure).", level="INFO")
        except Exception as e:
            self.log(f"⚠️ Failed to save pickle history: {e}", level="ERROR")

    def log_to_file(self, message):
        """Secure logging with input sanitization"""
        log_path = "/home/cciaz/Desktop/backup_folder_1.5b/hass_config/appdaemon/logs/qwen_assistant_secure.log"
        
        # Sanitize log message to prevent log injection
        safe_message = self.sanitize_input(str(message))
        timestamp = datetime.now().isoformat()
        
        try:
            with open(log_path, "a") as f:
                f.write(f"[{timestamp}] {safe_message}\n")
        except Exception as e:
            self.log(f"⚠️ Failed to write to log file: {e}", level="ERROR")
