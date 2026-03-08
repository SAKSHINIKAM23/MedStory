#!/bin/bash
set -euo pipefail

PROJECT_ID="medexplain-demo"
REGION="us-central1"
SERVICE_NAME="medstory-api"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "🏗  Building container image..."
gcloud builds submit --tag "${IMAGE}" --project "${PROJECT_ID}" .

echo "🚀 Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE}" \
  --platform managed \
  --region "${REGION}" \
  --project "${PROJECT_ID}" \
  --allow-unauthenticated \
  --memory 4Gi \
  --cpu 4 \
  --timeout 900 \
  --concurrency 10 \
  --max-instances 1 \
  --service-account "medstory-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION}"

echo ""
echo "✅ Deployment complete! Service URL:"
gcloud run services describe "${SERVICE_NAME}" \
  --region "${REGION}" \
  --project "${PROJECT_ID}" \
  --format "value(status.url)"
