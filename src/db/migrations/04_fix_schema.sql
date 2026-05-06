-- =========================================================================
-- 04_fix_schema.sql — Consolidar esquema completo
--
-- Problemas que resuelve:
--   1. erp_connections definido dos veces con esquemas distintos (01 vs 02)
--   2. database_connector.py usa connection_type/port/username/secret_id
--      pero erp_connections.py (02) usa erp_type/host/database_name/_credentials
--   3. Data Upload Wizard necesita tabla data_ingestions (03) — incluida aqui
--   4. Faltan triggers updated_at para clients y proposals
--   5. Faltan columnas scoping: sucursales, erps, fuentes_extra
--
-- Este script es IDEMPOTENTE (usa IF NOT EXISTS, ADD COLUMN IF NOT EXISTS).
-- Ejecutar en Supabase Dashboard > SQL Editor.
-- =========================================================================

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 0. EXTENSION — Vault (credenciales cifradas)
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CREATE EXTENSION IF NOT EXISTS supabase_vault WITH SCHEMA vault CASCADE;

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 1. ERP_CONNECTIONS — agregar columnas faltantes a la tabla existente
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- El objetivo: unificar ambos esquemas en una sola tabla con TODAS las columnas.
-- Si la tabla no existe, se creará al final del script.

DO $$
BEGIN
    -- Solo ALTER si la tabla ya existe
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'erp_connections'
    ) THEN
        -- Columnas del vault schema (01_supabase_vault.sql)
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'erp_connections' AND column_name = 'connection_type'
        ) THEN
            ALTER TABLE erp_connections ADD COLUMN connection_type VARCHAR(50);
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'erp_connections' AND column_name = 'port'
        ) THEN
            ALTER TABLE erp_connections ADD COLUMN port INTEGER DEFAULT 5432;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'erp_connections' AND column_name = 'username'
        ) THEN
            ALTER TABLE erp_connections ADD COLUMN username VARCHAR(128) DEFAULT '';
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'erp_connections' AND column_name = 'secret_id'
        ) THEN
            ALTER TABLE erp_connections ADD COLUMN secret_id UUID;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'erp_connections' AND column_name = 'extra_config'
        ) THEN
            ALTER TABLE erp_connections ADD COLUMN extra_config JSONB DEFAULT '{}';
        END IF;

        -- Columnas del frontend schema (02_war_room.sql)
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'erp_connections' AND column_name = 'erp_type'
        ) THEN
            ALTER TABLE erp_connections ADD COLUMN erp_type TEXT;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'erp_connections' AND column_name = 'database_name'
        ) THEN
            ALTER TABLE erp_connections ADD COLUMN database_name TEXT;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'erp_connections' AND column_name = 'host'
        ) THEN
            ALTER TABLE erp_connections ADD COLUMN host TEXT;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'erp_connections' AND column_name = 'is_read_only'
        ) THEN
            ALTER TABLE erp_connections ADD COLUMN is_read_only BOOLEAN DEFAULT true;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'erp_connections' AND column_name = '_credentials'
        ) THEN
            ALTER TABLE erp_connections ADD COLUMN _credentials JSONB;
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'erp_connections' AND column_name = 'status'
        ) THEN
            ALTER TABLE erp_connections ADD COLUMN status TEXT DEFAULT 'inactive';
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'erp_connections' AND column_name = 'last_test'
        ) THEN
            ALTER TABLE erp_connections ADD COLUMN last_test TIMESTAMPTZ;
        END IF;

        -- Asegurar NOT NULL en connection_type si ya existe
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'erp_connections' AND column_name = 'connection_type'
              AND is_nullable = 'YES'
        ) THEN
            UPDATE erp_connections SET connection_type = COALESCE(erp_type, 'generic')
            WHERE connection_type IS NULL;
            -- No podemos hacer NOT NULL si hay rows con NULL, primero llenamos
            ALTER TABLE erp_connections ALTER COLUMN connection_type SET NOT NULL;
        END IF;

        -- Asegurar NOT NULL en connection_type si se agregó
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'erp_connections' AND column_name = 'connection_type'
              AND is_nullable = 'YES'
        ) THEN
            -- Intentar hacer NOT NULL; si falla por NULLs, lo dejamos flexible
            BEGIN
                ALTER TABLE erp_connections ALTER COLUMN connection_type SET NOT NULL;
            EXCEPTION WHEN OTHERS THEN
                NULL; -- silently skip if there are still NULLs
            END;
        END IF;
    END IF;
END $$;

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 2. Si erp_connections aún no existe (ninguna migración la creó)
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CREATE TABLE IF NOT EXISTS erp_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    -- Vault schema (01)
    connection_type VARCHAR(50) NOT NULL,
    host VARCHAR(255) NOT NULL,
    port INTEGER NOT NULL DEFAULT 5432,
    database_name VARCHAR(128),
    username VARCHAR(128) NOT NULL,
    secret_id UUID NOT NULL,
    extra_config JSONB DEFAULT '{}',
    -- Frontend schema (02) — para compatibilidad
    erp_type TEXT,
    is_read_only BOOLEAN DEFAULT true,
    _credentials JSONB,
    status TEXT NOT NULL DEFAULT 'inactive',
    last_test TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Unique index por cliente
CREATE UNIQUE INDEX IF NOT EXISTS idx_erp_conn_client
    ON erp_connections (client_id);

-- RLS
ALTER TABLE erp_connections ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "erp_all" ON erp_connections;
CREATE POLICY "erp_all" ON erp_connections FOR ALL USING (auth.role() = 'authenticated');

-- Trigger updated_at
DROP TRIGGER IF EXISTS erp_updated_at ON erp_connections;
CREATE TRIGGER erp_updated_at BEFORE UPDATE ON erp_connections
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 3. FUNCIÓN: crear erp_connection + vault secret
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CREATE OR REPLACE FUNCTION create_erp_connection(
    _client_id  UUID,
    _type        VARCHAR,
    _host        VARCHAR,
    _username    VARCHAR,
    _password    TEXT,
    _port        INTEGER  DEFAULT 5432,
    _database    VARCHAR  DEFAULT NULL
) RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, vault
AS $$
DECLARE
    v_secret_id UUID;
    v_conn_id   UUID;
BEGIN
    v_secret_id := vault.store_secret(
        key_name    := 'erp_secret_' || gen_random_uuid()::text,
        secret      := _password,
        description := 'ERP password for client ' || _client_id::text,
        expires_at  := NULL
    )::UUID;

    INSERT INTO erp_connections (
        client_id, connection_type, host, port, database_name,
        username, secret_id, erp_type
    ) VALUES (
        _client_id, _type, _host, _port, _database,
        _username, v_secret_id, _type
    ) RETURNING id INTO v_conn_id;

    RETURN v_conn_id;
END;
$$ SET search_path = public, vault;

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 4. FUNCIÓN: revocar erp_connection + secret
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CREATE OR REPLACE FUNCTION revoke_erp_connection(_client_id UUID)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, vault
AS $$
DECLARE
    v_secret_id UUID;
BEGIN
    SELECT secret_id INTO v_secret_id
    FROM erp_connections
    WHERE client_id = _client_id;

    DELETE FROM erp_connections WHERE client_id = _client_id;

    IF v_secret_id IS NOT NULL THEN
        DELETE FROM vault.decrypted_secrets WHERE id = v_secret_id;
    END IF;
END;
$$ SET search_path = public, vault;

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 5. COLUMNAS SCOPING FALTANTES en foundation_engagements
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ALTER TABLE foundation_engagements ADD COLUMN IF NOT EXISTS sucursales INTEGER DEFAULT 1;
ALTER TABLE foundation_engagements ADD COLUMN IF NOT EXISTS erps INTEGER DEFAULT 1;
ALTER TABLE foundation_engagements ADD COLUMN IF NOT EXISTS fuentes_extra INTEGER DEFAULT 0;

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 6. DATA_INGESTIONS (auto-detect scoping)
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CREATE TABLE IF NOT EXISTS data_ingestions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    engagement_id UUID REFERENCES foundation_engagements(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL CHECK (source_type IN ('csv', 'excel', 'erp')),
    raw_filename TEXT,
    row_count INTEGER,
    column_count INTEGER,
    detected_params JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_data_ingestions_engagement_id
    ON data_ingestions(engagement_id);
CREATE INDEX IF NOT EXISTS idx_data_ingestions_source_type
    ON data_ingestions(source_type);

ALTER TABLE data_ingestions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "data_ingestions_all" ON data_ingestions;
CREATE POLICY "data_ingestions_all" ON data_ingestions FOR ALL USING (auth.role() = 'authenticated');

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 7. TRIGGERS updated_at para tablas que lo necesitan
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS clients_updated_at ON clients;
CREATE TRIGGER clients_updated_at BEFORE UPDATE ON clients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS proposals_updated_at ON proposals;
CREATE TRIGGER proposals_updated_at BEFORE UPDATE ON proposals
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 8. VERIFICACIÓN FINAL
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DO $$
DECLARE
    t TEXT;
BEGIN
    RAISE NOTICE '=== Tablas en schema public ===';
    FOR t IN
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY tablename
    LOOP
        RAISE NOTICE '  %', t;
    END LOOP;
END $$;
