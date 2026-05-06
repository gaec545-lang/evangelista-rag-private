-- 05_multi_equipo.sql
-- Migración para la Extensión Multi-Equipo (Spec 09)

-- Un workstream es un carril de trabajo paralelo dentro del proyecto
CREATE TABLE project_workstreams (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT,
  workstream_type TEXT NOT NULL CHECK (workstream_type IN (
    'consultoria', 'desarrollo', 'ingenieria', 'diseno', 'qa', 'externo_otro'
  )),
  team_type TEXT NOT NULL DEFAULT 'interno' CHECK (team_type IN (
    'interno', 'subcontratado', 'cliente'
  )),
  contractor_name TEXT,
  contractor_contact TEXT,
  contractor_rate NUMERIC(12,2),
  contractor_rate_type TEXT CHECK (contractor_rate_type IN (
    'hora', 'dia', 'sprint', 'fijo', 'por_entregable'
  )),
  color TEXT NOT NULL DEFAULT '#534ab7',
  display_order INTEGER DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'activo' CHECK (status IN (
    'activo', 'pausado', 'completado', 'cancelado'
  )),
  budget_allocated NUMERIC(12,2),
  budget_spent NUMERIC(12,2) DEFAULT 0,
  created_by UUID REFERENCES auth.users(id),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TRIGGER workstreams_updated_at
  BEFORE UPDATE ON project_workstreams
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

ALTER TABLE project_workstreams ENABLE ROW LEVEL SECURITY;
CREATE POLICY "team_access" ON project_workstreams
  FOR ALL USING (auth.uid() IN (
    SELECT user_id FROM team_members WHERE is_active = true
  ));

-- Tareas individuales dentro de un workstream
CREATE TABLE workstream_tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workstream_id UUID NOT NULL REFERENCES project_workstreams(id) ON DELETE CASCADE,
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT,
  task_type TEXT CHECK (task_type IN (
    'entregable', 'hito', 'reunion', 'revision', 'instalacion', 'tarea'
  )),
  status TEXT NOT NULL DEFAULT 'pendiente' CHECK (status IN (
    'pendiente', 'en_progreso', 'bloqueada', 'en_revision', 'completada', 'cancelada'
  )),
  priority TEXT NOT NULL DEFAULT 'media' CHECK (priority IN (
    'critica', 'alta', 'media', 'baja'
  )),
  responsible_name TEXT,
  responsible_type TEXT CHECK (responsible_type IN ('interno', 'externo')),
  planned_start DATE,
  planned_end DATE,
  actual_start DATE,
  actual_end DATE,
  depends_on UUID[],
  progress_pct INTEGER DEFAULT 0 CHECK (progress_pct BETWEEN 0 AND 100),
  estimated_cost NUMERIC(12,2),
  actual_cost NUMERIC(12,2),
  blocker_description TEXT,
  display_order INTEGER DEFAULT 0,
  created_by UUID REFERENCES auth.users(id),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TRIGGER tasks_updated_at
  BEFORE UPDATE ON workstream_tasks
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE INDEX idx_workstream_tasks_project ON workstream_tasks(project_id);
CREATE INDEX idx_workstream_tasks_workstream ON workstream_tasks(workstream_id);

ALTER TABLE workstream_tasks ENABLE ROW LEVEL SECURITY;
CREATE POLICY "team_access" ON workstream_tasks
  FOR ALL USING (auth.uid() IN (
    SELECT user_id FROM team_members WHERE is_active = true
  ));

-- Miembros asignados a cada workstream
CREATE TABLE workstream_members (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workstream_id UUID NOT NULL REFERENCES project_workstreams(id) ON DELETE CASCADE,
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  team_member_id UUID REFERENCES team_members(id),
  external_name TEXT,
  external_role TEXT,
  external_email TEXT,
  external_phone TEXT,
  external_company TEXT,
  member_type TEXT NOT NULL CHECK (member_type IN ('interno', 'externo')),
  role_in_project TEXT NOT NULL,
  has_eip_access BOOLEAN DEFAULT false,
  access_level TEXT CHECK (access_level IN ('viewer', 'contributor', 'lead')),
  hours_per_week INTEGER,
  start_date DATE,
  end_date DATE,
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE workstream_members ENABLE ROW LEVEL SECURITY;
CREATE POLICY "team_access" ON workstream_members
  FOR ALL USING (auth.uid() IN (
    SELECT user_id FROM team_members WHERE is_active = true
  ));

-- Reportes generados
CREATE TABLE project_reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  report_type TEXT NOT NULL CHECK (report_type IN (
    'avance_ejecutivo', 'entregable_parcial', 'reporte_final', 'presentacion_hallazgos',
    'sincronizacion_interna', 'reporte_subcontratista', 'reporte_financiero', 'risk_log'
  )),
  title TEXT NOT NULL,
  period_start DATE,
  period_end DATE,
  client_facing BOOLEAN NOT NULL DEFAULT false,
  executive_summary TEXT,
  content JSONB DEFAULT '{}',
  overall_progress_pct INTEGER,
  on_schedule BOOLEAN,
  budget_status TEXT CHECK (budget_status IN ('en_presupuesto', 'riesgo', 'sobrepasado')),
  file_url TEXT,
  file_name TEXT,
  status TEXT NOT NULL DEFAULT 'borrador' CHECK (status IN (
    'borrador', 'revision_interna', 'aprobado', 'enviado_cliente'
  )),
  generated_by UUID REFERENCES auth.users(id),
  generated_at TIMESTAMPTZ DEFAULT now(),
  sent_at TIMESTAMPTZ,
  sent_by UUID REFERENCES auth.users(id),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TRIGGER reports_updated_at
  BEFORE UPDATE ON project_reports
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

ALTER TABLE project_reports ENABLE ROW LEVEL SECURITY;
CREATE POLICY "team_access" ON project_reports
  FOR ALL USING (auth.uid() IN (
    SELECT user_id FROM team_members WHERE is_active = true
  ));
