#!/bin/bash
# Script to start AppDaemon with environment variables loaded

# Load environment variables from .env file
if [ -f ${PWD}/.env ]; then
    export $(grep -v '^#' ${PWD}/.env | xargs)
    echo "Environment variables loaded from .env"
else
    echo "Warning: .env file not found"
fi

# Start AppDaemon
exec ${PWD}/hass_config/appdaemon-venv/bin/appdaemon -c ${PWD}/hass_config/appdaemon
