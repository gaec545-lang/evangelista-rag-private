-- ============================================================
-- WAR ROOM SCHEMA — Evangelista Intelligence Platform
-- Ejecutar en Supabase Dashboard > SQL Editor
-- ============================================================

-- === EQUIPO Y ROLES ===
CREATE TABLE IF NOT EXISTS team_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('ceo', 'cto', 'cfo_cqa', 'consultant', 'viewer')),
    email TEXT NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT true,
    -- Permisos base (se sobrescriben programáticamente por rol)
    permissions JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- === ERP CONNECTIONS ===
-- (Debe existir antes de architecture_projects y sentinel_subscriptions)
CREATE TABLE IF NOT EXISTS erp_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    erp_type TEXT NOT NULL,
    host TEXT NOT NULL,
    database_name TEXT,
    is_read_only BOOLEAN DEFAULT true,
    -- Las credenciales se cifran con pgsodium antes de insertar
    -- En producción: username_encrypted / password_encrypted via pgsodium.crypto_aead_det_encrypt
    _credentials JSONB,
    status TEXT NOT NULL DEFAULT 'inactive' CHECK (status IN ('active', 'inactive', 'error')),
    last_test TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE erp_connections ENABLE ROW LEVEL SECURITY;
CREATE POLICY "erp_all" ON erp_connections FOR ALL USING (auth.role() = 'authenticated');

-- === FOUNDATION ENGAGEMENTS ===
CREATE TABLE IF NOT EXISTS foundation_engagements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,

    -- Pipeline de citas
    status TEXT NOT NULL DEFAULT 'scoping' CHECK (status IN (
        'scoping',
        'cita_1_scheduled',
        'cita_1_done',
        'immersion',
        'cita_2_done',
        'dictamen_review',
        'cita_3_scheduled',
        'cita_3_done',
        'vetting_gate',
        'cita_4_scheduled',
        'cita_4_done',
        'closed_go',
        'closed_nogo',
        'closed_lost'
    )),

    -- Factores calculados
    factor_alpha DECIMAL(4,2),
    factor_beta DECIMAL(4,2),
    factor_gamma DECIMAL(4,2),
    foundation_fee DECIMAL(12,2),

    -- Scoping data
    nodo_critico TEXT,
    registros_estimados INTEGER,
    fuentes_datos INTEGER DEFAULT 1,
    requiere_viaticos BOOLEAN DEFAULT false,

    -- Vetting Gate
    vetting_beta_ok BOOLEAN,
    vetting_alpha_ok BOOLEAN,
    vetting_gamma_viable BOOLEAN,
    vetting_sponsor_ok BOOLEAN,
    vetting_decision TEXT CHECK (vetting_decision IN ('go', 'no_go', 'pending')),
    vetting_decided_by UUID REFERENCES team_members(id),
    vetting_decided_at TIMESTAMPTZ,

    -- Dictamen
    hallazgos JSONB DEFAULT '[]'::jsonb,
    dictamen_total_impacto DECIMAL(12,2),
    dictamen_aprobado_por UUID REFERENCES team_members(id),
    dictamen_aprobado_at TIMESTAMPTZ,

    -- Fechas de citas
    cita_1_date TIMESTAMPTZ,
    cita_2_date TIMESTAMPTZ,
    cita_3_date TIMESTAMPTZ,
    cita_4_date TIMESTAMPTZ,

    -- Notas internas
    notas_internas TEXT,
    assigned_to UUID REFERENCES team_members(id),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- === ARCHITECTURE PROJECTS ===
CREATE TABLE IF NOT EXISTS architecture_projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    foundation_id UUID REFERENCES foundation_engagements(id),

    status TEXT NOT NULL DEFAULT 'setup' CHECK (status IN (
        'setup',
        'fase_1',
        'fase_2',
        'fase_3',
        'delivery',
        'completed',
        'on_hold'
    )),

    -- Financieros
    setup_fee DECIMAL(12,2),
    tramo_a DECIMAL(12,2),
    tramo_b DECIMAL(12,2),
    success_fee_estimado DECIMAL(12,2),
    tramo_a_pagado BOOLEAN DEFAULT false,
    tramo_b_pagado BOOLEAN DEFAULT false,

    -- Infraestructura
    escenario_infra TEXT CHECK (escenario_infra IN ('A', 'B')),
    erp_connection_id UUID REFERENCES erp_connections(id),

    -- Sprints
    sprints JSONB DEFAULT '[]'::jsonb,

    assigned_to UUID REFERENCES team_members(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- === SENTINEL SUBSCRIPTIONS ===
CREATE TABLE IF NOT EXISTS sentinel_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    architecture_id UUID REFERENCES architecture_projects(id),

    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'cancelled')),
    tier TEXT NOT NULL DEFAULT 'gold' CHECK (tier IN ('silver', 'gold', 'platinum')),
    monthly_fee DECIMAL(12,2) DEFAULT 45000,

    -- KPIs monitoreados
    kpis JSONB DEFAULT '[]'::jsonb,

    -- Juntas de consejo
    proxima_junta DATE,
    juntas_realizadas INTEGER DEFAULT 0,

    -- Alertas
    alertas_activas INTEGER DEFAULT 0,

    erp_connection_id UUID REFERENCES erp_connections(id),
    assigned_to UUID REFERENCES team_members(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- === ACTIVITY LOG ===
CREATE TABLE IF NOT EXISTS activity_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_member_id UUID REFERENCES team_members(id),
    client_id UUID REFERENCES clients(id),
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id UUID,
    details JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- === ÍNDICES ===
CREATE INDEX IF NOT EXISTS idx_foundation_client ON foundation_engagements(client_id);
CREATE INDEX IF NOT EXISTS idx_foundation_status ON foundation_engagements(status);
CREATE INDEX IF NOT EXISTS idx_foundation_assigned ON foundation_engagements(assigned_to);
CREATE INDEX IF NOT EXISTS idx_arch_client ON architecture_projects(client_id);
CREATE INDEX IF NOT EXISTS idx_arch_status ON architecture_projects(status);
CREATE INDEX IF NOT EXISTS idx_sentinel_client ON sentinel_subscriptions(client_id);
CREATE INDEX IF NOT EXISTS idx_sentinel_status ON sentinel_subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_activity_client ON activity_log(client_id);
CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_team_role ON team_members(role);

-- === RLS ===
ALTER TABLE team_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE foundation_engagements ENABLE ROW LEVEL SECURITY;
ALTER TABLE architecture_projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE sentinel_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE activity_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "team_all" ON team_members FOR ALL USING (auth.role() = 'authenticated');
CREATE POLICY "foundation_all" ON foundation_engagements FOR ALL USING (auth.role() = 'authenticated');
CREATE POLICY "architecture_all" ON architecture_projects FOR ALL USING (auth.role() = 'authenticated');
CREATE POLICY "sentinel_all" ON sentinel_subscriptions FOR ALL USING (auth.role() = 'authenticated');
CREATE POLICY "activity_all" ON activity_log FOR ALL USING (auth.role() = 'authenticated');

-- === TRIGGERS ===
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER foundation_updated_at BEFORE UPDATE ON foundation_engagements
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER architecture_updated_at BEFORE UPDATE ON architecture_projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER sentinel_updated_at BEFORE UPDATE ON sentinel_subscriptions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
