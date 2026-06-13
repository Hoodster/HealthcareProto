#!/usr/bin/env bash
# Provision Azure AI Search for RAG, seed guidelines, configure App Service.
#
# Prerequisites:
#   - az CLI logged in
#   - Key Vault Secrets Officer (to write secrets) + read for seed
#   - API_OPENAI in environment or .env (for seed embeddings if JSON lacks them — we use pre-embedded JSON)
#
# Usage:
#   ./scripts/setup_azure_search.sh
#   ./scripts/setup_azure_search.sh --skip-create   # service already exists
#   ./scripts/setup_azure_search.sh --skip-app    # only create + seed

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RG="${AZURE_RESOURCE_GROUP:-appsvc_linux_westeurope}"
LOCATION="${AZURE_LOCATION:-westeurope}"
VAULT="${KEY_VAULT_NAME:-azkvhtn4tglr3jlgw}"
WEBAPP="${AZURE_WEBAPP_NAME:-azaphtn4tglr3jlgw}"
SEARCH_NAME="${AZURE_SEARCH_NAME:-azsrhtn4tglr3jlgw}"
INDEX="${AZURE_SEARCH_INDEX:-healthcare-rag}"

SKIP_CREATE=false
SKIP_APP=false
for arg in "$@"; do
  case "$arg" in
    --skip-create) SKIP_CREATE=true ;;
    --skip-app) SKIP_APP=true ;;
  esac
done

if [[ -d .venv ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

echo "=== Azure AI Search setup ==="
echo "Resource group: $RG"
echo "Search service: $SEARCH_NAME"
echo "Key Vault:      $VAULT"
echo "Web App:        $WEBAPP"

if [[ "$SKIP_CREATE" == false ]]; then
  if az search service show -g "$RG" -n "$SEARCH_NAME" &>/dev/null; then
    echo "Search service $SEARCH_NAME already exists."
  else
    echo "Creating Azure AI Search (Basic)..."
    az search service create \
      -g "$RG" \
      -n "$SEARCH_NAME" \
      --sku basic \
      -l "$LOCATION" \
      --partition-count 1 \
      --replica-count 1
  fi
fi

ENDPOINT="https://${SEARCH_NAME}.search.windows.net"
PRIMARY_KEY="$(az search admin-key show -g "$RG" --service-name "$SEARCH_NAME" --query primaryKey -o tsv)"

echo "Storing secrets in Key Vault $VAULT..."
if az keyvault secret set --vault-name "$VAULT" --name azure-search-endpoint --value "$ENDPOINT" -o none 2>/dev/null; then
  az keyvault secret set --vault-name "$VAULT" --name azure-search-key --value "$PRIMARY_KEY" -o none
  USE_KV=true
else
  echo "WARNING: Key Vault write denied — App Service will use direct settings (not KV refs)."
  USE_KV=false
fi

export RAG_BACKEND=azure_search
export AZURE_SEARCH_ENDPOINT="$ENDPOINT"
export AZURE_SEARCH_KEY="$PRIMARY_KEY"
export AZURE_SEARCH_INDEX="$INDEX"

echo "Seeding index $INDEX from artifacts/rag_knowledge.json..."
python3 scripts/seed_azure_search.py

if [[ "$SKIP_APP" == false ]]; then
  echo "Configuring App Service $WEBAPP..."
  if [[ "${USE_KV:-false}" == true ]]; then
    az webapp config appsettings set \
      -g "$RG" \
      -n "$WEBAPP" \
      --settings \
        RAG_BACKEND=azure_search \
        AZURE_SEARCH_INDEX="$INDEX" \
        AZURE_SEARCH_ENDPOINT="@Microsoft.KeyVault(VaultName=${VAULT};SecretName=azure-search-endpoint)" \
        AZURE_SEARCH_KEY="@Microsoft.KeyVault(VaultName=${VAULT};SecretName=azure-search-key)" \
      -o none
  else
    az webapp config appsettings set \
      -g "$RG" \
      -n "$WEBAPP" \
      --settings \
        RAG_BACKEND=azure_search \
        AZURE_SEARCH_INDEX="$INDEX" \
        AZURE_SEARCH_ENDPOINT="$ENDPOINT" \
        AZURE_SEARCH_KEY="$PRIMARY_KEY" \
      -o none
  fi

  echo "Restarting App Service..."
  az webapp restart -g "$RG" -n "$WEBAPP"
fi

echo ""
echo "Done."
echo "  Endpoint: $ENDPOINT"
echo "  Index:    $INDEX"
echo "Verify: curl -s \"https://${WEBAPP}.azurewebsites.net/hp_proto/api/health?verify_rag=true\" | python3 -m json.tool"
