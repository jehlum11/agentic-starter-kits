#!/bin/bash
#
# Remove all cluster resources deployed by setup-cluster.sh and deploy-cluster.sh
#
# Usage:
#   ./cleanup-cluster.sh
#

set -e

echo "=== Outdoor Activity Agent - Cluster Cleanup ==="
echo ""

if ! oc whoami > /dev/null 2>&1; then
    echo "ERROR: Not logged into OpenShift. Run: oc login ..."
    exit 1
fi

echo "Cluster: $(oc whoami --show-server)"
echo "Namespace: $(oc project -q)"
echo ""

echo "--- Removing agent ---"
oc delete deployment,service,route -l app=langgraph-outdoor-activity-agent --ignore-not-found
oc delete secret langgraph-outdoor-activity-agent-secrets --ignore-not-found

echo "--- Removing Ollama ---"
oc delete deployment,service -l app=ollama --ignore-not-found

echo ""
echo "=== Cleanup Complete ==="
