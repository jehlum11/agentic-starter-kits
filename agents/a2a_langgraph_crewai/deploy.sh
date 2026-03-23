#!/usr/bin/env bash
#
# Build two images (crew | langgraph from the same Dockerfile) and deploy to OpenShift.
#
# Prerequisites: oc logged in, project selected, podman or docker buildx, envsubst,
#                container registry push access.
#
# Usage:
#   cp template.env .env   # fill API_KEY, BASE_URL, MODEL_ID, CONTAINER_IMAGE_*
#   ./deploy.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f .env ]; then
  echo "ERROR: .env not found. Copy template.env to .env and fill required variables."
  exit 1
fi

# shellcheck disable=SC1091
set -a
source .env
set +a

: "${API_KEY:?Set API_KEY in .env}"
: "${BASE_URL:?Set BASE_URL in .env}"
: "${MODEL_ID:?Set MODEL_ID in .env}"
: "${CONTAINER_IMAGE_CREW:?Set CONTAINER_IMAGE_CREW in .env}"
: "${CONTAINER_IMAGE_LANGGRAPH:?Set CONTAINER_IMAGE_LANGGRAPH in .env}"

echo "=== Building & pushing images (linux/amd64) ==="
docker buildx build --platform linux/amd64 \
  --build-arg A2A_ROLE=crew \
  -t "${CONTAINER_IMAGE_CREW}" -f Dockerfile --push .
docker buildx build --platform linux/amd64 \
  --build-arg A2A_ROLE=langgraph \
  -t "${CONTAINER_IMAGE_LANGGRAPH}" -f Dockerfile --push .

echo "=== OpenShift: secret ==="
oc delete secret a2a-langgraph-crewai-secrets --ignore-not-found
oc create secret generic a2a-langgraph-crewai-secrets --from-literal=api-key="${API_KEY}"

echo "=== Services & Routes (hostnames used for Agent Card public URLs) ==="
oc apply -f k8s/service-crew.yaml
oc apply -f k8s/service-langgraph.yaml
oc apply -f k8s/route-crew.yaml
oc apply -f k8s/route-langgraph.yaml

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
export CONTAINER_IMAGE_CREW CONTAINER_IMAGE_LANGGRAPH BASE_URL MODEL_ID

echo "CREW_A2A_PUBLIC_URL=${CREW_A2A_PUBLIC_URL}"
echo "LANGGRAPH_A2A_PUBLIC_URL=${LANGGRAPH_A2A_PUBLIC_URL}"

echo "=== Deployments ==="
envsubst < k8s/deployment-crew.yaml | oc apply -f -
envsubst < k8s/deployment-langgraph.yaml | oc apply -f -

oc rollout status deployment/a2a-crew-agent --timeout=300s
oc rollout status deployment/a2a-langgraph-agent --timeout=300s

echo "=== Done ==="
oc get route a2a-crew-agent a2a-langgraph-agent
echo "Orchestrator (demo client): set LANGGRAPH_A2A_PUBLIC_URL to https://${LG_PUBLIC_HOST} and run: uv run python demo_client.py"
