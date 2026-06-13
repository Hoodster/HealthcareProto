# Azure Deployment Guide — HealthcareProto

This document describes what was deployed to Azure, how to redeploy, and how to maintain the environment.

---

## Current deployment (App Service stack)

| Item | Value |
|------|-------|
| **App URL** | https://azaphtn4tglr3jlgw.azurewebsites.net |
| **Swagger** | https://azaphtn4tglr3jlgw.azurewebsites.net/hp_proto/api/swagger |
| **Resource group** | `appsvc_linux_westeurope` |
| **Region** | West Europe |
| **azd environment** | `healthcare-proto` |
| **Subscription** | Azure for Students |

### Provisioned resources

| Resource | Name | Purpose |
|----------|------|---------|
| App Service (Linux container) | `azaphtn4tglr3jlgw` | Runs the FastAPI app |
| App Service Plan | `azsphtn4tglr3jlgw` | B1 Linux plan |
| Container Registry | `azcrhtn4tglr3jlgw` | Stores Docker images |
| PostgreSQL Flexible Server | `azpgkgbf6qhcbo5iq` | Database (`healthcare_db`) in **North Europe** |
| Key Vault | `azkvhtn4tglr3jlgw` | Stores `db-url` secret |
| Application Insights | `azaihtn4tglr3jlgw` | Monitoring & telemetry |
| Log Analytics | `azlawhtn4tglr3jlgw` | Centralized logs |

Configuration is defined in `infra/main.bicep` and orchestrated via [Azure Developer CLI (`azd`)](https://learn.microsoft.com/azure/developer/azure-developer-cli/) in `azure.yaml`.

---

## What was done (2026-06-06)

1. **Re-provisioned infrastructure** — previous App Service resources had been deleted; ran:
   ```bash
   azd provision --no-prompt --no-state
   ```
2. **Built Docker image** locally (`healthcare-proto-api:latest`).
3. **Pushed image to ACR** and updated App Service (workaround for an `azd deploy` packaging error):
   ```bash
   az acr login --name azcrhtn4tglr3jlgw --resource-group appsvc_linux_westeurope
   docker tag healthcare-proto-api:latest azcrhtn4tglr3jlgw.azurecr.io/healthcare-proto/api:latest
   docker push azcrhtn4tglr3jlgw.azurecr.io/healthcare-proto/api:latest
   az webapp restart -g appsvc_linux_westeurope -n azaphtn4tglr3jlgw
   ```
4. **Verified deployment** — Swagger endpoint returns HTTP 200.
5. **Added temporary PostgreSQL firewall rule** `AllowLocalMigration` for local IP `31.11.231.68` (required to run migrations from your machine).
6. **Granted Key Vault Secrets User** role to the deploying user (needed to read `db-url` for migrations).
7. **Ran database migrations** — all Alembic revisions applied; current head: `a3f1c9e7d502`.

---

## Database migrations

PostgreSQL is provisioned with database `healthcare_db`. The connection string is stored in Key Vault as `db-url` and injected into App Service as the `DB_URL` setting.

**Status:** schema is up to date at revision `a3f1c9e7d502 (head)`.

---

## Seed MIMIC demo data & DrugBank

After migrations, load clinical demo data into the online PostgreSQL database.

### MIMIC-III (mimiciii schema)

Uses `scripts/seed_mimic_data.py` — imports CSVs from `.sources/mimic/` into the Alembic-defined tables (`patients`, `admissions`, `labevents`, etc.).

**Do not** use `scripts/init_mimic_db.py` against Azure — it runs the full `.create_tables.sql` DDL and conflicts with the Alembic schema.

```bash
export DB_URL="$(az keyvault secret show \
  --vault-name azkvhtn4tglr3jlgw \
  --name db-url \
  --query value -o tsv)"

# Full import (~30–60 min over network to Azure)
python scripts/seed_mimic_data.py

# Resume specific tables only
python scripts/seed_mimic_data.py --only LABEVENTS PRESCRIPTIONS --batch 5000
```

Requires your IP in the PostgreSQL firewall (see migrations section).

Expected row counts (demo dataset):

| Table | ~Rows |
|-------|------:|
| patients | 100 |
| admissions | 129 |
| icustays | 136 |
| d_icd_diagnoses | 14,567 |
| d_labitems | 753 |
| diagnoses_icd | 1,761 |
| labevents | 76,074 |
| prescriptions | 10,398 |

### DrugBank (app.drugs & app.drug_interactions)

Uses `scripts/seed_drug_interactions.py` with `.sources/drugbank.xml` (~2.4 GB). Parsing takes 15–30 minutes; inserts another 10–20 minutes.

```bash
export DB_URL="$(az keyvault secret show \
  --vault-name azkvhtn4tglr3jlgw \
  --name db-url \
  --query value -o tsv)"

python scripts/seed_drug_interactions.py --batch 1000
```

Idempotent — safe to re-run (`ON CONFLICT DO NOTHING`).

After seeding, restart App Service so the in-memory drug store reloads:

```bash
az webapp restart -g appsvc_linux_westeurope -n azaphtn4tglr3jlgw
```

### Run migrations from your machine

**Prerequisite:** Your public IP must be allowed in the PostgreSQL firewall. A rule named `AllowLocalMigration` was added during deployment. If your IP changes, add a new rule:

```bash
MY_IP=$(curl -s https://ifconfig.me)
az postgres flexible-server firewall-rule create \
  -g appsvc_linux_westeurope \
  -n azpgkgbf6qhcbo5iq \
  --rule-name AllowLocalDev \
  --start-ip-address "$MY_IP" \
  --end-ip-address "$MY_IP"
```

Then run migrations:

```bash
cd /path/to/HealthcareProto
source .venv/bin/activate

# You need Key Vault Secrets User role on azkvhtn4tglr3jlgw to read db-url.
# One-time grant (if not already assigned):
# USER_ID=$(az ad signed-in-user show --query id -o tsv)
# KV_ID=$(az keyvault show -n azkvhtn4tglr3jlgw -g appsvc_linux_westeurope --query id -o tsv)
# az role assignment create --role "Key Vault Secrets User" --assignee "$USER_ID" --scope "$KV_ID"

# Option A — read connection string from Key Vault
export DB_URL="$(az keyvault secret show \
  --vault-name azkvhtn4tglr3jlgw \
  --name db-url \
  --query value -o tsv)"

# Option B — build from azd env (if .azure/healthcare-proto/.env exists)
# source .azure/healthcare-proto/.env
# export DB_URL="postgresql+psycopg2://${DB_ADMIN_USERNAME}:${DB_ADMIN_PASSWORD}@$(az postgres flexible-server show -g appsvc_linux_westeurope -n $POSTGRES_SERVER_NAME --query fullyQualifiedDomainName -o tsv):5432/healthcare_db?sslmode=require"

alembic upgrade head
alembic current   # verify revision
```

### Run migrations from App Service (no local firewall needed)

The container already has `DB_URL` resolved from Key Vault at runtime:

```bash
# SSH into the running container (interactive)
az webapp ssh -g appsvc_linux_westeurope -n azaphtn4tglr3jlgw

# Inside the container:
cd /app
alembic upgrade head
alembic current
```

---

## Redeploying the app

### Full deploy (infra + app)

```bash
azd up --no-prompt
```

If provisioning skips changes but resources were manually deleted, force a fresh deploy:

```bash
azd provision --no-prompt --no-state
azd deploy --no-prompt
```

### App-only deploy (recommended if `azd deploy` packaging fails)

Requires **Docker Desktop** running.

```bash
# 1. Build
docker build -t healthcare-proto-api .

# 2. Push to ACR
az acr login --name azcrhtn4tglr3jlgw --resource-group appsvc_linux_westeurope
docker tag healthcare-proto-api:latest azcrhtn4tglr3jlgw.azurecr.io/healthcare-proto/api:latest
docker push azcrhtn4tglr3jlgw.azurecr.io/healthcare-proto/api:latest

# 3. Restart App Service
az webapp restart -g appsvc_linux_westeurope -n azaphtn4tglr3jlgw
```

After deploying code that changes the schema, always run `alembic upgrade head` (see above).

---

## Environment variables

Managed by Bicep / azd (see `infra/main.bicep`):

| Variable | Source | Notes |
|----------|--------|-------|
| `DB_URL` | Key Vault reference | PostgreSQL connection string |
| `API_OPENAI` | azd env / Bicep param | OpenAI API key (embeddings + optional LLM) |
| `API_CLAUDE` | Key Vault / App Settings | Anthropic API key when `LLM_PROVIDER=claude` |
| `LLM_PROVIDER` | App Settings | Domyślny provider gdy brak `?llm_provider=` w żądaniu |
| `LLM_MODEL` | App Settings | e.g. `gpt-4o` or `claude-sonnet-4-6` |

**Przełącznik per request (Swagger):** `?llm_provider=openai|claude` na endpointach `/pipeline/evaluate-mimic`, `/pipeline/outcome-comparison`, `/pipeline/antiarrhythmic-safety`. Lista providerów: `GET /pipeline/llm-providers`.
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | App Insights | Auto-configured |
| `WEBSITES_PORT` | `8000` | Container listen port |

Local azd config lives in `.azure/healthcare-proto/.env` (git-ignored). **Do not commit this file.**

To view or update azd settings:

```bash
azd env get-values          # list all (includes secrets)
azd env set API_OPENAI <key>
# Optional — Claude provider for GenAI/RAG (RAG embeddings stay on OpenAI):
az keyvault secret set --vault-name <kv-name> --name ApiClaude --value <anthropic-key>
az webapp config appsettings set -g <rg> -n <app> --settings LLM_PROVIDER=claude LLM_MODEL=claude-sonnet-4-20250514
```

---

## Monitoring & logs

```bash
# Stream live logs
az webapp log tail -g appsvc_linux_westeurope -n azaphtn4tglr3jlgw

# Download log archive
az webapp log download -g appsvc_linux_westeurope -n azaphtn4tglr3jlgw --log-file webapp-logs.zip
```

Portal links:
- [Resource group](https://portal.azure.com/#@/resource/subscriptions/9427fe6c-dddd-45d5-88e9-07fa3225cd5c/resourceGroups/appsvc_linux_westeurope/overview)
- [App Service](https://portal.azure.com/#@/resource/subscriptions/9427fe6c-dddd-45d5-88e9-07fa3225cd5c/resourceGroups/appsvc_linux_westeurope/providers/Microsoft.Web/sites/azaphtn4tglr3jlgw)

---

## Alternative deployment: Container App (GitHub Actions)

A separate deployment exists on the `develop` branch via GitHub Actions:

| Item | Value |
|------|-------|
| **Container App** | `singleton-hpproto-containerapp` |
| **Resource group** | `finalproject` |
| **URL** | https://singleton-hpproto-containerapp.icydune-87df7818.polandcentral.azurecontainerapps.io |
| **Trigger** | Push to `develop` |
| **Workflow** | `.github/workflows/singleton-hpproto-containerapp-AutoDeployTrigger-*.yml` |

This is independent of the App Service stack above. Pushing to `develop` updates the Container App, not the App Service.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Cannot connect to Docker daemon` | Start Docker Desktop, then retry deploy |
| `azd deploy` — "no package artifacts found" | Use manual ACR push + `az webapp restart` (see above) |
| PostgreSQL connection timeout from local machine | Add your IP to PostgreSQL firewall rules |
| App returns 502 after deploy | Check logs; ensure image tag exists in ACR; wait ~1 min for container start |
| `azd provision` skips deleted resources | Run with `--no-state` flag |

---

## Prerequisites for future deploys

- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) (`az`) — logged in: `az login`
- [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) (`azd`)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) — required for local image builds
- Python 3.13 + venv — for running Alembic migrations locally

```bash
# Verify tooling
az account show
azd version
docker info
```
