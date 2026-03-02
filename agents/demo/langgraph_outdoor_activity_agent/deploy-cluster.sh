#!/bin/bash
#
# Deploy Outdoor Activity Agent to OpenShift cluster
#
# Prerequisites:
#   - oc CLI installed and logged in
#   - docker installed
#   - ./setup-cluster.sh already run (Ollama + LlamaStack deployed)
#   - .env file configured
#
# Usage:
#   ./deploy-cluster.sh
#

set -e

echo "=== Outdoor Activity Agent - Cluster Deployment ==="
echo ""

# Check prerequisites
if ! command -v oc &> /dev/null; then
    echo "ERROR: oc CLI not installed"
    exit 1
fi

if ! oc whoami > /dev/null 2>&1; then
    echo "ERROR: Not logged into OpenShift. Run: oc login ..."
    exit 1
fi

if [ ! -f .env ]; then
    echo "ERROR: .env file not found"
    exit 1
fi

source .env

# Auto-detect Ollama in-cluster URL if BASE_URL is still localhost
NAMESPACE=$(oc project -q)
if echo "$BASE_URL" | grep -q "localhost"; then
    BASE_URL="http://ollama.${NAMESPACE}.svc.cluster.local:11434/v1"
    echo "Auto-detected in-cluster Ollama URL: ${BASE_URL}"
fi

# Strip ollama/ prefix from MODEL_ID (not needed when connecting directly)
if echo "$MODEL_ID" | grep -q "^ollama/"; then
    MODEL_ID="${MODEL_ID#ollama/}"
    echo "Stripped ollama/ prefix from MODEL_ID: ${MODEL_ID}"
fi

# API_KEY not needed for in-cluster Ollama
if [ -z "$API_KEY" ] || [ "$API_KEY" = "not-needed" ]; then
    API_KEY="not-needed"
fi

export CONTAINER_IMAGE BASE_URL MODEL_ID

# Validate required env vars
for var in BASE_URL MODEL_ID CONTAINER_IMAGE NPS_API_KEY; do
    if [ -z "${!var}" ] || [ "${!var}" = "not-needed" ]; then
        echo "ERROR: $var is not set in .env (required for cluster deployment)"
        exit 1
    fi
done

# Check Ollama is running on cluster
echo "Checking Ollama on cluster..."
OLLAMA_POD=$(oc get pods -l app=ollama -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
if [ -z "$OLLAMA_POD" ]; then
    echo "ERROR: Ollama is not deployed. Run ./setup-cluster.sh first."
    exit 1
fi
echo "OK: Ollama running (pod: ${OLLAMA_POD})"

echo ""
echo "Cluster: $(oc whoami --show-server)"
echo "User: $(oc whoami)"
echo "Image: ${CONTAINER_IMAGE}"
echo "LLM: ${MODEL_ID} at ${BASE_URL}"
echo ""

# Step 1: Build and push Docker image
echo "--- Building Docker image ---"
docker buildx build --platform linux/amd64 -t "${CONTAINER_IMAGE}" -f Dockerfile --push . && echo "Docker build completed"

# Step 2: Create secrets
echo "--- Creating secrets ---"
oc delete secret langgraph-outdoor-activity-agent-secrets --ignore-not-found
oc create secret generic langgraph-outdoor-activity-agent-secrets \
    --from-literal=api-key="${API_KEY}" \
    --from-literal=nps-api-key="${NPS_API_KEY}" \
    && echo "Secrets created"

# Step 3: Deploy
echo "--- Deploying to OpenShift ---"
oc delete deployment,service,route -l app=langgraph-outdoor-activity-agent --ignore-not-found && echo "Previous resources cleaned up"

envsubst < k8s/deployment.yaml | oc apply -f - && echo "Deployment applied"
oc apply -f k8s/service.yaml && echo "Service applied"
oc apply -f k8s/route.yaml && echo "Route applied"

# Step 4: Wait for rollout
echo "--- Waiting for rollout ---"
oc rollout status deployment/langgraph-outdoor-activity-agent --timeout=300s

# Step 5: Print route
ROUTE_URL=$(oc get route langgraph-outdoor-activity-agent -o jsonpath='{.spec.host}' 2>/dev/null)
echo ""
echo "=== Deployment Complete ==="
echo "Route: https://${ROUTE_URL}"
echo ""
echo "Test with:"
echo "  curl -X POST https://${ROUTE_URL}/chat \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"message\": \"I want to go hiking near Denver this weekend. What day is best?\"}'"
