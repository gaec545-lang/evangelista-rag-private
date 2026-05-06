-- ============================================================
-- Evangelista Intelligence Platform — Schema inicial
-- ============================================================

-- Clientes de Evangelista
CREATE TABLE clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    sector TEXT NOT NULL,
    contact_name TEXT,
    contact_email TEXT,
    contact_phone TEXT,
    city TEXT DEFAULT 'Puebla',
    sucursales INTEGER DEFAULT 1,
    sistemas_erp INTEGER DEFAULT 1,
    erp_type TEXT,
    factor_gamma DECIMAL(4,2),
    factor_alpha DECIMAL(4,2),
    factor_beta DECIMAL(4,2),
    vetting_status TEXT DEFAULT 'pending' CHECK (vetting_status IN ('pending','go','no_go')),
    status TEXT DEFAULT 'prospect' CHECK (status IN ('prospect','active','completed','archived')),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Análisis ejecutados
CREATE TABLE analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID REFERENCES clients(id) ON DELETE SET NULL,
    task TEXT NOT NULL,
    execution_plan TEXT,
    final_response TEXT,
    confidence DECIMAL(3,2),
    subtasks JSONB,
    sources_used TEXT[],
    errors TEXT[],
    execution_time_ms INTEGER,
    status TEXT DEFAULT 'completed' CHECK (status IN ('running','completed','failed')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Propuestas generadas
CREATE TABLE proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID REFERENCES clients(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('foundation','architecture')),
    content TEXT NOT NULL,
    pricing JSONB,
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft','sent','accepted','rejected')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Row Level Security
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE proposals ENABLE ROW LEVEL SECURITY;

-- Políticas: solo usuarios autenticados (equipo interno)
CREATE POLICY "equipo_interno_clients" ON clients FOR ALL USING (auth.role() = 'authenticated');
CREATE POLICY "equipo_interno_analyses" ON analyses FOR ALL USING (auth.role() = 'authenticated');
CREATE POLICY "equipo_interno_proposals" ON proposals FOR ALL USING (auth.role() = 'authenticated');

-- Índices
CREATE INDEX idx_clients_sector ON clients(sector);
CREATE INDEX idx_clients_status ON clients(status);
CREATE INDEX idx_analyses_client ON analyses(client_id);
CREATE INDEX idx_analyses_created ON analyses(created_at DESC);
CREATE INDEX idx_proposals_client ON proposals(client_id);

-- Trigger updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER clients_updated_at BEFORE UPDATE ON clients FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER proposals_updated_at BEFORE UPDATE ON proposals FOR EACH ROW EXECUTE FUNCTION update_updated_at();
