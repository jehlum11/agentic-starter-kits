#!/bin/bash
# Usage:
#   ./init.sh
#
# Prerequisites:
#   - oc CLI installed and logged in to OpenShift cluster
#   - docker installed
#   - Access to container registry (e.g., Quay.io)
#

set -e

source .env && echo "Environment variables loaded from .env file"

if [ -z "$API_KEY" ]; then
    echo "API_KEY not set, check .env file"
    exit 1
fi

if [ -z "$BASE_URL" ]; then
    echo "BASE_URL not set, check .env file"
    exit 1
fi

if [ -z "$MODEL_ID" ]; then
    echo "MODEL_ID not set, check .env file"
    exit 1
fi

if [ -z "$CONTAINER_IMAGE" ]; then
    echo "CONTAINER_IMAGE not set, check .env file"
    exit 1
fi


echo "Agent initialized successfully"
