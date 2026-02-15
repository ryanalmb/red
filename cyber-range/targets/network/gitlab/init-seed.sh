#!/bin/bash
# =============================================================================
# GitLab Seed Script — Cyber Range Tier 2 (Corporate)
# =============================================================================
# Runs as a sidecar or manual step after GitLab is fully up.
# Creates a repository with leaked secrets.
#
# CORP-22: API token leakage in commit history
# CORP-23: CI/CD variable exposure
# CORP-25: Kubernetes config in repository
# CORP-26: .env file with database and AD service account credentials
#
# DO NOT deploy outside the cyber-range.
# =============================================================================
set -e

GITLAB_URL="${GITLAB_URL:-http://gitlab:8082}"
GITLAB_TOKEN="${GITLAB_TOKEN:-}"
ROOT_PASSWORD="5iveL!fe"

echo "[gitlab-seed] Waiting for GitLab to be ready..."
for i in $(seq 1 120); do
    if curl -sf "${GITLAB_URL}/-/readiness" > /dev/null 2>&1; then
        echo "[gitlab-seed] GitLab is ready."
        break
    fi
    sleep 5
done

# Get a personal access token via API (GitLab 14.x)
echo "[gitlab-seed] Creating personal access token..."
GITLAB_TOKEN=$(curl -sf -X POST "${GITLAB_URL}/api/v4/session" \
    -d "login=root&password=${ROOT_PASSWORD}" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('private_token',''))" 2>/dev/null || echo "")

if [ -z "$GITLAB_TOKEN" ]; then
    # Fallback: use oauth token endpoint
    GITLAB_TOKEN=$(curl -sf -X POST "${GITLAB_URL}/oauth/token" \
        -d "grant_type=password&username=root&password=${ROOT_PASSWORD}" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || echo "")
fi

if [ -z "$GITLAB_TOKEN" ]; then
    echo "[gitlab-seed] WARNING: Could not obtain GitLab token. Seed data must be added manually."
    echo "[gitlab-seed] Manual steps:"
    echo "  1. Login to ${GITLAB_URL} as root / ${ROOT_PASSWORD}"
    echo "  2. Create project 'infrastructure'"
    echo "  3. Add .env file with AD credentials"
    echo "  4. Add k8s-config.yaml with cluster credentials"
    exit 0
fi

HEADER="PRIVATE-TOKEN: ${GITLAB_TOKEN}"

# Create 'infrastructure' project
echo "[gitlab-seed] Creating 'infrastructure' project..."
PROJECT_ID=$(curl -sf -X POST "${GITLAB_URL}/api/v4/projects" \
    -H "${HEADER}" \
    -d "name=infrastructure&visibility=internal&description=Infrastructure as Code - deployment configs" \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")

if [ -z "$PROJECT_ID" ]; then
    echo "[gitlab-seed] Project may already exist, skipping..."
    exit 0
fi

# CORP-26: .env file with AD service account credentials
echo "[gitlab-seed] Adding .env file (CORP-26)..."
ENV_CONTENT=$(cat <<'ENVFILE'
# Infrastructure Environment Variables
# Last updated: 2025-12-15

# Database
DB_HOST=postgres
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=corporate

# Active Directory Service Account (for LDAP queries)
AD_DOMAIN=PSYCHE.LOCAL
AD_SERVICE_USER=svc_repl
AD_SERVICE_PASSWORD=Repl1cate!
AD_BASE_DN=DC=psyche,DC=local

# Jenkins
JENKINS_URL=http://jenkins:8081
JENKINS_USER=admin
JENKINS_TOKEN=admin

# Redis
REDIS_URL=redis://redis:6379/0

# AWS (development — read-only)
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_REGION=us-east-1
ENVFILE
)

curl -sf -X POST "${GITLAB_URL}/api/v4/projects/${PROJECT_ID}/repository/files/.env" \
    -H "${HEADER}" \
    -H "Content-Type: application/json" \
    -d "$(python3 -c "import json; print(json.dumps({'branch':'main','content':'''${ENV_CONTENT}''','commit_message':'Add environment config'}))")" \
    > /dev/null 2>&1 || echo "[gitlab-seed] .env upload failed"

# CORP-25: Kubernetes config
echo "[gitlab-seed] Adding k8s config (CORP-25)..."
K8S_CONTENT=$(cat <<'K8SFILE'
apiVersion: v1
kind: Config
clusters:
- cluster:
    server: https://k8s.psyche.local:6443
    certificate-authority-data: LS0tLS1CRUdJTi...
  name: psyche-production
contexts:
- context:
    cluster: psyche-production
    user: deploy-admin
  name: production
current-context: production
users:
- name: deploy-admin
  user:
    token: eyJhbGciOiJSUzI1NiIsImtpZCI6IkRFRkFVTFQifQ.eyJpc3MiOiJrdWJlcm5ldGVzL3NlcnZpY2VhY2NvdW50Iiwic3ViIjoic3lzdGVtOnNlcnZpY2VhY2NvdW50OmRlZmF1bHQ6ZGVwbG95LWFkbWluIn0.FAKE_TOKEN_FOR_CYBER_RANGE
K8SFILE
)

curl -sf -X POST "${GITLAB_URL}/api/v4/projects/${PROJECT_ID}/repository/files/k8s-config.yaml" \
    -H "${HEADER}" \
    -H "Content-Type: application/json" \
    -d "$(python3 -c "import json; print(json.dumps({'branch':'main','content':'''${K8S_CONTENT}''','commit_message':'Add kubernetes deployment config'}))")" \
    > /dev/null 2>&1 || echo "[gitlab-seed] k8s config upload failed"

# CORP-22: Add and then "remove" an API token (stays in git history)
echo "[gitlab-seed] Planting API token in commit history (CORP-22)..."
curl -sf -X POST "${GITLAB_URL}/api/v4/projects/${PROJECT_ID}/repository/files/config.py" \
    -H "${HEADER}" \
    -H "Content-Type: application/json" \
    -d '{"branch":"main","content":"# Config\nAPI_TOKEN = \"glpat-PSYCHE-LEAKED-TOKEN-1234567890\"\nSECRET_KEY = \"psyche-internal-secret-key-do-not-share\"\n","commit_message":"Add application config"}' \
    > /dev/null 2>&1

# Now "remove" the token (but it stays in history)
curl -sf -X PUT "${GITLAB_URL}/api/v4/projects/${PROJECT_ID}/repository/files/config.py" \
    -H "${HEADER}" \
    -H "Content-Type: application/json" \
    -d '{"branch":"main","content":"# Config\nAPI_TOKEN = \"REDACTED\"\nSECRET_KEY = \"REDACTED\"\n","commit_message":"Remove leaked credentials (oops)"}' \
    > /dev/null 2>&1

echo "[gitlab-seed] GitLab seed complete."
echo "[gitlab-seed] Project ID: ${PROJECT_ID}"
echo "[gitlab-seed] Leaked: .env (AD svc_repl creds), k8s-config.yaml (cluster token), config.py history (API token)"
