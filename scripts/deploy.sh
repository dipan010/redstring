#!/usr/bin/env bash
# Deploy the API to Cloud Run and the web app + rules to Firebase.
set -euo pipefail
PROJECT=${PROJECT:-redstring-511910}
REGION=${REGION:-us-central1}
GEMINI_MODEL=${GEMINI_MODEL:-gemini-2.5-flash}
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$HOME/google-cloud-sdk/bin:$PATH"

if [[ "${1:-}" != "--web-only" ]]; then
  echo "== Cloud Run: redstring-api"
  gcloud run deploy redstring-api \
    --project "$PROJECT" --region "$REGION" --source "$ROOT/backend" \
    --allow-unauthenticated \
    --min-instances 1 --max-instances 4 --no-cpu-throttling \
    --cpu 1 --memory 1Gi --concurrency 40 --timeout 300 \
    --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT,GOOGLE_CLOUD_LOCATION=$REGION,GEMINI_MODEL=$GEMINI_MODEL,STORAGE_BUCKET=$PROJECT.firebasestorage.app"
fi

echo "== Firebase Hosting + rules"
(cd "$ROOT/frontend" && npm run build)
(cd "$ROOT" && npx -y firebase-tools deploy --project "$PROJECT" --only hosting,firestore,storage)
echo "Live at https://$PROJECT.web.app"
