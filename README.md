# Secured Qwen 2.5 Home Assistant Smart Home Integration

A complete Home Assistant setup with Qwen AI conversation integration via AppDaemon, featuring enhanced security controls and structured action execution.

## Features

- 🏠 **Home Assistant Core** - Running in Docker container
- 🤖 **Qwen AI Integration** - Secure AppDaemon assistant with input validation
- 📱 **Smart Home Devices** - Temperature, humidity, motion sensors, LED, buzzer, fan, lights
- 🔒 **Enhanced Security** - Input sanitization, allowlist validation, and structured responses
- 📊 **AppDaemon** - Advanced automation with JSON-based action execution
- 🛡️ **Security Hardened** - Multiple layers of protection against injection attacks

## ⚠️ Important: Path Configuration Required

**Before running this project, you MUST update file paths in the following files:**

1. **Python files** (`hass_config/appdaemon/apps/`):
   - `qwen_assistant.py` - Lines 48 and 160
   - `qwen_assistant_secure.py` - Lines 191 and 407
   
2. **Service file** (`appdaemon.service`):
   - Lines 9 and 11 - Update `${PWD}` to your actual project directory path
   
3. **Shell script** (`start_appdaemon.sh`):
   - Lines 5, 6, and 12 - Update `${PWD}` references to your project path

**Current paths use `${PWD}` and relative paths - update these based on your installation location.**

## Quick Setup

### 1. Clone and Configure Paths

```bash
git clone <your-repo>
cd Secured-Qwen-2.5-HomeAssistant-Smart-Home

# IMPORTANT: Update all file paths in .py, .service, and .sh files
# Replace ${PWD} and relative paths with your actual project directory
```

### 2. Environment Variables

Create `.env` file with your configuration:

```bash
# Home Assistant Configuration
HA_URL=http://your-ha-ip:8123
HA_TOKEN=your-home-assistant-long-lived-access-token

# Qwen/Ollama Configuration  
QWEN_URL=http://localhost:11434
QWEN_MODEL=qwen2.5:1.5b-instruct-q4_0
```

### 3. Install SystemD Service

```bash
# Copy service file to systemd directory
sudo cp appdaemon.service /etc/systemd/system/

# Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable appdaemon.service
sudo systemctl start appdaemon.service

# Check service status
sudo systemctl status appdaemon.service
```

### 4. Start Services

```bash
# Start Home Assistant
docker-compose up -d

# Verify container is running
docker logs homeassistant
```

### 5. Setup Ollama (if using local Qwen)

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull Qwen model
ollama pull qwen2.5:1.5b-instruct-q4_0
```

## Project Structure

```
Secured-Qwen-2.5-HomeAssistant-Smart-Home/
├── .env                    # Environment variables (create from template)
├── .gitignore             # Git ignore rules
├── docker-compose.yaml    # Docker configuration
├── appdaemon.service      # SystemD service file
├── start_appdaemon.sh     # AppDaemon startup script
├── chat_client.py         # PyQt5 chat client
├── README.md              # This file
└── hass_config/           # Home Assistant configuration
    ├── appdaemon/
    │   ├── apps/
    │   │   ├── qwen_assistant.py        # Basic Qwen integration
    │   │   └── qwen_assistant_secure.py # Security-hardened version
    │   └── logs/          # Log files directory
    └── custom_components/ # (if using custom components)
```

## Security Architecture

### 🛡️ Security Mitigations

The secure version (`qwen_assistant_secure.py`) implements multiple layers of protection based on LLM security best practices:

#### **Input Validation & Sanitization**
- **HTML Escaping** - Prevents XSS and injection attacks on all user inputs
- **Pattern Filtering** - Removes dangerous code patterns (script tags, eval, exec, import, etc.)
- **Length Limits** - Prevents DoS attacks via oversized inputs (1000 character limit)
- **Type Validation** - Ensures proper data types throughout the system

#### **Unified Action Mapping System**
- **Centralized Action Mapping** - Single `ACTION_MAPPING` dictionary defines all permitted actions
- **Entity Allowlist** - Only predefined entities can be controlled:
  - `switch.smarthome_node_dc_motor_fan`
  - `switch.smarthome_node_smart_home_light`
  - Temperature and humidity sensors
  - Motion sensor and counters
- **Service Allowlist** - Only approved services can be called (`switch/turn_on`, `switch/turn_off`)
- **Structured Validation** - Actions validated against mapping before execution

#### **Response Security & Validation**
- **LLM Output Validation** - Scans AI responses for malicious content and suspicious patterns
- **Structured JSON Responses** - Forces predictable response format for reliable action execution
- **Content Filtering** - Removes dangerous patterns from LLM outputs
- **Safe Fallback** - Security violations return safe error messages without information disclosure

#### **Conversation History Management**
- **Automatic Rotation** - History limited to 50 messages to prevent memory exhaustion
- **Age-based Clearing** - History automatically cleared after 7 days
- **Secure Storage** - Separate pickle file for secure version (`qwen_history_secure.pkl`)
- **Resource Limits** - Caps history length and API response sizes

#### **Enhanced Logging & Monitoring**
- **Secure Logging** - Sanitized log entries prevent log injection attacks
- **Timestamped Entries** - All logs include ISO timestamps for audit trails
- **Separate Log Files** - Secure version uses dedicated log file (`qwen_assistant_secure.log`)
- **Security Event Monitoring** - Logs unauthorized access attempts and security violations

#### **Network & Operational Security**
- **Local-only Operations** - No external API calls required
- **Token-based Authentication** - Secure HA API access with long-lived tokens
- **Timeout Controls** - Prevents hanging requests and resource exhaustion
- **Principle of Least Privilege** - Minimal permissions for all operations
- **Context Entity Sanitization** - All entity states sanitized before adding to prompts

### Action Execution Model

The system uses **structured JSON responses** for reliable and secure action execution:

#### Response Format
```json
{
  "action": "turn_on_fan",
  "message": "I'll turn on the fan for you."
}
```

#### Available Actions
- `turn_on_fan` - Turn on the DC motor fan
- `turn_off_fan` - Turn off the DC motor fan  
- `turn_on_light` - Turn on the smart home light
- `turn_off_light` - Turn off the smart home light

## Usage

### Web Interface
Access Home Assistant at `http://your-ip:8123` and use the built-in conversation interface.

### Chat Client
Run the PyQt5 desktop client:
```bash
python3 chat_client.py
```

### AppDaemon Dashboard
Access AppDaemon at `http://your-ip:5050`

### SystemD Service Management
```bash
# Start/stop service
sudo systemctl start appdaemon.service
sudo systemctl stop appdaemon.service

# View logs
sudo journalctl -u appdaemon.service -f

# Check status
sudo systemctl status appdaemon.service
```

## Troubleshooting

### Path Configuration Issues
1. Verify all `${PWD}` references are updated to actual paths
2. Check file permissions: `chmod +x start_appdaemon.sh`
3. Ensure log directory exists: `mkdir -p hass_config/appdaemon/logs`

### SystemD Service Issues
1. Check service status: `sudo systemctl status appdaemon.service`
2. View detailed logs: `sudo journalctl -u appdaemon.service -n 50`
3. Verify service file location: `/etc/systemd/system/appdaemon.service`
4. Reload after changes: `sudo systemctl daemon-reload`

### Home Assistant Recovery Mode
If HA enters recovery mode:
1. Check Docker logs: `docker logs homeassistant`
2. Verify `.env` file exists and has correct values
3. Ensure custom component files are present

### Qwen Connection Issues
1. Verify Ollama is running: `ollama list`
2. Check model is available: `ollama pull qwen2.5:1.5b-instruct-q4_0`
3. Test API: `curl http://localhost:11434/api/version`

### Security Validation Errors
1. Check AppDaemon logs for validation failures
2. Verify entities are in `ALLOWED_ENTITIES` list
3. Ensure actions are in `ACTION_MAPPING`
4. Review input sanitization logs for blocked content

## Development

### Adding New Actions
1. Add action to `ACTION_MAPPING` in `qwen_assistant_secure.py`
2. Ensure entity is in `ALLOWED_ENTITIES`
3. Update system prompt with new available actions
4. Test with both valid and invalid inputs

### Modifying Security Rules
1. Update sanitization patterns in `sanitize_input()`
2. Modify allowlists as needed
3. Test thoroughly with edge cases
4. Monitor logs for false positives

### Performance Optimization
1. Adjust `MAX_HISTORY_LENGTH` for memory usage
2. Tune `HISTORY_ROTATION_DAYS` for storage
3. Monitor conversation history file sizes
4. Consider implementing compression for logs

## Contributing

1. Fork the repository
2. Create feature branch
3. **Update all file paths** for your environment
4. Test security features thoroughly
5. Ensure no secrets in commits
6. Submit pull request

## License

MIT License - see LICENSE file for details.
