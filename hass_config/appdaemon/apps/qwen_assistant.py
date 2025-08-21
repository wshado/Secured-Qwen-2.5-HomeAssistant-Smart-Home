#qwen-assistant.py
import appdaemon.plugins.hass.hassapi as hass
from ollama import Client
import json
import pickle
import os
import requests
import re

class QwenAssistant(hass.Hass):

    def extract_dates(self, text):
        # Example: "from 2025-07-08T00:00:00Z to 2025-07-09T00:00:00Z"
        match = re.search(r'from (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) to (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)', text)
        if match:
            return match.group(1), match.group(2)
        return None, None

    def get_entity_history(self, entity_id, start_time, end_time):
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
                    summary = [
                        {"time": e["last_changed"], "value": e["state"]}
                        for e in entries
                    ]
                    return summary
            else:
                self.log(f"⚠️ Error fetching history: {response.status_code}", level="ERROR")
        except Exception as e:
            self.log(f"⚠️ Exception fetching history: {e}", level="ERROR")
        return []

    def initialize(self):
        self.listen_event(self.on_utterance, "conversation_utterance")
        self.ollama = Client(host=self.args["qwen_url"])
        context_prompt = { e: self.get_state(e) for e in self.args["context_entities"] }
        context_str = "\n".join([f"{k}: {v}" for k, v in context_prompt.items()])

        self.history_path = "/home/cciaz/Desktop/backup_folder_1.5b/hass_config/appdaemon/logs/qwen_history.pkl"

        if os.path.exists(self.history_path):
            try:
                with open(self.history_path, "rb") as f:
                    self.conversation_history = pickle.load(f)
                self.log("✅ Loaded existing conversation history from pickle.", level="INFO")
            except Exception as e:
                self.conversation_history = []
                self.log(f"⚠️ Error loading pickle history: {e}", level="ERROR")
        else:
            self.conversation_history = []
            self.log("💬 No existing pickle history found, starting new.", level="INFO")
            
    def on_utterance(self, event_name, data, kwargs):
        self.log(f"🎯 Received conversation_utterance event: {data}", level="INFO")
        user_text = data.get("text", "")
        try:
            conv_context = data["metadata"]["context"]
            self.log(f"📝 Processing utterance: '{user_text}' with context: {conv_context}", level="INFO")
            self.run_in(self.handle_query, 0, user_text=user_text, context=conv_context)
        except KeyError as e:
            self.log(f"❌ Error accessing event data: {e}. Full data: {data}", level="ERROR")

    def handle_query(self, kwargs):
        user_text = kwargs["user_text"]
        conv_context = kwargs["context"]
        
         # Check if user requested a range
        start_time, end_time = self.extract_dates(user_text)

        history_str = ""
        if start_time and end_time:
            self.log(f"📊 Fetching history from {start_time} to {end_time}", level="INFO")
            # Example: pull humidity
            history = self.get_entity_history("sensor.smarthome_node_keystudio_humidity", start_time, end_time)
            if history:
                history_str = "\n".join([f"{x['time']}: {x['value']}" for x in history])
            else:
                history_str = "No history data found for that range."

        # Compose context from entities
        context_prompt = { e: self.get_state(e) for e in self.args["context_entities"] }
        context_str = "\n".join([f"{k}: {v}" for k, v in context_prompt.items()])

        if history_str:
            context_str += f"\n\nHumidity history (requested):\n{history_str}"

        self.conversation_history.append(
            {
                "role": "system",
                "content": "You are a multi-tool home assist, browser assist, and helpful acolyte. Provide clear, brief, helpful, and direct answers.  Use the following context to answer:\n" + context_str
            }
        )
        # Build conversation messages for Qwen

        self.conversation_history.append({
                "role": "user",
                "content": user_text
            })
        self.log_to_file(f"User Request: {self.conversation_history[-1]}")
        

        try:
            # Call local Qwen model using Ollama Python client
            response = self.ollama.chat(model=self.args["qwen_model"], messages=self.conversation_history)
            speech = response["message"]["content"]
        except Exception as e:
            speech = f"Error contacting Qwen: {e}"

        lower_speech = speech.lower()

        # 🔥 FAN control
        if "turning on the fan" in lower_speech:
            self.call_service("switch/turn_on", entity_id="switch.smarthome_node_dc_motor_fan")
            self.log("Fan turned ON via Qwen", level="INFO")
        elif "turning off the fan" in lower_speech:
            self.call_service("switch/turn_off", entity_id="switch.smarthome_node_dc_motor_fan")
            self.log("Fan turned OFF via Qwen", level="INFO")

        # 💡 LIGHT control
        if "turning on the light" in lower_speech:
            self.call_service("switch/turn_on", entity_id="switch.smarthome_node_smart_home_light")
            self.log("Light turned ON via Qwen", level="INFO")
        elif "turning off the light" in lower_speech:
            self.call_service("switch/turn_off", entity_id="switch.smarthome_node_smart_home_light")
            self.log("Light turned OFF via Qwen", level="INFO")

        # 📄 RFID list clearing
        if "clear rfid list" in lower_speech or "reset rfid list" in lower_speech:
            self.call_service("input_text/set_value", entity_id="input_text.input_text_rfid_tag_list", value="")
            self.log("RFID tag list cleared via Qwen", level="INFO")

        # 🔊 Send response back to HA conversation UI
        self.log(f"▶ conversation_response with context {conv_context}: {speech}", level="INFO")
        self.log_to_file(f"Qwen Response: {speech}")
        self.fire_event("conversation_response", text=speech, context=conv_context)


        self.conversation_history.append({
            "role": "assistant",
            "content": speech
        })

        try:
            with open(self.history_path, "wb") as f:
                pickle.dump(self.conversation_history, f)
            self.log("💾 Conversation history saved with pickle.", level="INFO")
        except Exception as e:
            self.log(f"⚠️ Failed to save pickle history: {e}", level="ERROR")

    def log_to_file(self, message):
        log_path = "PATH TO LOGS"  # customize path
        with open(log_path, "a") as f:
            f.write(f"{message}\n")
