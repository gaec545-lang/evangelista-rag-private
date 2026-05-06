-- Migración 002 — Evangelista Intelligence Platform Redesign
-- Fecha: Abril 2026

-- 1. Tabla projects
CREATE TABLE projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  area TEXT NOT NULL CHECK (area IN (
    'supply_chain', 'finanzas', 'operaciones',
    'ventas', 'logistica', 'rrhh', 'tecnologia', 'multi'
  )),
  description TEXT,
  status TEXT NOT NULL DEFAULT 'scoping' CHECK (status IN (
    'scoping', 'propuesta_enviada', 'en_ejecucion',
    'entrega', 'completado', 'pausado', 'cancelado'
  )),
  current_phase TEXT NOT NULL DEFAULT 'scoping',
  complexity_alpha NUMERIC(4,2) DEFAULT 0,   -- Factor αAlcance (0.0 – 0.30)
  complexity_beta NUMERIC(4,2) DEFAULT 0,    -- Factor βComplejidad (0.0 – 0.50)
  gamma_sources NUMERIC(4,2) DEFAULT 1.0,    -- ΓFuentes (≥ 1.0)
  base_price NUMERIC(12,2),                  -- BaseÁrea calculada
  total_price NUMERIC(12,2),                 -- Precio final sin IVA
  travel_expenses NUMERIC(12,2) DEFAULT 0,   -- Viáticos si aplica
  created_by UUID REFERENCES auth.users(id),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Trigger para updated_at automático
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER projects_updated_at
  BEFORE UPDATE ON projects
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- RLS para projects
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
CREATE POLICY "team_access" ON projects
  FOR ALL USING (auth.uid() IN (
    SELECT user_id FROM team_members WHERE active = true
  ));

-- 2. Tabla project_phases
CREATE TABLE project_phases (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  phase_name TEXT NOT NULL,
  phase_order INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'pendiente' CHECK (status IN (
    'pendiente', 'en_curso', 'completada', 'bloqueada'
  )),
  responsible TEXT,
  notes TEXT,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE project_phases ENABLE ROW LEVEL SECURITY;
CREATE POLICY "team_access" ON project_phases
  FOR ALL USING (auth.uid() IN (
    SELECT user_id FROM team_members WHERE active = true
  ));

-- 3. Tabla data_sources (Credential Vault)
CREATE TABLE data_sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
  client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  source_type TEXT NOT NULL CHECK (source_type IN (
    'sql_server', 'mysql', 'postgresql', 'oracle',
    'contpaqi', 'aspel', 'sap_b1',
    'excel', 'csv', 'api_rest', 'otro'
  )),
  connection_config JSONB NOT NULL DEFAULT '{}',
  access_mode TEXT NOT NULL DEFAULT 'read_only' CHECK (access_mode IN ('read_only', 'read_write')),
  status TEXT NOT NULL DEFAULT 'pendiente' CHECK (status IN (
    'pendiente', 'conectado', 'error', 'sin_probar'
  )),
  last_tested_at TIMESTAMPTZ,
  last_test_result TEXT,
  authorized_tables TEXT[],
  notes TEXT,
  created_by UUID REFERENCES auth.users(id),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TRIGGER data_sources_updated_at
  BEFORE UPDATE ON data_sources
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

ALTER TABLE data_sources ENABLE ROW LEVEL SECURITY;
CREATE POLICY "team_access" ON data_sources
  FOR ALL USING (auth.uid() IN (
    SELECT user_id FROM team_members WHERE active = true
  ));

-- 4. Tabla hypotheses
CREATE TABLE hypotheses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  statement TEXT NOT NULL,
  framework_used TEXT,
  area TEXT,
  hypothesis_type TEXT CHECK (hypothesis_type IN (
    'problema', 'causa_raiz', 'oportunidad', 'riesgo'
  )),
  status TEXT NOT NULL DEFAULT 'planteada' CHECK (status IN (
    'planteada', 'en_validacion', 'validada', 'refutada', 'derivada'
  )),
  evidence TEXT,
  economic_impact NUMERIC(12,2),
  parent_hypothesis_id UUID REFERENCES hypotheses(id),
  priority INTEGER DEFAULT 0,
  created_by UUID REFERENCES auth.users(id),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TRIGGER hypotheses_updated_at
  BEFORE UPDATE ON hypotheses
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

ALTER TABLE hypotheses ENABLE ROW LEVEL SECURITY;
CREATE POLICY "team_access" ON hypotheses
  FOR ALL USING (auth.uid() IN (
    SELECT user_id FROM team_members WHERE active = true
  ));

-- 5. Tabla interview_notes
CREATE TABLE interview_notes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  session_title TEXT NOT NULL,
  content TEXT NOT NULL,
  interviewer TEXT NOT NULL,
  interviewee TEXT,
  interview_type TEXT CHECK (interview_type IN (
    'scoping', 'inmersion', 'validacion', 'seguimiento', 'cierre', 'otro'
  )),
  captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  location TEXT,
  alcoa_hash TEXT,
  created_by UUID REFERENCES auth.users(id),
  created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE interview_notes ENABLE ROW LEVEL SECURITY;
CREATE POLICY "team_access" ON interview_notes
  FOR ALL USING (auth.uid() IN (
    SELECT user_id FROM team_members WHERE active = true
  ));

-- 6. Tabla findings
CREATE TABLE findings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  data_source_id UUID REFERENCES data_sources(id),
  folio TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  technical_description TEXT,
  severity TEXT NOT NULL CHECK (severity IN (
    'critico', 'alto', 'medio', 'bajo', 'oportunidad'
  )),
  area TEXT,
  economic_impact NUMERIC(12,2),
  economic_impact_basis TEXT,
  recommended_action TEXT,
  evidence JSONB DEFAULT '[]',
  hash_md5 TEXT,
  captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  git_commit TEXT,
  status TEXT NOT NULL DEFAULT 'identificado' CHECK (status IN (
    'identificado', 'validado', 'presentado', 'cerrado'
  )),
  created_by UUID REFERENCES auth.users(id),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TRIGGER findings_updated_at
  BEFORE UPDATE ON findings
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

ALTER TABLE findings ENABLE ROW LEVEL SECURITY;
CREATE POLICY "team_access" ON findings
  FOR ALL USING (auth.uid() IN (
    SELECT user_id FROM team_members WHERE active = true
  ));

-- 7. Tabla deliverables
CREATE TABLE deliverables (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  deliverable_type TEXT NOT NULL CHECK (deliverable_type IN (
    'propuesta', 'cronograma', 'dictamen_forense',
    'certificado_alcoa', 'reporte_analisis',
    'tablero_powerbi', 'otro'
  )),
  title TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'borrador' CHECK (status IN (
    'borrador', 'revision_interna', 'aprobado', 'entregado_cliente'
  )),
  file_url TEXT,
  file_name TEXT,
  version INTEGER DEFAULT 1,
  notes TEXT,
  generated_at TIMESTAMPTZ,
  delivered_at TIMESTAMPTZ,
  created_by UUID REFERENCES auth.users(id),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TRIGGER deliverables_updated_at
  BEFORE UPDATE ON deliverables
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

ALTER TABLE deliverables ENABLE ROW LEVEL SECURITY;
CREATE POLICY "team_access" ON deliverables
  FOR ALL USING (auth.uid() IN (
    SELECT user_id FROM team_members WHERE active = true
  ));

-- 8. Tabla project_activity_log
CREATE TABLE project_activity_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  action_type TEXT NOT NULL,
  entity_type TEXT,
  entity_id UUID,
  description TEXT NOT NULL,
  metadata JSONB DEFAULT '{}',
  performed_by UUID REFERENCES auth.users(id),
  performed_by_name TEXT,
  performed_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE project_activity_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "team_read" ON project_activity_log
  FOR SELECT USING (auth.uid() IN (
    SELECT user_id FROM team_members WHERE active = true
  ));
CREATE POLICY "team_insert" ON project_activity_log
  FOR INSERT WITH CHECK (auth.uid() IN (
    SELECT user_id FROM team_members WHERE active = true
  ));
