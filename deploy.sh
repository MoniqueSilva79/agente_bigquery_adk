#!/usr/bin/env bash
# Deploy do agente no Cloud Run com o CLI do ADK.
# Pré-requisitos: gcloud autenticado e APIs Vertex AI, Cloud Run e BigQuery ativas.
set -euo pipefail

PROJETO="${GOOGLE_CLOUD_PROJECT:?defina GOOGLE_CLOUD_PROJECT}"
REGIAO="${GOOGLE_CLOUD_LOCATION:-us-central1}"
CONTA_SERVICO="agente-bq@${PROJETO}.iam.gserviceaccount.com"

# 1. Conta de serviço com o mínimo de privilégio (leitura de dados + execução de jobs)
gcloud iam service-accounts create agente-bq --project "$PROJETO" \
  --display-name "Agente IA BigQuery (somente leitura)" 2>/dev/null || true
for papel in roles/bigquery.dataViewer roles/bigquery.jobUser roles/aiplatform.user; do
  gcloud projects add-iam-policy-binding "$PROJETO" \
    --member "serviceAccount:${CONTA_SERVICO}" --role "$papel" --condition=None >/dev/null
done

# 2. Deploy (execute a partir da pasta acima deste repositório)
cd "$(dirname "$0")/.."
adk deploy cloud_run \
  --project "$PROJETO" \
  --region "$REGIAO" \
  --service_name agente-bigquery \
  --with_ui \
  ./agente_bigquery_adk

echo "Lembre de configurar a conta de serviço ${CONTA_SERVICO} no serviço do Cloud Run."
