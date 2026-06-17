# deploy_supabase_local.ps1
# Script para desplegar los contenedores de Supabase directamente desde tu máquina local
# hacia Azure Container Apps. (Útil ya que no se pudo crear un Service Principal para GitHub Actions).

$ErrorActionPreference = "Stop"

# === 1. CONFIGURACIÓN ===
$RG_NAME = "rg-evangelista-prod"
$ACA_ENV = "cae-evangelista"
$LOCATION = "southcentralus"
$POSTGRES_HOST = "pg-evangelista-prod.postgres.database.azure.com"

# IMPORTANTE: Reemplaza estos valores con los que hayas generado (puedes ver el .env.example)
$DB_PASSWORD = "EIP_S3cur3!2025#"
$JWT_SECRET = "REEMPLAZAR_CON_TU_JWT_SECRET_DE_32_CARACTERES"
$ANON_KEY = "REEMPLAZAR_CON_TU_ANON_KEY"
$SERVICE_ROLE_KEY = "REEMPLAZAR_CON_TU_SERVICE_ROLE_KEY"
$STORAGE_ACCOUNT = "stevangelistadocs"
$STORAGE_KEY = "REEMPLAZAR_CON_STORAGE_KEY"

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " DESPLEGANDO SUPABASE EN AZURE CONTAINER APPS" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

# ── Gotrue (Auth) ──
Write-Host "[1/4] Desplegando Gotrue (Auth)..." -ForegroundColor Yellow
& az containerapp create `
    --name ca-gotrue `
    --resource-group $RG_NAME `
    --environment $ACA_ENV `
    --image supabase/gotrue:v2.164.0 `
    --target-port 9999 `
    --ingress internal `
    --min-replicas 1 `
    --max-replicas 2 `
    --cpu 0.25 --memory 0.5Gi `
    --secrets "supabase-jwt-secret=$JWT_SECRET" `
    --env-vars `
        "GOTRUE_API_HOST=0.0.0.0" `
        "GOTRUE_API_PORT=9999" `
        "API_EXTERNAL_URL=https://supabase-api.evangelistaco.com" `
        "GOTRUE_DB_DRIVER=postgres" `
        "GOTRUE_DB_DATABASE_URL=postgres://supabase_auth_admin:$($DB_PASSWORD)@$($POSTGRES_HOST):5432/postgres?sslmode=require" `
        "GOTRUE_SITE_URL=https://plataforma.evangelistaco.com" `
        "GOTRUE_URI_ALLOW_LIST=https://plataforma.evangelistaco.com" `
        "GOTRUE_DISABLE_SIGNUP=false" `
        "GOTRUE_JWT_ADMIN_ROLES=service_role" `
        "GOTRUE_JWT_AUD=authenticated" `
        "GOTRUE_JWT_DEFAULT_GROUP_NAME=authenticated" `
        "GOTRUE_JWT_EXP=3600" `
        "GOTRUE_JWT_SECRET=secretref:supabase-jwt-secret" `
        "GOTRUE_EXTERNAL_EMAIL_ENABLED=true" `
        "GOTRUE_MAILER_AUTOCONFIRM=false"

# ── PostgREST (REST API) ──
Write-Host "[2/4] Desplegando PostgREST (API de Datos)..." -ForegroundColor Yellow
& az containerapp create `
    --name ca-postgrest `
    --resource-group $RG_NAME `
    --environment $ACA_ENV `
    --image postgrest/postgrest:v12.2.3 `
    --target-port 3000 `
    --ingress internal `
    --min-replicas 1 `
    --max-replicas 3 `
    --cpu 0.25 --memory 0.5Gi `
    --secrets "supabase-jwt-secret=$JWT_SECRET" `
    --env-vars `
        "PGRST_DB_URI=postgres://authenticator:$($DB_PASSWORD)@$($POSTGRES_HOST):5432/postgres?sslmode=require" `
        "PGRST_DB_SCHEMAS=public,storage,graphql_public" `
        "PGRST_DB_ANON_ROLE=anon" `
        "PGRST_JWT_SECRET=secretref:supabase-jwt-secret" `
        "PGRST_DB_USE_LEGACY_GUCS=false"

# ── Storage ──
Write-Host "[3/4] Desplegando Storage..." -ForegroundColor Yellow
& az containerapp create `
    --name ca-storage `
    --resource-group $RG_NAME `
    --environment $ACA_ENV `
    --image supabase/storage-api:v1.11.13 `
    --target-port 5000 `
    --ingress internal `
    --min-replicas 1 `
    --max-replicas 2 `
    --cpu 0.25 --memory 0.5Gi `
    --secrets "supabase-jwt-secret=$JWT_SECRET" `
    --env-vars `
        "ANON_KEY=$ANON_KEY" `
        "SERVICE_KEY=$SERVICE_ROLE_KEY" `
        "POSTGREST_URL=http://ca-postgrest" `
        "PGRST_JWT_SECRET=secretref:supabase-jwt-secret" `
        "DATABASE_URL=postgres://supabase_storage_admin:$($DB_PASSWORD)@$($POSTGRES_HOST):5432/postgres?sslmode=require" `
        "FILE_SIZE_LIMIT=52428800" `
        "STORAGE_BACKEND=s3" `
        "GLOBAL_S3_BUCKET=evangelista-vault" `
        "GLOBAL_S3_ENDPOINT=https://$($STORAGE_ACCOUNT).blob.core.windows.net" `
        "GLOBAL_S3_FORCE_PATH_STYLE=false" `
        "GLOBAL_S3_PROTOCOL=https" `
        "AWS_ACCESS_KEY_ID=$STORAGE_ACCOUNT" `
        "AWS_SECRET_ACCESS_KEY=$STORAGE_KEY" `
        "AUTH_JWT_SECRET=secretref:supabase-jwt-secret" `
        "REGION=auto" `
        "TENANT_ID=stub"

# ── Kong (API Gateway) ──
Write-Host "[4/4] Desplegando Kong (API Gateway)..." -ForegroundColor Yellow

$SHARE_NAME = "kong-config"
$STORAGE_MOUNT_NAME = "kong-volume"

Write-Host "Configurando Azure Files para Kong..." -ForegroundColor Cyan
& az storage share create --name $SHARE_NAME --account-name $STORAGE_ACCOUNT --account-key $STORAGE_KEY --output none

$KONG_YML_PATH = Join-Path $PSScriptRoot "..\..\kong\kong.yml"
if (-not (Test-Path $KONG_YML_PATH)) {
    $KONG_YML_PATH = ".\kong\kong.yml"
}
& az storage file upload --account-name $STORAGE_ACCOUNT --account-key $STORAGE_KEY --share-name $SHARE_NAME --source $KONG_YML_PATH --path "kong.yml" --output none

Write-Host "Vinculando Azure Files a Container Apps Env..." -ForegroundColor Cyan
& az containerapp env storage set `
    --name $ACA_ENV `
    --resource-group $RG_NAME `
    --storage-name $STORAGE_MOUNT_NAME `
    --azure-file-account-name $STORAGE_ACCOUNT `
    --azure-file-account-key $STORAGE_KEY `
    --azure-file-share-name $SHARE_NAME `
    --access-mode ReadOnly `
    --output none

Write-Host "Generando configuración YAML y creando Container App..." -ForegroundColor Cyan
$ENV_ID = & az containerapp env show --name $ACA_ENV --resource-group $RG_NAME --query id -o tsv

$KONG_YAML = @"
location: $LOCATION
properties:
  environmentId: $ENV_ID
  configuration:
    ingress:
      external: true
      targetPort: 8000
  template:
    containers:
      - name: ca-kong
        image: kong:2.8.1
        env:
          - name: KONG_DATABASE
            value: "off"
          - name: KONG_DECLARATIVE_CONFIG
            value: "/home/kong/kong.yml"
          - name: KONG_DNS_ORDER
            value: "LAST,A,CNAME"
          - name: KONG_PLUGINS
            value: "request-transformer,cors,key-auth,acl,basic-auth"
          - name: SUPABASE_ANON_KEY
            value: "$ANON_KEY"
          - name: SUPABASE_SERVICE_KEY
            value: "$SERVICE_ROLE_KEY"
        resources:
          cpu: 0.5
          memory: 1Gi
        volumeMounts:
          - volumeName: kong-volume
            mountPath: /home/kong
    scale:
      minReplicas: 1
      maxReplicas: 3
    volumes:
      - name: kong-volume
        storageType: AzureFile
        storageName: kong-volume
"@

$KONG_YAML_PATH = "kong_app.yaml"
$KONG_YAML | Set-Content $KONG_YAML_PATH -Encoding UTF8

& az containerapp create `
    --name ca-kong `
    --resource-group $RG_NAME `
    --environment $ACA_ENV `
    --yaml $KONG_YAML_PATH

Remove-Item $KONG_YAML_PATH

Write-Host "=============================================" -ForegroundColor Green
Write-Host " ¡DESPLIEGUE COMPLETADO!" -ForegroundColor Green
Write-Host "Obteniendo URL pública de Supabase..." -ForegroundColor Yellow
& az containerapp show --name ca-kong --resource-group $RG_NAME --query "properties.configuration.ingress.fqdn" -o tsv
