#!/usr/bin/env bash
# bootstrap-test-infra.sh — infra de process-ai en el proyecto de TEST (margay-platform-test).
# Crea: service accounts (api/ui), los 4 secrets, y los permisos mínimos.
# NO hardcodea secretos: los pide por stdin silencioso (no quedan en el script ni en el historial).
#
# Correr con alguien que tenga permisos de IAM/Secret Manager en margay-platform-test.
# Uso: ./ops/bootstrap-test-infra.sh [PROJECT]
set -euo pipefail

PROJECT="${1:-margay-platform-test}"
API_SA="process-ai-api-sa@${PROJECT}.iam.gserviceaccount.com"
UI_SA="process-ai-ui-sa@${PROJECT}.iam.gserviceaccount.com"
DEPLOYER="github-deployer@${PROJECT}.iam.gserviceaccount.com"

echo "==> 1) Service accounts (runtime de Cloud Run)"
gcloud iam service-accounts create process-ai-api-sa --project "$PROJECT" \
  --display-name "process-ai API (test)" 2>/dev/null && echo "   + api-sa creada" || echo "   api-sa ya existe"
gcloud iam service-accounts create process-ai-ui-sa --project "$PROJECT" \
  --display-name "process-ai UI (test)" 2>/dev/null && echo "   + ui-sa creada" || echo "   ui-sa ya existe"

echo "==> 2) Secrets en Secret Manager"
prompt_secret() {
  local name="$1"
  if gcloud secrets describe "$name" --project "$PROJECT" >/dev/null 2>&1; then
    echo "   $name ya existe (rotar: printf '%s' NUEVO | gcloud secrets versions add $name --data-file=- --project $PROJECT)"
    return
  fi
  read -rs -p "   Valor de ${name}: " V; echo
  printf '%s' "$V" | gcloud secrets create "$name" --project "$PROJECT" \
    --replication-policy=automatic --data-file=-
  echo "   + $name creado"
}
prompt_secret process-ai-database-url            # connection string del Supabase de test (con password)
prompt_secret process-ai-openai-api-key          # key de OpenAI (podés reusar la de prod)
prompt_secret process-ai-supabase-service-role-key   # service_role key del Supabase de test

# artifact-signing-secret: se genera aleatorio (no hay que "conocerlo")
if gcloud secrets describe process-ai-artifact-signing-secret --project "$PROJECT" >/dev/null 2>&1; then
  echo "   process-ai-artifact-signing-secret ya existe"
else
  openssl rand -hex 32 | gcloud secrets create process-ai-artifact-signing-secret \
    --project "$PROJECT" --replication-policy=automatic --data-file=-
  echo "   + process-ai-artifact-signing-secret generado"
fi

echo "==> 3) La API-SA puede LEER sus secrets (secretAccessor)"
for S in process-ai-database-url process-ai-openai-api-key \
         process-ai-supabase-service-role-key process-ai-artifact-signing-secret; do
  gcloud secrets add-iam-policy-binding "$S" --project "$PROJECT" \
    --member="serviceAccount:${API_SA}" --role=roles/secretmanager.secretAccessor >/dev/null
  echo "   + secretAccessor $S -> api-sa"
done

echo "==> 4) El deployer (CI) puede DEPLOYAR Cloud Run con esas SAs (serviceAccountUser)"
for SA in "$API_SA" "$UI_SA"; do
  gcloud iam service-accounts add-iam-policy-binding "$SA" --project "$PROJECT" \
    --member="serviceAccount:${DEPLOYER}" --role=roles/iam.serviceAccountUser >/dev/null
  echo "   + serviceAccountUser $(echo "$SA" | cut -d@ -f1) -> deployer"
done

echo
echo "==> Infra de test lista. Falta (fuera de este script):"
echo "   - WIF en test: (desde margay-gcp-run-template) ./ops/bootstrap-github-wif.sh ${PROJECT} margaystudio process-ai-core"
echo "   - Variables del repo en GitHub: GCP_WIF_PROVIDER_TEST + GCP_DEPLOY_SA_TEST"
echo "   - Domain mapping de la UI: process.test.margaystudio.io -> servicio margay-process-ai-ui-test"
echo "   - Registrar la app 'process_ai' en el workspace de test (SSO)."
