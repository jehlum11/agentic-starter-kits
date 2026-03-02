#!/bin/bash
#
# Set up cluster dependencies for the Outdoor Activity Agent
#
# Deploys Ollama with the required model on the OpenShift cluster.
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
echo "Namespace: ${NAMESPACE}"
echo ""

# Load env
if [ -f .env ]; then
    source .env
else
    echo "ERROR: .env file not found"
    exit 1
fi

## ============================================
# STEP 1: Deploy Ollama
## ============================================
echo "--- Step 1: Deploying Ollama ---"

oc delete deployment,service -l app=ollama --ignore-not-found && echo "Previous Ollama resources cleaned up"

oc apply -f k8s/ollama-deployment.yaml && echo "Ollama deployment applied"
oc apply -f k8s/ollama-service.yaml && echo "Ollama service applied"

echo "Waiting for Ollama to be ready..."
oc rollout status deployment/ollama --timeout=300s

## ============================================
# STEP 2: Pull model into Ollama
## ============================================
echo ""
echo "--- Step 2: Pulling model into Ollama ---"

OLLAMA_POD=$(oc get pods -l app=ollama -o jsonpath='{.items[0].metadata.name}')
echo "Ollama pod: ${OLLAMA_POD}"

echo "Pulling qwen2.5:7b (this may take a few minutes)..."
oc exec "${OLLAMA_POD}" -- ollama pull qwen2.5:7b

echo ""
echo "Models available:"
oc exec "${OLLAMA_POD}" -- ollama list

## ============================================
# STEP 3: Check NPS API Key
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
# STEP 4: Check MLflow (optional)
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
echo "=== Cluster Setup Complete ==="
echo ""
echo "Ollama is running at: ${OLLAMA_URL}"
echo ""
echo "Next step: ./deploy-cluster.sh"
