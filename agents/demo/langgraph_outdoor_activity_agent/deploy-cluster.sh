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

if ! command -v docker &> /dev/null; then
    echo "ERROR: docker not installed"
    exit 1
fi

if ! docker info > /dev/null 2>&1; then
    echo "ERROR: Docker is not running. Start Docker Desktop first: open -a Docker"
    exit 1
fi

if ! command -v envsubst &> /dev/null; then
    echo "ERROR: envsubst not found. Install with: brew install gettext"
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

NAMESPACE=$(oc project -q)
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

source .env

# Detect if using local Ollama or hosted model
if echo "$BASE_URL" | grep -q "localhost"; then
    echo "Detected local Ollama configuration. Checking cluster..."

    OLLAMA_POD=$(oc get pods -l app=ollama -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    if [ -z "$OLLAMA_POD" ]; then
        echo "ERROR: Ollama is not running in project '${NAMESPACE}'."
        echo "       Run ./setup-cluster.sh first to deploy Ollama and pull the model."
        exit 1
    fi
    echo "OK: Ollama running (pod: ${OLLAMA_POD})"

    # Replace localhost with in-cluster Ollama URL
    BASE_URL="http://ollama.${NAMESPACE}.svc.cluster.local:11434/v1"

    # Strip ollama/ prefix from MODEL_ID (not needed when connecting directly)
    if echo "$MODEL_ID" | grep -q "^ollama/"; then
        MODEL_ID="${MODEL_ID#ollama/}"
    fi

    # API_KEY not needed for in-cluster Ollama
    API_KEY="not-needed"
else
    echo "Using hosted model at: ${BASE_URL}"
fi

# Refresh MLflow token if logged into oc
if [ -n "$MLFLOW_TRACKING_URI" ] && oc whoami > /dev/null 2>&1; then
    MLFLOW_TRACKING_TOKEN=$(oc whoami -t)
fi

export CONTAINER_IMAGE BASE_URL MODEL_ID MLFLOW_TRACKING_URI MLFLOW_TRACKING_TOKEN MLFLOW_WORKSPACE MLFLOW_ENABLE_WORKSPACES

# Validate required env vars
for var in BASE_URL MODEL_ID CONTAINER_IMAGE NPS_API_KEY; do
    if [ -z "${!var}" ] || [ "${!var}" = "not-needed" ]; then
        echo "ERROR: $var is not set in .env (required for cluster deployment)"
        exit 1
    fi
done

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
