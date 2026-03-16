#!/bin/bash
#
# Deploy AutoGen Agent to OpenShift (with MCP AutoML Server)
#
# Usage:
#   ./deploy.sh
#
# Prerequisites:
#   - oc CLI installed and logged in to OpenShift cluster
#   - podman or docker installed
#   - Access to container registry (e.g., Quay.io)
#

set -e  # Exit on error

source .env
export CONTAINER_IMAGE BASE_URL MODEL_ID
export CONTAINER_IMAGE_MCP DEPLOYMENT_URL DEPLOYMENT_TOKEN
export MCP_SERVER_URL="${MCP_SERVER_URL:-http://mcp-automl:8080/sse}"

## ============================================
# MCP AutoML Server (build + deploy)
## ============================================
./mcp_automl_template/deploy_mcp.sh

# Set MCP_SERVER_URL from MCP Route (for agent deployment env)
MCP_ROUTE_HOST=$(oc get route mcp-automl -o jsonpath='{.spec.host}' 2>/dev/null || true)
if [ -n "$MCP_ROUTE_HOST" ]; then
  export MCP_SERVER_URL="https://${MCP_ROUTE_HOST}/sse"
  echo "MCP_SERVER_URL set to ${MCP_SERVER_URL}"
fi

## ============================================
# DOCKER BUILD – AutoGen Agent
## ============================================

docker buildx build --platform linux/amd64 -t "${CONTAINER_IMAGE}" -f Dockerfile --push . && echo "AutoGen agent Docker build completed"

## ============================================
# OPENSHIFT – AutoGen Agent SECRET
## ============================================

oc delete secret autogen-agent-secrets --ignore-not-found && echo "Secret deleted"
oc create secret generic autogen-agent-secrets --from-literal=api-key="${API_KEY}" && echo "Secret created"

## ============================================
# OPENSHIFT – AutoGen Agent DELETE OLD
## ============================================

oc delete deployment,service,route -l app=autogen-agent --ignore-not-found && echo "Previous AutoGen resources cleaned up"

## ============================================
# OPENSHIFT – AutoGen Agent APPLY
## ============================================
envsubst < k8s/deployment.yaml | oc apply -f - && echo "AutoGen deployment applied"
oc apply -f k8s/service.yaml && echo "AutoGen service applied"
oc apply -f k8s/route.yaml && echo "AutoGen route applied"

oc rollout status deployment/autogen-agent --timeout=300s && echo "AutoGen deployment rolled out"

oc get deployment autogen-agent && echo "AutoGen deployment exists"
oc get service autogen-agent && echo "AutoGen service exists"
oc get route autogen-agent && echo "AutoGen route exists"
