# create_azure_infra.ps1
# Script para aprovisionar la infraestructura completa de EIP en Azure for Students.
# Ejecutar desde PowerShell habiendo iniciado sesión con 'az login'.

$ErrorActionPreference = "Stop"

# === 1. CONFIGURACIÓN ===
$RG_NAME = "rg-evangelista-prod"
$LOCATION = "eastus"
$DB_SERVER_NAME = "pg-evangelista-" + (Get-Random -Minimum 1000 -Maximum 9999)
$DB_NAME = "postgres"
$DB_USER = "evangelista_admin"
# Generar contraseña segura para la DB
$DB_PASS = [Guid]::NewGuid().ToString() + "!"
$KV_NAME = "kv-evangelist-" + (Get-Random -Minimum 100 -Maximum 999)
$ACA_ENV_NAME = "cae-evangelista"

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " INICIANDO APROVISIONAMIENTO EN AZURE" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "Resource Group: $RG_NAME"
Write-Host "Location:       $LOCATION"
Write-Host "DB Server:      $DB_SERVER_NAME"
Write-Host "Key Vault:      $KV_NAME"
Write-Host "ACA Env:        $ACA_ENV_NAME"
Write-Host "=============================================" -ForegroundColor Cyan

# === 2. VERIFICAR SESIÓN AZURE ===
Write-Host "[*] Verificando cuenta de Azure..." -ForegroundColor Yellow
$account = & az account show --query "{user:user.name, subscription:name, subscriptionId:id}" -o json | ConvertFrom-Json
Write-Host "Autenticado como: $($account.user)" -ForegroundColor Green
Write-Host "Suscripción:      $($account.subscription) ($($account.subscriptionId))" -ForegroundColor Green

# === 3. CREAR RESOURCE GROUP ===
Write-Host "[*] Creando Resource Group..." -ForegroundColor Yellow
& az group create --name $RG_NAME --location $LOCATION -o table

# === 4. CREAR AZURE POSTGRES FLEXIBLE SERVER ===
Write-Host "[*] Creando Azure Database for PostgreSQL (Flexible Server)..." -ForegroundColor Yellow
Write-Host "Nota: Esto puede tardar de 5 a 10 minutos (Plan Free Standard_B1ms, 32GB)..." -ForegroundColor DarkYellow

# Crear el servidor en la capa gratuita
& az postgres flexible-server create `
  --resource-group $RG_NAME `
  --name $DB_SERVER_NAME `
  --location $LOCATION `
  --admin-user $DB_USER `
  --admin-password $DB_PASS `
  --sku-name Standard_B1ms `
  --tier Burstable `
  --storage-size 32 `
  --database-name $DB_NAME `
  --yes `
  -o json

# Habilitar extensiones de PostgreSQL requeridas para RAG y Supabase (incluido pg_sodium y pgvector)
Write-Host "[*] Habilitando extensiones de base de datos..." -ForegroundColor Yellow
& az postgres flexible-server parameter set `
  --resource-group $RG_NAME `
  --server-name $DB_SERVER_NAME `
  --name azure.extensions `
  --value "pgsodium,pg_trgm,pgcrypto,uuid-ossp,vector" `
  -o table

# Permitir que otros servicios de Azure (como Container Apps) accedan a la BD
Write-Host "[*] Configurando reglas de Firewall de la DB para servicios de Azure..." -ForegroundColor Yellow
& az postgres flexible-server firewall-rule create `
  --resource-group $RG_NAME `
  --name $DB_SERVER_NAME `
  --rule-name AllowAllAzureServices `
  --start-ip-address 0.0.0.0 `
  --end-ip-address 0.0.0.0 `
  -o table

# === 5. CREAR AZURE KEY VAULT ===
Write-Host "[*] Creando Azure Key Vault..." -ForegroundColor Yellow
& az keyvault create `
  --name $KV_NAME `
  --resource-group $RG_NAME `
  --location $LOCATION `
  --sku standard `
  -o table

# Guardar las credenciales de la DB en el Key Vault
Write-Host "[*] Guardando credenciales de la BD en Key Vault..." -ForegroundColor Yellow
$connectionString = "postgresql://$($DB_USER):$($DB_PASS)@$($DB_SERVER_NAME).postgres.database.azure.com:5432/$($DB_NAME)?sslmode=require"
& az keyvault secret set --vault-name $KV_NAME --name "DATABASE-URL" --value $connectionString -o table
& az keyvault secret set --vault-name $KV_NAME --name "DB-PASSWORD" --value $DB_PASS -o table

# === 6. CREAR ENVIRONMENT DE CONTAINER APPS ===
Write-Host "[*] Creando Azure Container Apps Environment..." -ForegroundColor Yellow
& az containerapp env create `
  --name $ACA_ENV_NAME `
  --resource-group $RG_NAME `
  --location $LOCATION `
  -o table

Write-Host "=============================================" -ForegroundColor Green
Write-Host " ¡INFRAESTRUCTURA INICIAL CREADA CON ÉXITO!" -ForegroundColor Green
Write-Host "Guarda estos datos temporalmente:" -ForegroundColor Yellow
Write-Host "DB Server Name:  $DB_SERVER_NAME.postgres.database.azure.com"
Write-Host "DB Admin User:   $DB_USER"
Write-Host "DB Admin Pass:   $DB_PASS"
Write-Host "Key Vault Name:  $KV_NAME"
Write-Host "Connection URL:  $connectionString"
Write-Host "=============================================" -ForegroundColor Green
