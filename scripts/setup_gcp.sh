#!/usr/bin/env bash
# One-time project setup for Redstring. Idempotent; safe to re-run.
set -euo pipefail
PROJECT=${PROJECT:-redstring-511910}
REGION=${REGION:-us-central1}
export PATH="$HOME/google-cloud-sdk/bin:$PATH"

gcloud config set project "$PROJECT"

echo "== enabling APIs"
gcloud services enable \
  run.googleapis.com aiplatform.googleapis.com firestore.googleapis.com firebase.googleapis.com \
  firebasestorage.googleapis.com storage.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com identitytoolkit.googleapis.com firebasehosting.googleapis.com \
  firebaserules.googleapis.com

echo "== Firebase"
npx -y firebase-tools projects:addfirebase "$PROJECT" 2>/dev/null || echo "(already a Firebase project)"

echo "== Firestore (native, $REGION)"
gcloud firestore databases describe --database="(default)" >/dev/null 2>&1 \
  || gcloud firestore databases create --location="$REGION" --type=firestore-native

echo "== IAM for the Cloud Run runtime service account"
NUM=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')
SA="$NUM-compute@developer.gserviceaccount.com"
for ROLE in roles/aiplatform.user roles/datastore.user roles/storage.objectAdmin roles/firebaseauth.viewer; do
  gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:$SA" --role="$ROLE" \
    --condition=None --quiet >/dev/null
done
echo "done. Next: create the Storage bucket + web app in Firebase console if not present, then scripts/deploy.sh"
