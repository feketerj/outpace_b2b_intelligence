# Secrets Management Guide

**OutPace B2B Intelligence Platform**
Last Updated: 2026-01-15

---

## Overview

This document describes how to migrate from environment-variable-based secrets to a proper secrets management solution for production deployments.

### Current State (Development)

```
.env file → Environment Variables → Application
```

**Limitations:**
- Secrets in plain text on disk
- No audit trail for access
- Manual rotation required
- No version control for secrets
- Risk of accidental commit

### Target State (Production)

```
Secrets Manager → Injected at Runtime → Application
                     ↑
              (No disk storage)
```

**Benefits:**
- Encrypted at rest and in transit
- Full audit trail
- Automatic rotation support
- Centralized management
- Access control policies

---

## Secrets Inventory

| Secret | Current Source | Sensitivity | Rotation Frequency |
|--------|---------------|-------------|-------------------|
| `JWT_SECRET` | `.env` | Critical | Quarterly |
| `MONGO_URL` | `.env` | High | On compromise |
| `HIGHERGOV_API_KEY` | `.env` | High | Quarterly |
| `PERPLEXITY_API_KEY` | `.env` | High | Quarterly |
| `MISTRAL_API_KEY` | `.env` | High | Quarterly |

---

## Option 1: GCP Secret Manager (Recommended for GCP hosting)

### Setup

1. **Create secrets in GCP:**

```bash
# Set project
export PROJECT_ID="your-gcp-project"

# JWT Secret
echo -n "$(openssl rand -base64 32)" | gcloud secrets create outpace-production-jwt-secret --data-file=-

# Database URL
echo -n "mongodb://user:password@host:27017/outpace_intelligence" | gcloud secrets create outpace-production-mongo-url --data-file=-

# API Keys (JSON payload)
echo -n '{"highergov":"key1","perplexity":"key2","mistral":"key3"}' | gcloud secrets create outpace-production-api-keys --data-file=-
```

2. **Grant access to the runtime service account:**

```bash
gcloud secrets add-iam-policy-binding outpace-production-jwt-secret \
  --member="serviceAccount:YOUR_SA@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

3. **Configure environment:**

```bash
SECRETS_BACKEND=gcp
GCP_PROJECT_ID=your-gcp-project
ENVIRONMENT=production
```

---

## Option 2: AWS Secrets Manager

### Setup

1. **Create secrets in AWS:**

```bash
# JWT Secret
aws secretsmanager create-secret \
    --name outpace/production/jwt-secret \
    --secret-string "$(openssl rand -base64 32)"

# Database URL
aws secretsmanager create-secret \
    --name outpace/production/mongo-url \
    --secret-string "mongodb://user:password@host:27017/outpace_intelligence"

# API Keys (as JSON)
aws secretsmanager create-secret \
    --name outpace/production/api-keys \
    --secret-string '{"highergov":"key1","perplexity":"key2","mistral":"key3"}'
```

2. **IAM Policy for application:**

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "secretsmanager:GetSecretValue"
            ],
            "Resource": [
                "arn:aws:secretsmanager:us-east-1:*:secret:outpace/production/*"
            ]
        }
    ]
}
```

3. **Application integration:**

Create `backend/utils/secrets.py`:

```python
"""
Secrets management abstraction layer.

Supports multiple backends:
- Environment variables (development)
- AWS Secrets Manager (production)
- HashiCorp Vault (enterprise)
"""

import os
import json
import logging
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

# Backend selection
SECRETS_BACKEND = os.environ.get("SECRETS_BACKEND", "env")


class SecretsProvider:
    """Abstract base for secrets providers."""

    def get_secret(self, key: str) -> Optional[str]:
        raise NotImplementedError


class EnvSecretsProvider(SecretsProvider):
    """Development: read from environment variables."""

    def get_secret(self, key: str) -> Optional[str]:
        return os.environ.get(key)


class AWSSecretsProvider(SecretsProvider):
    """Production: read from AWS Secrets Manager."""

    def __init__(self):
        import boto3
        self.client = boto3.client('secretsmanager')
        self._cache = {}

    def get_secret(self, key: str) -> Optional[str]:
        # Map env var names to AWS secret paths
        secret_map = {
            "JWT_SECRET": "outpace/production/jwt-secret",
            "MONGO_URL": "outpace/production/mongo-url",
            "HIGHERGOV_API_KEY": ("outpace/production/api-keys", "highergov"),
            "PERPLEXITY_API_KEY": ("outpace/production/api-keys", "perplexity"),
            "MISTRAL_API_KEY": ("outpace/production/api-keys", "mistral"),
        }

        if key not in secret_map:
            logger.warning(f"[secrets] Unknown secret key: {key}")
            return None

        mapping = secret_map[key]

        # Simple secret (string value)
        if isinstance(mapping, str):
            return self._fetch_secret(mapping)

        # JSON secret (key within object)
        secret_path, json_key = mapping
        secret_json = self._fetch_secret(secret_path)
        if secret_json:
            try:
                data = json.loads(secret_json)
                return data.get(json_key)
            except json.JSONDecodeError:
                logger.error(f"[secrets] Failed to parse JSON secret: {secret_path}")
        return None

    def _fetch_secret(self, secret_name: str) -> Optional[str]:
        if secret_name in self._cache:
            return self._cache[secret_name]

        try:
            response = self.client.get_secret_value(SecretId=secret_name)
            value = response.get('SecretString')
            self._cache[secret_name] = value
            logger.info(f"[secrets] Loaded secret: {secret_name}")
            return value
        except Exception as e:
            logger.error(f"[secrets] Failed to fetch {secret_name}: {e}")
            return None


class VaultSecretsProvider(SecretsProvider):
    """Enterprise: read from HashiCorp Vault."""

    def __init__(self):
        import hvac
        self.client = hvac.Client(
            url=os.environ.get("VAULT_ADDR", "http://localhost:8200"),
            token=os.environ.get("VAULT_TOKEN")
        )
        self._cache = {}

    def get_secret(self, key: str) -> Optional[str]:
        secret_path = f"secret/data/outpace/{key.lower()}"

        if secret_path in self._cache:
            return self._cache[secret_path]

        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=f"outpace/{key.lower()}"
            )
            value = response['data']['data'].get('value')
            self._cache[secret_path] = value
            logger.info(f"[secrets] Loaded secret from Vault: {key}")
            return value
        except Exception as e:
            logger.error(f"[secrets] Failed to fetch {key} from Vault: {e}")
            return None


@lru_cache()
def get_secrets_provider() -> SecretsProvider:
    """Get the configured secrets provider (singleton)."""
    providers = {
        "env": EnvSecretsProvider,
        "aws": AWSSecretsProvider,
        "vault": VaultSecretsProvider,
    }

    provider_class = providers.get(SECRETS_BACKEND, EnvSecretsProvider)
    logger.info(f"[secrets] Using secrets backend: {SECRETS_BACKEND}")
    return provider_class()


def get_secret(key: str, default: str = None) -> Optional[str]:
    """
    Get a secret value.

    Args:
        key: Secret name (e.g., "JWT_SECRET")
        default: Default value if not found

    Returns:
        Secret value or default
    """
    provider = get_secrets_provider()
    value = provider.get_secret(key)

    if value is None and default is not None:
        logger.warning(f"[secrets] Using default for {key}")
        return default

    return value
```

4. **Update application to use secrets provider:**

In `backend/database.py`:

```python
from utils.secrets import get_secret

def init_database():
    mongo_url = get_secret("MONGO_URL", "mongodb://localhost:27017")
    db_name = get_secret("DB_NAME", "outpace_intelligence")
    # ...
```

In `backend/routes/auth.py`:

```python
from utils.secrets import get_secret

JWT_SECRET = get_secret("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET not configured")
```

5. **Docker configuration:**

```yaml
# docker-compose.production.yml
services:
  api:
    environment:
      - SECRETS_BACKEND=aws
      - AWS_REGION=us-east-1
    # Use IAM role instead of credentials
```

### Automatic Rotation

```bash
# Enable rotation for JWT_SECRET
aws secretsmanager rotate-secret \
    --secret-id outpace/production/jwt-secret \
    --rotation-lambda-arn arn:aws:lambda:us-east-1:123456789:function:SecretsRotation \
    --rotation-rules AutomaticallyAfterDays=90
```

---

## Option 2: HashiCorp Vault

### Setup

1. **Start Vault (development):**

```bash
vault server -dev -dev-root-token-id="root"
```

2. **Configure secrets:**

```bash
export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='root'

# Enable KV secrets engine
vault secrets enable -path=secret kv-v2

# Store secrets
vault kv put secret/outpace/jwt_secret value="$(openssl rand -base64 32)"
vault kv put secret/outpace/mongo_url value="mongodb://user:pass@host:27017/db"
vault kv put secret/outpace/highergov_api_key value="your-key"
vault kv put secret/outpace/perplexity_api_key value="your-key"
vault kv put secret/outpace/mistral_api_key value="your-key"
```

3. **Application policy:**

```hcl
# outpace-policy.hcl
path "secret/data/outpace/*" {
  capabilities = ["read"]
}
```

```bash
vault policy write outpace-read outpace-policy.hcl
```

4. **Docker configuration:**

```yaml
# docker-compose.production.yml
services:
  api:
    environment:
      - SECRETS_BACKEND=vault
      - VAULT_ADDR=http://vault:8200
      - VAULT_TOKEN=${VAULT_TOKEN}  # Or use AppRole auth
```

---

## Option 3: Docker Secrets (Swarm)

For Docker Swarm deployments:

1. **Create secrets:**

```bash
echo "your-jwt-secret" | docker secret create jwt_secret -
echo "mongodb://..." | docker secret create mongo_url -
```

2. **Use in compose:**

```yaml
# docker-compose.swarm.yml
services:
  api:
    secrets:
      - jwt_secret
      - mongo_url
    environment:
      - JWT_SECRET_FILE=/run/secrets/jwt_secret
      - MONGO_URL_FILE=/run/secrets/mongo_url

secrets:
  jwt_secret:
    external: true
  mongo_url:
    external: true
```

3. **Application code:**

```python
def get_secret_from_file_or_env(key: str) -> str:
    """Read secret from file (Docker secrets) or environment."""
    file_key = f"{key}_FILE"
    file_path = os.environ.get(file_key)

    if file_path and os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return f.read().strip()

    return os.environ.get(key)
```

---

## Option 4: Kubernetes Secrets

For Kubernetes deployments:

1. **Create secrets:**

```bash
kubectl create secret generic outpace-secrets \
    --from-literal=jwt-secret="$(openssl rand -base64 32)" \
    --from-literal=mongo-url="mongodb://..." \
    --from-literal=highergov-api-key="..."
```

2. **Use in deployment:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: outpace-api
spec:
  template:
    spec:
      containers:
        - name: api
          envFrom:
            - secretRef:
                name: outpace-secrets
```

3. **With External Secrets Operator (recommended):**

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: outpace-secrets
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: SecretStore
  target:
    name: outpace-secrets
  data:
    - secretKey: jwt-secret
      remoteRef:
        key: outpace/production/jwt-secret
```

---

## Migration Checklist

### Phase 1: Preparation

- [ ] Choose secrets management solution
- [ ] Set up secrets manager infrastructure
- [ ] Create secrets with current values
- [ ] Add `backend/utils/secrets.py` abstraction
- [ ] Test locally with `SECRETS_BACKEND=env`

### Phase 2: Integration

- [ ] Update all secret consumers to use `get_secret()`
- [ ] Test with `SECRETS_BACKEND=aws` (or chosen backend)
- [ ] Update CI/CD to inject secrets
- [ ] Update Docker configurations

### Phase 3: Deployment

- [ ] Deploy to staging with secrets manager
- [ ] Verify all functionality works
- [ ] Remove secrets from `.env` files
- [ ] Deploy to production
- [ ] Enable secret rotation

### Phase 4: Cleanup

- [ ] Delete `.env` files from servers
- [ ] Audit access logs
- [ ] Document rotation procedures
- [ ] Train team on new process

---

## Security Best Practices

1. **Least Privilege:** Applications should only access secrets they need
2. **Audit Logging:** Enable CloudTrail (AWS) or Audit Device (Vault)
3. **Rotation:** Rotate secrets quarterly at minimum
4. **No Defaults:** Never hardcode default secrets in production
5. **Encryption:** Use TLS for all secrets manager communication
6. **Backup:** Maintain encrypted backups of secrets
7. **Access Control:** Use IAM roles, not access keys

---

## Troubleshooting

### "Secret not found"

```bash
# AWS: Check secret exists
aws secretsmanager describe-secret --secret-id outpace/production/jwt-secret

# Vault: Check path
vault kv get secret/outpace/jwt_secret
```

### "Access denied"

```bash
# AWS: Check IAM policy
aws iam simulate-principal-policy \
    --policy-source-arn arn:aws:iam::123456789:role/OutpaceAPIRole \
    --action-names secretsmanager:GetSecretValue \
    --resource-arns arn:aws:secretsmanager:us-east-1:123456789:secret:outpace/*

# Vault: Check token permissions
vault token lookup
```

### "Connection refused"

```bash
# Check secrets manager is reachable
curl -v https://secretsmanager.us-east-1.amazonaws.com/

# For Vault
curl -v $VAULT_ADDR/v1/sys/health
```
