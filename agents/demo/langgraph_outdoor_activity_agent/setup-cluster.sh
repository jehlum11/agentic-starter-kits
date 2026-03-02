#!/bin/bash
#
# Set up cluster dependencies for the Outdoor Activity Agent
#
# Prompts for model type (local Ollama or hosted), configures the
# environment, and deploys Ollama if needed.
#
# Run this ONCE before deploy-cluster.sh.
#
# Prerequisites:
#   - oc CLI installed and logged in to OpenShift cluster
#   - .env file configured
#
# Usage:
#   ./setup-cluster.sh
#

set -e

echo "=== Outdoor Activity Agent - Cluster Setup ==="
echo ""

# Check oc login
if ! oc whoami > /dev/null 2>&1; then
    echo "ERROR: Not logged into OpenShift. Run: oc login ..."
    exit 1
fi

NAMESPACE=$(oc project -q)
echo "Cluster: $(oc whoami --show-server)"
echo "User: $(oc whoami)"
echo ""
echo "Current project: ${NAMESPACE}"
echo "  [y] Deploy to this project"
echo "  [n] Create a new project"
echo "  [q] Quit"
read -p "Choice: " answer
if [ "$answer" = "q" ] || [ "$answer" = "Q" ]; then
    echo "Aborted."
    exit 0
elif [ "$answer" = "n" ] || [ "$answer" = "N" ]; then
    read -p "New project name: " new_project
    oc new-project "$new_project" 2>/dev/null || oc project "$new_project"
    NAMESPACE="$new_project"
elif [ "$answer" != "y" ] && [ "$answer" != "Y" ]; then
    echo "Aborted."
    exit 0
fi
echo ""

# Load env
if [ -f .env ]; then
    source .env
else
    echo "ERROR: .env file not found"
    exit 1
fi

## ============================================
# Choose model type
## ============================================
echo "How will the LLM be served?"
echo "  [1] Local Ollama (deploy Ollama on this cluster)"
echo "  [2] Hosted model (OpenAI, Azure, or other remote endpoint)"
read -p "Choice: " model_choice
echo ""

if [ "$model_choice" = "2" ]; then
    ## ============================================
    # Hosted model setup
    ## ============================================
    echo "--- Hosted Model Configuration ---"
    echo ""

    read -p "BASE_URL (e.g. https://api.openai.com/v1): " hosted_url
    read -p "MODEL_ID (e.g. gpt-4o-mini): " hosted_model
    read -p "API_KEY: " hosted_key

    # Update .env with hosted values
    sed -i.bak "s|^BASE_URL=.*|BASE_URL=${hosted_url}|" .env
    sed -i.bak "s|^MODEL_ID=.*|MODEL_ID=${hosted_model}|" .env
    sed -i.bak "s|^API_KEY=.*|API_KEY=${hosted_key}|" .env
    rm -f .env.bak

    echo ""
    echo "=== Setup Complete (Hosted Model) ==="
    echo ""
    echo "  BASE_URL: ${hosted_url}"
    echo "  MODEL_ID: ${hosted_model}"
    echo "  API_KEY:  ${hosted_key:0:10}..."
    echo ""
    echo "No Ollama deployment needed."
    echo "Next step: ./deploy-cluster.sh"
    exit 0
fi

## ============================================
# Local Ollama setup
## ============================================
echo "--- Step 1: Deploying Ollama ---"

oc delete deployment,service -l app=ollama --ignore-not-found && echo "Previous Ollama resources cleaned up"

oc apply -f k8s/ollama-deployment.yaml && echo "Ollama deployment applied"
oc apply -f k8s/ollama-service.yaml && echo "Ollama service applied"

echo "Waiting for Ollama to be ready..."
oc rollout status deployment/ollama --timeout=300s

## ============================================
# Pull model
## ============================================
echo ""
echo "--- Step 2: Pulling model into Ollama ---"

OLLAMA_POD=$(oc get pods -l app=ollama -o jsonpath='{.items[0].metadata.name}')
echo "Ollama pod: ${OLLAMA_POD}"

# Use MODEL_ID from .env, strip ollama/ prefix
PULL_MODEL="${MODEL_ID#ollama/}"
echo "Pulling ${PULL_MODEL} (this may take a few minutes)..."
oc exec "${OLLAMA_POD}" -- ollama pull "${PULL_MODEL}"

echo ""
echo "Models available:"
oc exec "${OLLAMA_POD}" -- ollama list

## ============================================
# Check NPS API Key
## ============================================
echo ""
echo "--- Step 3: Checking NPS API Key ---"

if [ -n "$NPS_API_KEY" ]; then
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 \
        -H "X-Api-Key: $NPS_API_KEY" \
        "https://developer.nps.gov/api/v1/parks?limit=1" 2>/dev/null)
    if [ "$HTTP_CODE" = "200" ]; then
        echo "OK: NPS API key is valid"
    else
        echo "WARN: NPS API returned HTTP ${HTTP_CODE}. Check your NPS_API_KEY."
    fi
else
    echo "WARN: NPS_API_KEY not set"
fi

## ============================================
# Check MLflow (optional)
## ============================================
echo ""
echo "--- Step 4: Checking MLflow ---"

if [ -n "$MLFLOW_TRACKING_URI" ]; then
    TOKEN=${MLFLOW_TRACKING_TOKEN:-$(oc whoami -t 2>/dev/null)}
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -H "X-MLflow-Workspace: ${MLFLOW_WORKSPACE:-default}" \
        "${MLFLOW_TRACKING_URI}/api/2.0/mlflow/experiments/search" \
        -d '{"max_results": 1}' 2>/dev/null)
    if [ "$HTTP_CODE" = "200" ]; then
        echo "OK: MLflow reachable at ${MLFLOW_TRACKING_URI}"
    else
        echo "WARN: MLflow returned HTTP ${HTTP_CODE}"
    fi
else
    echo "SKIP: MLFLOW_TRACKING_URI not set (tracing disabled)"
fi

## ============================================
# Summary
## ============================================
OLLAMA_URL="http://ollama.${NAMESPACE}.svc.cluster.local:11434"

echo ""
echo "=== Cluster Setup Complete (Local Ollama) ==="
echo ""
echo "  Ollama: ${OLLAMA_URL}"
echo "  Model:  ${PULL_MODEL}"
echo ""
echo "Next step: ./deploy-cluster.sh"
