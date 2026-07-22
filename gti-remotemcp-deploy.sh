#!/bin/bash
set -e

# Configuration - Edit these values before running
# Enter your Google Cloud project ID (find it at: https://console.cloud.google.com)
PROJECT_ID="YOUR_PROJECT_ID"
SERVICE_NAME="gti-mcp-service"
REGION="us-central1"

# NOTE: Replace these with your actual secrets or set them in your environment before running
# You can also use Google Secret Manager references in Cloud Run for better security.
# Generate a random token if not provided
AUTH_TOKEN=${MCP_AUTH_TOKEN:-$(openssl rand -hex 32)}
# VT_KEY is now passed via tool arguments
# VT_KEY=${VT_APIKEY:-"change-me-to-your-actual-vt-api-key"}

echo "=================================================="
echo "Deploying $SERVICE_NAME to project $PROJECT_ID"
echo "Region: $REGION"
echo "=================================================="

# Ensure the correct project is active
gcloud config set project "$PROJECT_ID"

# Deploy to Cloud Run using source deploy
# This automatically builds the container using Google Cloud Buildpacks
# and handles the Artifact Registry creation/management.
echo "Deploying service to Cloud Run (source deploy)..."
gcloud run deploy "$SERVICE_NAME" \
  --quiet \
  --source . \
  --platform managed \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --no-allow-unauthenticated \
  --set-env-vars STATELESS="1" \
  --set-env-vars VT_APIKEY="YOUR_VT_API_KEY"

echo "=================================================="
echo "Deployment Complete!"
echo "Service URL: $(gcloud run services describe $SERVICE_NAME --platform managed --region $REGION --project $PROJECT_ID --format 'value(status.url)')"
echo "SSE Endpoint: $(gcloud run services describe $SERVICE_NAME --platform managed --region $REGION --project $PROJECT_ID --format 'value(status.url)')/sse"
echo "Auth Token: $AUTH_TOKEN"
echo "=================================================="
