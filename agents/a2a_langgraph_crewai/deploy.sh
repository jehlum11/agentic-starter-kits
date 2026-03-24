#!/bin/bash
#
# Deploy A2A LangGraph ↔ CrewAI to OpenShift (two images, two Deployments)
#
# Usage (same shell as init):
#   source ./init.sh
#   ./deploy.sh
#
# Prerequisites:
#   - Environment loaded via source ./init.sh (see README)
#   - oc CLI installed and logged in to OpenShift cluster
#   - podman or docker with buildx
#   - Access to container registry (e.g., Quay.io)
#   - gettext (envsubst)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -z "${API_KEY:-}" ] || [ -z "${BASE_URL:-}" ] || [ -z "${MODEL_ID:-}" ] \
  || [ -z "${CONTAINER_IMAGE_CREW:-}" ] || [ -z "${CONTAINER_IMAGE_LANGGRAPH:-}" ]; then
  echo "ERROR: Required environment variables are missing."
  echo "From this directory run: source ./init.sh"
  echo "(after cp template.env .env and filling values)"
  exit 1
fi

export CONTAINER_IMAGE_CREW CONTAINER_IMAGE_LANGGRAPH BASE_URL MODEL_ID

## ============================================
# DOCKER BUILD
## ============================================

docker buildx build --platform linux/amd64 \
  --build-arg A2A_ROLE=crew \
  -t "${CONTAINER_IMAGE_CREW}" -f Dockerfile --push . && echo "Docker build (crew) completed"

docker buildx build --platform linux/amd64 \
  --build-arg A2A_ROLE=langgraph \
  -t "${CONTAINER_IMAGE_LANGGRAPH}" -f Dockerfile --push . && echo "Docker build (langgraph) completed"

## ============================================
# OPENSHIFT CREATE SECRET
## ============================================

oc delete secret a2a-langgraph-crewai-secrets --ignore-not-found && echo "Secret deleted"
oc create secret generic a2a-langgraph-crewai-secrets --from-literal=api-key="${API_KEY}" && echo "Secret created"

## ============================================
# OPENSHIFT DELETE DEPLOYMENT, SERVICE, ROUTE
## ============================================

oc delete deployment,service,route -l app.kubernetes.io/part-of=a2a-langgraph-crewai --ignore-not-found && echo "Previous resources cleaned up"

## ============================================
# OPENSHIFT APPLY SERVICE & ROUTE (hostnames for Agent Card URLs)
## ============================================

oc apply -f k8s/service-crew.yaml && echo "Service (crew) applied"
oc apply -f k8s/service-langgraph.yaml && echo "Service (langgraph) applied"
oc apply -f k8s/route-crew.yaml && echo "Route (crew) applied"
oc apply -f k8s/route-langgraph.yaml && echo "Route (langgraph) applied"

echo "=== Waiting for Route hostnames ==="
for _ in $(seq 1 60); do
  CREW_PUBLIC_HOST=$(oc get route a2a-crew-agent -o jsonpath='{.spec.host}' 2>/dev/null || true)
  LG_PUBLIC_HOST=$(oc get route a2a-langgraph-agent -o jsonpath='{.spec.host}' 2>/dev/null || true)
  if [ -n "${CREW_PUBLIC_HOST}" ] && [ -n "${LG_PUBLIC_HOST}" ]; then
    break
  fi
  sleep 1
done
if [ -z "${CREW_PUBLIC_HOST:-}" ] || [ -z "${LG_PUBLIC_HOST:-}" ]; then
  echo "ERROR: Could not read route hostnames. Check: oc get route"
  exit 1
fi

export CREW_A2A_PUBLIC_URL="https://${CREW_PUBLIC_HOST}"
export LANGGRAPH_A2A_PUBLIC_URL="https://${LG_PUBLIC_HOST}"

echo "CREW_A2A_PUBLIC_URL=${CREW_A2A_PUBLIC_URL}"
echo "LANGGRAPH_A2A_PUBLIC_URL=${LANGGRAPH_A2A_PUBLIC_URL}"

## ============================================
# OPENSHIFT APPLY DEPLOYMENTS
## ============================================

envsubst < k8s/deployment-crew.yaml | oc apply -f - && echo "Deployment (crew) applied"
envsubst < k8s/deployment-langgraph.yaml | oc apply -f - && echo "Deployment (langgraph) applied"

oc rollout status deployment/a2a-crew-agent --timeout=300s && echo "Deployment (crew) rolled out"
oc rollout status deployment/a2a-langgraph-agent --timeout=300s && echo "Deployment (langgraph) rolled out"

echo "=== Done ==="
oc get route a2a-crew-agent a2a-langgraph-agent
echo "Orchestrator (demo client): set LANGGRAPH_A2A_PUBLIC_URL to https://${LG_PUBLIC_HOST} and run: uv run python demo_client.py"
