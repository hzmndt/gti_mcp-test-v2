#!/bin/bash
set -e

# Configuration - Edit these values before running or set them as env vars
PROJECT_ID="YOUR_PROJECT_ID"
SERVICE_NAME="gti-mcp-service"
REGION="us-central1"
ALLOW_UNAUTHENTICATED=${ALLOW_UNAUTHENTICATED:-"true"}
ALLOWED_IPS=${ALLOWED_IPS:-""} # Semicolon-separated IPs (e.g. "1.1.1.1;2.2.2.2")

# VT_APIKEY can be loaded from Google Secret Manager (recommended) or set as a raw key
VT_API_KEY_SECRET=${VT_API_KEY_SECRET:-"gti-api-token:latest"}
VT_API_KEY_RAW=${VT_API_KEY_RAW:-""}

echo "=================================================="
echo "Deploying $SERVICE_NAME to project $PROJECT_ID"
echo "Region: $REGION"
echo "Allow Unauthenticated: $ALLOW_UNAUTHENTICATED"
echo "Allowed IPs: $ALLOWED_IPS"
echo "=================================================="

# Ensure the correct project is active
gcloud config set project "$PROJECT_ID"

AUTH_FLAG="--no-allow-unauthenticated"
if [ "$ALLOW_UNAUTHENTICATED" = "true" ]; then
  AUTH_FLAG="--allow-unauthenticated"
fi

SECRET_FLAG=""
ENV_VARS="STATELESS=1,ALLOWED_IPS=$ALLOWED_IPS"

if [ -n "$VT_API_KEY_RAW" ]; then
  ENV_VARS="$ENV_VARS,VT_APIKEY=$VT_API_KEY_RAW"
else
  SECRET_FLAG="--set-secrets=VT_APIKEY=$VT_API_KEY_SECRET"
fi

# Deploy to Cloud Run using source deploy
echo "Deploying service to Cloud Run (source deploy)..."
gcloud run deploy "$SERVICE_NAME" \
  --quiet \
  --source . \
  --platform managed \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  $AUTH_FLAG \
  --set-env-vars "$ENV_VARS" \
  $SECRET_FLAG

echo "=================================================="
echo "Deployment Complete!"
echo "Service URL: $(gcloud run services describe $SERVICE_NAME --platform managed --region $REGION --project $PROJECT_ID --format 'value(status.url)')"
echo "SSE Endpoint: $(gcloud run services describe $SERVICE_NAME --platform managed --region $REGION --project $PROJECT_ID --format 'value(status.url)')/sse"
echo "=================================================="
