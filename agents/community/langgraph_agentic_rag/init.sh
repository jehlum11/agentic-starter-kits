#!/bin/bash
# Usage:
#   ./init.sh

set -e

source .env && echo "Environment variables loading from .env file"

if [ -z "$CONTAINER_IMAGE" ]; then
    echo "CONTAINER_IMAGE not set, check .env file"
    exit 1
fi
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
if [ -z "$VECTOR_STORE_PATH" ]; then
    echo "VECTOR_STORE_PATH not set, check .env file"
    exit 1
fi


