#!/bin/bash
#
# init.sh - Environment bootstrap for the CrewAI Web Search Agent
#
# Loads environment variables from the .env file located next to this script,
# validates that all required variables (API_KEY, BASE_URL, MODEL_ID,
# CONTAINER_IMAGE) are set, and ensures the shared milvus_data directory
# exists at the repository root.

# Resolve the directory containing this script (works when sourced or executed)
# BASH_SOURCE works in bash; ${(%):-%x} is the zsh equivalent
AGENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-${(%):-%x}}")" && pwd)"
REPO_ROOT="$AGENT_DIR/../../.."
ENV_FILE="$AGENT_DIR/.env"

# 1. Load .env, export variables, and collect their names for validation
ENV_VARS=()

if [ -f "$ENV_FILE" ]; then
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line//$'\r'/}"
        line="${line#"${line%%[![:space:]]*}"}"
        [[ -z "$line" || "$line" == \#* ]] && continue
        export "$line"
        ENV_VARS+=("${line%%=*}")
    done < "$ENV_FILE"
    echo "Environment variables loaded from $ENV_FILE"
else
    echo "ERROR: .env file not found at $ENV_FILE"
    return 1 2>/dev/null || exit 1
fi

# 2. Validate every variable found in .env
for var_name in "${ENV_VARS[@]}"; do
    var_value=$(eval echo "\$$var_name")
    if [ -z "$var_value" ]; then
        echo "  ERROR: $var_name is empty. Check your .env file."
        return 1 2>/dev/null || exit 1
    fi
    local_lower=$(echo "$var_name" | tr '[:upper:]' '[:lower:]')
    if [[ "$local_lower" == *password* || "$local_lower" == *apikey* || "$local_lower" == *api_key* || "$local_lower" == *secret* || "$local_lower" == *token* ]]; then
        echo "  $var_name=****"
    else
        echo "  $var_name=$var_value"
    fi
done

# 3. Ensure milvus_data directory exists at repo root
MILVUS_DIR="$REPO_ROOT/milvus_data"

if [ -d "$MILVUS_DIR" ]; then
    echo "milvus_data directory exists in root folder"
else
    if mkdir -p "$MILVUS_DIR"; then
        echo "Created milvus_data directory at: $MILVUS_DIR"
    else
        echo "ERROR: Failed to create $MILVUS_DIR"
        return 1 2>/dev/null || exit 1
    fi
fi
