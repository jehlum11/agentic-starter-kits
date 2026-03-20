#!/bin/bash
#
# Deploy CrewAI Web Search Agent to OpenShift
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

## ============================================
# COPY SHARED IMAGES FOR DOCKER BUILD CONTEXT
## ============================================

cp -r ../../../images ./images && echo "Images copied into build context"
trap 'rm -rf ./images' EXIT

## ============================================
# DOCKER BUILD
## ============================================

docker buildx build --platform linux/amd64 -t "${CONTAINER_IMAGE}" -f Dockerfile --push . && echo "Docker build completed"

## ============================================
# OPENSHIFT CREATE SECRET
## ============================================

 oc delete secret crewai-websearch-agent-secrets --ignore-not-found && echo "Secret deleted"
 oc create secret generic crewai-websearch-agent-secrets --from-literal=api-key="${API_KEY}" && echo "Secret created"

## ============================================
# OPENSHIFT DELETE DEPLOYMENT, SERVICE, ROUTE
## ============================================

 oc delete deployment,service,route -l app=crewai-websearch-agent --ignore-not-found && echo "Previous resources cleaned up"

## ============================================
# OPENSHIFT APPLY DEPLOYMENT, SERVICE, ROUTE
## ============================================

envsubst < k8s/deployment.yaml | oc apply -f - && echo "Deployment applied"
oc apply -f k8s/service.yaml && echo "Service applied"
oc apply -f k8s/route.yaml && echo "Route applied"

oc rollout status deployment/crewai-websearch-agent --timeout=300s && echo "Deployment rolled out"

oc get deployment crewai-websearch-agent && echo "Deployment exists"
oc get service crewai-websearch-agent && echo "Service exists"
oc get route crewai-websearch-agent && echo "Route exists"
