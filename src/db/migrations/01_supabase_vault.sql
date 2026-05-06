-- Migración: Supabase Vault nativo para Data Abstraction
-- Extensión supabase_vault (pgsodium + vault schema)
--
-- Crea:
--   1. Tabla erp_connections (metadatos NO sensibles)
--   2. Secretos en vault.secrets (credenciales cifradas por pgsodium)
--   3. Función helper para crear conexiones completas
--
-- Aplicar en Supabase Dashboard > SQL Editor o via supabase-js migration.
-- Requiere: rol `service_role` para acceder a vault.decrypted_secrets.

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 1. EXTENSIÓN
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CREATE EXTENSION IF NOT EXISTS supabase_vault WITH SCHEMA vault CASCADE;

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 2. TABLA ERP_CONNECTIONS (metadatos, SIN contraseñas)
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CREATE TABLE IF NOT EXISTS erp_connections (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id       UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    connection_type VARCHAR(50) NOT NULL,  -- 'sap_hana', 'aspel', 'sql_server', 'postgresql', 'mysql'
    host            VARCHAR(255) NOT NULL,
    port            INTEGER NOT NULL DEFAULT 5432,
    database_name   VARCHAR(128),
    username        VARCHAR(128) NOT NULL,
    secret_id       UUID NOT NULL,          -- referencia a vault.secrets
    extra_config    JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE erp_connections IS
    'Metadatos de conexiones ERP. La contraseña vive exclusivamente en vault.secrets.';

-- Índice para lookup rápido por cliente
CREATE UNIQUE INDEX IF NOT EXISTS idx_erp_conn_client
    ON erp_connections (client_id);

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 3. FUNCIÓN HELPER: crear erp_connection + secreto en un solo paso
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
--
-- Uso desde el backend:
--   SELECT create_erp_connection(
--     p_client_id  := 'uuid-del-cliente',
--     p_type       := 'sap_hana',
--     p_host       := 'erp.cliente.com',
--     p_port       := 39015,
--     p_database   := 'HANA_DB',
--     p_username   := 'evangelista_ro',
--     p_password   := 'la-contraseña-en-plaintext'   -- ← se cifra internamente
--   );
--
-- Esta función:
--   1. Guarda la contraseña en vault.secrets (pgsodium cifrado)
--   2. Inserta el erp_connection con el secret_id referenciado
--   3. Retorna el ID del connection creado

CREATE OR REPLACE FUNCTION create_erp_connection(
    _client_id  UUID,
    _type        VARCHAR,
    _host        VARCHAR,
    _port        INTEGER  DEFAULT 5432,
    _database    VARCHAR  DEFAULT NULL,
    _username    VARCHAR,
    _password    TEXT      -- ← plaintext, se cifra internamente
) RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER   -- ejecuta con permisos del schema supabase_admin
SET search_path = public, vault
AS $$
DECLARE
    v_secret_id UUID;
    v_conn_id   UUID;
BEGIN
    -- 1. Guardar la contraseña en vault.secrets (cifrado automático via pgsodium)
    v_secret_id := vault.store_secret(
        key_name        := 'erp_secret_' || gen_random_uuid()::text,
        secret          := _password,
        description     := 'ERP password for client ' || _client_id::text,
        expires_at      := NULL               -- no expira
    )::UUID;

    -- 2. Insertar la conexión con referencia al secreto
    INSERT INTO erp_connections (
        client_id, connection_type, host, port, database_name,
        username, secret_id
    ) VALUES (
        _client_id, _type, _host, _port, _database,
        _username, v_secret_id
    ) RETURNING id INTO v_conn_id;

    RETURN v_conn_id;
END;
$$ SET search_path = public, vault;

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 4. FUNCIÓN HELPER: eliminar erp_connection + secret
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CREATE OR REPLACE FUNCTION revoke_erp_connection(_client_id UUID)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, vault
AS $$
DECLARE
    v_secret_id UUID;
BEGIN
    -- Obtener el secret_id antes de borrar
    SELECT secret_id INTO v_secret_id
    FROM erp_connections
    WHERE client_id = _client_id;

    -- Borrar la conexión
    DELETE FROM erp_connections WHERE client_id = _client_id;

    -- Borrar el secreto asociado
    IF v_secret_id IS NOT NULL THEN
        DELETE FROM vault.decrypted_secrets WHERE id = v_secret_id;
    END IF;
END;
$$ SET search_path = public, vault;
