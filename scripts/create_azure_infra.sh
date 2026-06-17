#!/bin/bash
# create_azure_infra.sh
# Script para aprovisionar base de datos PostgreSQL, Key Vault y Storage Account en Azure.
set -e

# Configuración
az() {
  AZURE_CONFIG_DIR="/Volumes/Adriel-SSD/Evangelista & Co/Evangelista Intelligence Platform/.azure" "/Volumes/Adriel-SSD/Evangelista & Co/Evangelista Intelligence Platform/Backend/.venv/bin/python" "/Volumes/Adriel-SSD/Evangelista & Co/Evangelista Intelligence Platform/Backend/.venv/bin/az" "$@"
}

RG_NAME="rg-evangelista-platform"
LOCATION="westus3"
# Usamos el ID fijo de los recursos creados en la primera corrida para mantener consistencia
RANDOM_ID="7990"
DB_SERVER_NAME="pg-evangelista-${RANDOM_ID}"
DB_NAME="db_evangelista"
DB_USER="evangelista_admin"
DB_PASS="Evangelista.Pass${RANDOM_ID}*"
KV_NAME="kv-evangelista-${RANDOM_ID}"
STORAGE_ACCOUNT_NAME="stevangelista${RANDOM_ID}"
SHARE_NAME="models"

echo "========================================="
echo "INICIANDO PROVISIONAMIENTO EN AZURE"
echo "========================================="
echo "Resource Group: $RG_NAME"
echo "Location:       $LOCATION"
echo "Storage Account:$STORAGE_ACCOUNT_NAME"
echo "Key Vault:      $KV_NAME"
echo "PostgreSQL:     $DB_SERVER_NAME"
echo "========================================="

# 1. Crear Storage Account (Standard LRS)
if az storage account show --name "$STORAGE_ACCOUNT_NAME" --resource-group "$RG_NAME" &>/dev/null; then
  echo "[*] Storage Account '$STORAGE_ACCOUNT_NAME' ya existe, omitiendo creación."
else
  echo "[*] Creando Storage Account..."
  az storage account create \
    --name "$STORAGE_ACCOUNT_NAME" \
    --resource-group "$RG_NAME" \
    --location "$LOCATION" \
    --sku Standard_LRS \
    -o table
fi

# 2. Obtener Connection String y crear File Share SMB
CONN_STRING=$(az storage account show-connection-string --name "$STORAGE_ACCOUNT_NAME" --resource-group "$RG_NAME" --query connectionString -o tsv)
if az storage share show --name "$SHARE_NAME" --connection-string "$CONN_STRING" &>/dev/null; then
  echo "[*] File Share '$SHARE_NAME' ya existe, omitiendo creación."
else
  echo "[*] Creando File Share SMB..."
  az storage share create \
    --name "$SHARE_NAME" \
    --connection-string "$CONN_STRING" \
    -o table
fi

# 3. Crear Azure Key Vault
if az keyvault show --name "$KV_NAME" --resource-group "$RG_NAME" &>/dev/null; then
  echo "[*] Key Vault '$KV_NAME' ya existe, omitiendo creación."
else
  echo "[*] Creando Key Vault..."
  az keyvault create \
    --name "$KV_NAME" \
    --resource-group "$RG_NAME" \
    --location "$LOCATION" \
    --sku standard \
    -o table
fi

# 4. Crear Azure Database for PostgreSQL (Flexible Server)
if az postgres flexible-server show --resource-group "$RG_NAME" --name "$DB_SERVER_NAME" &>/dev/null; then
  echo "[*] PostgreSQL Server '$DB_SERVER_NAME' ya existe, omitiendo creación."
else
  echo "[*] Creando Azure Database for PostgreSQL (Flexible Server)..."
  echo "Nota: Esto tomará de 3 a 5 minutos..."
  # Omitimos el argumento --database-name porque no aplica a servidores flexibles individuales
  az postgres flexible-server create \
    --resource-group "$RG_NAME" \
    --name "$DB_SERVER_NAME" \
    --location "$LOCATION" \
    --admin-user "$DB_USER" \
    --admin-password "$DB_PASS" \
    --sku-name Standard_B1ms \
    --tier Burstable \
    --storage-size 32 \
    --yes \
    -o table
fi

# Crear la base de datos dentro del servidor
echo "[*] Creando base de datos '$DB_NAME'..."
# Si ya existe no pasa nada, pero la creamos de forma segura
if ! az postgres flexible-server db list --resource-group "$RG_NAME" --server-name "$DB_SERVER_NAME" --query "[?name=='$DB_NAME']" -o tsv | grep -q "$DB_NAME"; then
  az postgres flexible-server db create \
    --resource-group "$RG_NAME" \
    --server-name "$DB_SERVER_NAME" \
    --database-name "$DB_NAME" \
    -o table
else
  echo "[*] La base de datos '$DB_NAME' ya existe."
fi

# 5. Habilitar extensiones requeridas para RAG (vector, pgcrypto, uuid-ossp)
echo "[*] Habilitando extensiones de base de datos..."
az postgres flexible-server parameter set \
  --resource-group "$RG_NAME" \
  --server-name "$DB_SERVER_NAME" \
  --name azure.extensions \
  --value "pg_trgm,pgcrypto,uuid-ossp,vector" \
  -o table

# 6. Permitir acceso de servicios de Azure
echo "[*] Configurando firewall para servicios de Azure..."
az postgres flexible-server firewall-rule create \
  --resource-group "$RG_NAME" \
  --name "$DB_SERVER_NAME" \
  --rule-name AllowAllAzureServices \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0 \
  -o table

# 7. Permitir acceso de la IP pública actual del Mac (necesario para correr migraciones locales)
echo "[*] Obteniendo IP pública local..."
MY_IP=$(curl -s https://api.ipify.org || echo "")
if [ -n "$MY_IP" ]; then
  echo "[*] Agregando IP local $MY_IP al firewall..."
  az postgres flexible-server firewall-rule create \
    --resource-group "$RG_NAME" \
    --name "$DB_SERVER_NAME" \
    --rule-name AllowLocalMac \
    --start-ip-address "$MY_IP" \
    --end-ip-address "$MY_IP" \
    -o table
else
  echo "[!] No se pudo determinar la IP pública. Deberás agregarla manualmente en el portal."
fi

# 8. Guardar cadenas de conexión y secretos en Key Vault
echo "[*] Guardando secretos en Key Vault..."
DB_CONN_STR="postgresql://${DB_USER}:${DB_PASS}@${DB_SERVER_NAME}.postgres.database.azure.com:5432/${DB_NAME}?sslmode=require"
DB_ASYNC_CONN_STR="postgresql+asyncpg://${DB_USER}:${DB_PASS}@${DB_SERVER_NAME}.postgres.database.azure.com:5432/${DB_NAME}?sslmode=require"

# Guardar secretos de conexión
az keyvault secret set --vault-name "$KV_NAME" --name "pg-connection-string" --value "$DB_CONN_STR" -o table
az keyvault secret set --vault-name "$KV_NAME" --name "pg-async-connection-string" --value "$DB_ASYNC_CONN_STR" -o table
az keyvault secret set --vault-name "$KV_NAME" --name "groq-api-key" --value "PLACEHOLDER_KEY" -o table

echo "========================================="
echo "PROVISIONAMIENTO FINALIZADO CON ÉXITO!"
echo "========================================="
echo "PostgreSQL:     ${DB_SERVER_NAME}.postgres.database.azure.com"
echo "Key Vault URL:  https://${KV_NAME}.vault.azure.net/"
echo "Storage Conn:   $CONN_STRING"
echo "DATABASE_URL:   $DB_CONN_STR"
echo "========================================="

# Guardar información en un archivo local temporal (no commiteado)
echo "STORAGE_CONN_STRING=\"$CONN_STRING\"" > ../.azure_env
echo "DATABASE_URL=\"$DB_CONN_STR\"" >> ../.azure_env
echo "ASYNC_DATABASE_URL=\"$DB_ASYNC_CONN_STR\"" >> ../.azure_env
echo "AZURE_KEY_VAULT_URL=\"https://${KV_NAME}.vault.azure.net/\"" >> ../.azure_env
echo "AZURE_POSTGRES_HOST=\"${DB_SERVER_NAME}.postgres.database.azure.com\"" >> ../.azure_env
