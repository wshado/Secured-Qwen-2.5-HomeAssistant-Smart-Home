# Security Mitigations Applied to QwenAssistantSecure

## Overview
This document outlines the comprehensive security mitigations applied to `qwen_assistant_secure.py` based on LLM security best practices and threat modeling for AI-powered home automation systems.

## Threat Model

### Potential Attack Vectors
1. **Prompt Injection** - Malicious inputs designed to manipulate LLM behavior
2. **Code Injection** - Attempts to execute arbitrary code through LLM responses
3. **Privilege Escalation** - Unauthorized access to restricted entities or services
4. **Data Exfiltration** - Attempts to extract sensitive information from context
5. **Denial of Service** - Resource exhaustion through oversized inputs or requests
6. **Log Injection** - Malicious content injected into log files
7. **Response Manipulation** - Crafted inputs to generate harmful outputs

## Applied Mitigations

### 1. Input Sanitization and Validation
- **HTML escaping** of all user inputs to prevent injection attacks
- **Pattern filtering** to remove dangerous code patterns:
  - Script tags (`<script>`, `javascript:`, `vbscript:`)
  - Code execution patterns (`eval()`, `exec()`, `import`, `__.*__`)
  - File system access (`../`, `system()`, `subprocess`, `os.`, `file()`, `open()`)
- **Length limits** (1000 chars) to prevent DoS attacks
- **Type validation** to ensure inputs are strings
- **Recursive sanitization** for nested data structures

### 2. Unified Action Mapping System
- **Centralized action mapping**: Single `ACTION_MAPPING` dictionary defines all permitted actions
- **Entity allowlist**: Only specific entities can be controlled
  - `switch.smarthome_node_dc_motor_fan`
  - `switch.smarthome_node_smart_home_light`
  - `sensor.smarthome_node_keystudio_temperature`
  - `sensor.smarthome_node_keystudio_humidity`
  - `binary_sensor.smarthome_node_motion_sensor`
  - `sensor.smarthome_node_led_activation_count`
  - `sensor.smarthome_node_buzzer_alert_count`
- **Service allowlist**: Only specific services can be called
  - `switch/turn_on`, `switch/turn_off`
- **Structured validation**: Actions validated against mapping before execution
- **Double validation**: Entity permissions checked at both action and execution levels

### 3. Conversation History Management
- **Automatic rotation**: History limited to 50 messages to prevent memory exhaustion
- **Age-based clearing**: History cleared after 7 days to limit data exposure
- **Secure storage**: Separate pickle file for secure version (`hass_config/appdaemon/logs/qwen_history_secure.pkl`)
- **File permission controls**: Restricted access to history files
- **Graceful degradation**: System continues operating if history files are corrupted

### 4. Post-Processing Validation
- **Response sanitization**: LLM outputs are validated and sanitized before execution
- **Malicious content detection**: Suspicious patterns filtered from responses:
  - Script injection attempts
  - Code execution patterns
  - Import statements and system calls
  - Attribute manipulation functions
- **Safe fallback**: Security violations return safe error messages without information disclosure
- **JSON validation**: Structured responses validated for proper format and content

### 5. Context Entity Sanitization
- **Value sanitization**: All entity states sanitized before adding to prompts
- **Type conversion**: Non-string values safely converted and sanitized
- **Context limiting**: Only essential context included in prompts
- **State validation**: Entity states validated before inclusion

### 6. Enhanced Logging and Monitoring
- **Secure logging**: Log messages sanitized to prevent log injection attacks
- **Timestamped entries**: All logs include ISO timestamps for audit trails
- **Separate log files**: Secure version uses dedicated log file (`hass_config/appdaemon/logs/qwen_assistant_secure.log`)
- **Security event logging**: Comprehensive logging of security-related events
- **Log rotation**: Automatic log file management to prevent disk exhaustion
- **Access control**: Restricted permissions on log files

### 7. Structured Response System
- **JSON response format**: LLM instructed to return structured JSON for actions
- **Action validation**: Only actions in `ACTION_MAPPING` are accepted
- **Fallback handling**: Graceful degradation when JSON parsing fails
- **Security instructions**: LLM explicitly instructed about security constraints
- **Scope limitation**: Responses limited to home automation tasks only
- **Command restrictions**: Explicit prohibition of code execution, file access, and system commands

### 8. Network and Resource Security
- **Local-only operations**: No external API calls or network requests
- **Timeout controls**: Request timeouts prevent resource exhaustion
- **Rate limiting**: Built-in delays and failure handling
- **Resource monitoring**: Memory and CPU usage awareness
- **Connection validation**: Secure API token validation for Home Assistant access

## Configuration Changes Required

### ⚠️ Path Configuration
**Before deployment, update file paths in:**
1. **Line 191**: `self.history_path = "hass_config/appdaemon/logs/qwen_history_secure.pkl"`
2. **Line 407**: `log_path = "hass_config/appdaemon/logs/qwen_assistant_secure.log"`

### AppDaemon Configuration
Update your `apps.yaml` to use the secure version:

```yaml
qwen_assistant_secure:
  module: qwen_assistant_secure
  class: QwenAssistantSecure
  qwen_url: "http://localhost:11434"
  qwen_model: "qwen2.5:1.5b-instruct-q4_0"
  ha_url: !env_var HA_URL
  ha_token: !env_var HA_TOKEN
  context_entities:
    - sensor.smarthome_node_keystudio_humidity
    - sensor.smarthome_node_keystudio_temperature
    - switch.smarthome_node_dc_motor_fan
    - switch.smarthome_node_smart_home_light
    - binary_sensor.smarthome_node_motion_sensor
```

### File Locations (Relative Paths)
- **Secure script**: `hass_config/appdaemon/apps/qwen_assistant_secure.py`
- **Secure history**: `hass_config/appdaemon/logs/qwen_history_secure.pkl`
- **Secure logs**: `hass_config/appdaemon/logs/qwen_assistant_secure.log`

## Security Benefits

1. **Prevents prompt injection** through comprehensive input sanitization
2. **Limits blast radius** with strict entity/service allowlists
3. **Reduces data exposure** through conversation history rotation and age limits
4. **Blocks malicious outputs** via multi-layer response validation
5. **Prevents log poisoning** through log message sanitization
6. **Enforces principle of least privilege** for all operations
7. **Eliminates string matching vulnerabilities** through structured JSON responses
8. **Provides single source of truth** for action definitions and validation
9. **Enables comprehensive audit trails** through enhanced logging
10. **Protects against resource exhaustion** through limits and timeouts

## Migration Steps

1. **Backup current configuration** and conversation history
2. **Update file paths** in the secure version for your environment
3. **Test the secure version** alongside the original in a safe environment
4. **Update AppDaemon configuration** to use secure class
5. **Monitor logs** for any blocked actions or security events
6. **Validate functionality** of all intended device controls
7. **Gradually phase out** the original version once validated
8. **Document any custom modifications** for future reference

## Security Monitoring

### Critical Security Events to Monitor
- `⚠️ Unauthorized entity access attempt: [entity_id]`
- `⚠️ Unauthorized action attempt: [action]`
- `⚠️ Suspicious content detected in LLM response`
- `⚠️ Input truncated due to length limit`
- `⚠️ Failed to parse JSON from LLM response`
- `🔄 Conversation history rotated due to length limit`
- `🔄 Conversation history cleared due to age`

### Log Analysis Recommendations
1. **Regular review** of security event logs
2. **Automated alerting** for repeated unauthorized attempts
3. **Trend analysis** for unusual patterns
4. **Performance monitoring** for resource usage
5. **Backup verification** of log files

## Structured Response Format

The system uses structured JSON responses for reliable and secure action execution:

### Expected LLM Response Format
```json
{
  "action": "turn_on_fan",
  "message": "I'll turn on the fan for you."
}
```

### Available Actions
- `turn_on_fan` - Turn on the DC motor fan
- `turn_off_fan` - Turn off the DC motor fan
- `turn_on_light` - Turn on the smart home light
- `turn_off_light` - Turn off the smart home light

### Security Validation Flow
1. **Parse JSON** from LLM response with error handling
2. **Validate action** exists in `ACTION_MAPPING`
3. **Check entity permissions** against allowlist
4. **Validate service call** against approved services
5. **Execute service call** with validated parameters
6. **Log action execution** with security validation status
7. **Return sanitized response** to user interface

## Advanced Security Recommendations

### Deployment Security
1. **File system permissions**: Restrict access to configuration and log files
2. **Network segmentation**: Isolate Home Assistant network from internet
3. **Regular updates**: Keep all dependencies and models updated
4. **Backup strategy**: Implement secure backup and recovery procedures
5. **Access logging**: Enable comprehensive audit trails

### Operational Security
1. **Regular security reviews**: Periodic assessment of security controls
2. **Incident response plan**: Procedures for handling security events
3. **User training**: Education on secure usage patterns
4. **Configuration management**: Version control for security configurations
5. **Penetration testing**: Regular security testing of the system

### Development Security
1. **Code review**: Security-focused review of all modifications
2. **Static analysis**: Automated security scanning of code
3. **Dependency scanning**: Regular vulnerability assessment of dependencies
4. **Secure coding practices**: Follow security guidelines for modifications
5. **Testing protocols**: Comprehensive security testing procedures

## Compliance and Standards

This implementation follows security principles from:
- **OWASP Top 10** for web application security
- **NIST Cybersecurity Framework** for risk management
- **ISO 27001** for information security management
- **CIS Controls** for cyber defense best practices
