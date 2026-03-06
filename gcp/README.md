# GCP Cloud Run Deployment Guide

## Overview

The `outpace_b2b_intelligence` project deploys two Cloud Run services:

| Service | Image | Description |
|---|---|---|
| `outpace-api` | `outpace/backend` | FastAPI (Python 3.11) backend |
| `outpace-web` | `outpace/frontend` | React 19 / Vite SPA served by nginx |

---

## Prerequisites

### 1. GCP Project & APIs

Enable the required APIs (run once per project):

```bash
export PROJECT_ID=your-project-id
export REGION=us-central1

gcloud config set project $PROJECT_ID

gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com
```

### 2. Artifact Registry Repository

```bash
gcloud artifacts repositories create outpace \
  --repository-format=docker \
  --location=$REGION \
  --description="Outpace B2B Intelligence container images"
```

### 3. Service Accounts

Create least-privilege service accounts for each Cloud Run service:

```bash
# Backend service account
gcloud iam service-accounts create outpace-api-sa \
  --display-name="Outpace API Service Account"

# Frontend service account (no special permissions needed)
gcloud iam service-accounts create outpace-web-sa \
  --display-name="Outpace Web Service Account"

# Grant backend SA access to Secret Manager secrets
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:outpace-api-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### 4. Secret Manager Secrets

Create each secret (replace placeholder values with real credentials):

```bash
# MongoDB Atlas connection string
echo -n "mongodb+srv://user:password@cluster.mongodb.net/outpace_intelligence" | \
  gcloud secrets create outpace-mongo-url --data-file=-

# JWT signing secret (generate a strong random value)
openssl rand -base64 48 | \
  gcloud secrets create outpace-jwt-secret --data-file=-

# Third-party API keys
echo -n "your-mistral-api-key" | \
  gcloud secrets create outpace-mistral-api-key --data-file=-

echo -n "your-perplexity-api-key" | \
  gcloud secrets create outpace-perplexity-api-key --data-file=-

echo -n "your-highergov-api-key" | \
  gcloud secrets create outpace-highergov-api-key --data-file=-

# Rate limiting values
echo -n "100" | gcloud secrets create outpace-rate-limit-auth --data-file=-
echo -n "200" | gcloud secrets create outpace-rate-limit-default --data-file=-
```

---

## MongoDB Atlas Setup

1. Create a free or paid cluster at [cloud.mongodb.com](https://cloud.mongodb.com).
2. Under **Database Access**, create a database user with `readWrite` on the `outpace_intelligence` database.
3. Under **Network Access**, add `0.0.0.0/0` to the IP allowlist (Cloud Run IPs are dynamic; restrict using VPC connector for production hardening).
4. Copy the **Connection String** (SRV format):
   ```
   mongodb+srv://<user>:<password>@<cluster>.mongodb.net/outpace_intelligence?retryWrites=true&w=majority
   ```
5. Store it in Secret Manager as shown above (`outpace-mongo-url`).

---

## Update YAML Placeholders

Before deploying, substitute the placeholder values in the Cloud Run YAML files:

```bash
sed -i "s/PROJECT_ID/$PROJECT_ID/g" gcp/cloud-run-api.yaml gcp/cloud-run-web.yaml
sed -i "s/REGION/$REGION/g"         gcp/cloud-run-api.yaml gcp/cloud-run-web.yaml
```

---

## Manual Deployment

Submit a Cloud Build from the repository root:

```bash
gcloud builds submit . \
  --config=gcp/cloudbuild.yaml \
  --substitutions=_PROJECT_ID=$PROJECT_ID,_REGION=$REGION
```

Cloud Build will:
1. Build both Docker images in parallel.
2. Push each image tagged `:latest` and `:<git-sha>` to Artifact Registry.
3. Deploy `outpace-api` and `outpace-web` to Cloud Run.
4. Shift 100% traffic to the new revision.

---

## CI/CD Trigger from GitHub

Create a Cloud Build trigger connected to your GitHub repository:

```bash
# First, connect your GitHub repo in the GCP Console:
# Cloud Build → Triggers → Connect Repository

# Then create the trigger via CLI:
gcloud builds triggers create github \
  --name="outpace-deploy-main" \
  --repo-name="outpace_b2b_intelligence" \
  --repo-owner="YOUR_GITHUB_ORG" \
  --branch-pattern="^main$" \
  --build-config="gcp/cloudbuild.yaml" \
  --substitutions=_PROJECT_ID=$PROJECT_ID,_REGION=$REGION
```

Alternatively, use the GitHub Actions workflow at `.github/workflows/deploy-gcp.yml`, which authenticates via Workload Identity Federation and submits Cloud Build on every push to `main`.

### Workload Identity Federation Setup (for GitHub Actions)

```bash
# Create a Workload Identity Pool
gcloud iam workload-identity-pools create "github-pool" \
  --location="global" \
  --display-name="GitHub Actions Pool"

POOL_ID=$(gcloud iam workload-identity-pools describe "github-pool" \
  --location="global" --format="value(name)")

# Create a provider for GitHub OIDC
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="GitHub Provider" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.actor=assertion.actor" \
  --attribute-condition="assertion.repository=='YOUR_GITHUB_ORG/outpace_b2b_intelligence'"

# Create a deploy service account
gcloud iam service-accounts create outpace-deployer \
  --display-name="Outpace GitHub Actions Deployer"

# Grant necessary roles
for ROLE in roles/cloudbuild.builds.editor roles/run.admin roles/artifactregistry.writer roles/iam.serviceAccountUser; do
  gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:outpace-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="$ROLE"
done

# Allow the GitHub Actions pool to impersonate the deployer SA
gcloud iam service-accounts add-iam-policy-binding \
  "outpace-deployer@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/${POOL_ID}/attribute.repository/YOUR_GITHUB_ORG/outpace_b2b_intelligence"

# Print values needed for GitHub Secrets
echo "GCP_PROJECT_ID: $PROJECT_ID"
echo "GCP_SERVICE_ACCOUNT: outpace-deployer@${PROJECT_ID}.iam.gserviceaccount.com"
gcloud iam workload-identity-pools providers describe "github-provider" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --format="value(name)"
# ^ Set this value as GCP_WORKLOAD_IDENTITY_PROVIDER in GitHub Secrets
```

Add these three values as **GitHub repository secrets**:
- `GCP_PROJECT_ID`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_SERVICE_ACCOUNT`

---

## Custom Domain

Map a custom domain to each Cloud Run service via the GCP Console (**Cloud Run → Domain Mappings**), or via CLI:

```bash
# Backend API (e.g., api.outpace.io)
gcloud run domain-mappings create \
  --service=outpace-api \
  --domain=api.outpace.io \
  --region=$REGION

# Frontend (e.g., app.outpace.io)
gcloud run domain-mappings create \
  --service=outpace-web \
  --domain=app.outpace.io \
  --region=$REGION
```

Update your DNS provider with the CNAME/A records shown in the output. GCP provisions a managed TLS certificate automatically.

---

## Environment Variable Reference

| Variable | Source | Description |
|---|---|---|
| `MONGO_URL` | Secret Manager: `outpace-mongo-url` | MongoDB Atlas SRV connection string |
| `JWT_SECRET` | Secret Manager: `outpace-jwt-secret` | HS256/RS256 signing key for JWTs |
| `DB_NAME` | Hardcoded in YAML: `outpace_intelligence` | MongoDB database name |
| `MISTRAL_API_KEY` | Secret Manager: `outpace-mistral-api-key` | Mistral AI API key |
| `PERPLEXITY_API_KEY` | Secret Manager: `outpace-perplexity-api-key` | Perplexity AI API key |
| `HIGHERGOV_API_KEY` | Secret Manager: `outpace-highergov-api-key` | HigherGov API key |
| `RATE_LIMIT_AUTH` | Secret Manager: `outpace-rate-limit-auth` | Requests/minute for authenticated routes |
| `RATE_LIMIT_DEFAULT` | Secret Manager: `outpace-rate-limit-default` | Requests/minute for unauthenticated routes |

> **Note**: `MONGO_URL`, `JWT_SECRET`, and `DB_NAME` are required at startup. The backend exits with code 1 if any of these are missing.

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| Container fails to start | Missing required env var | Check Secret Manager secret names match YAML |
| `permission denied` on secrets | SA missing `secretmanager.secretAccessor` | Re-run IAM binding for the API service account |
| Build fails at push step | Artifact Registry repo doesn't exist | Run `gcloud artifacts repositories create` |
| 503 errors after deploy | Health check failing on `/api/health` | Check backend logs for startup errors |
| Cold start latency | `minScale: 0` | Already set to `1` in this config — no action needed |
