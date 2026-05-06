-- 05_modulo_cierre.sql
-- Migración para el Módulo de Contratos, Transiciones de Fase y Cierre

-- Control de pagos acordados y recibidos por proyecto
CREATE TABLE project_payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  payment_type TEXT NOT NULL CHECK (payment_type IN (
    'anticipo',        -- Pago inicial (típico: 50%)
    'parcial',         -- Pago intermedio por hito
    'finiquito',       -- Pago final al cierre
    'subcontratista'   -- Pago saliente a subcontratista (interno)
  )),
  direction TEXT NOT NULL DEFAULT 'entrante' CHECK (direction IN (
    'entrante',        -- Del cliente a Evangelista
    'saliente'         -- De Evangelista a subcontratista
  )),
  description TEXT NOT NULL,             -- Ej: "Anticipo 50% — Proyecto HTD"
  amount NUMERIC(12,2) NOT NULL,
  currency TEXT NOT NULL DEFAULT 'MXN',
  due_date DATE,                         -- Fecha acordada de pago
  received_at TIMESTAMPTZ,              -- Fecha real de recepción (null = pendiente)
  received BOOLEAN NOT NULL DEFAULT false,
  payment_method TEXT CHECK (payment_method IN (
    'transferencia', 'cheque', 'efectivo', 'otro'
  )),
  reference TEXT,                        -- Número de referencia bancaria
  notes TEXT,
  workstream_id UUID REFERENCES project_workstreams(id),  -- Para pagos a subcontratistas
  created_by UUID REFERENCES auth.users(id),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TRIGGER payments_updated_at
  BEFORE UPDATE ON project_payments
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

ALTER TABLE project_payments ENABLE ROW LEVEL SECURITY;
CREATE POLICY "team_access" ON project_payments
  FOR ALL USING (auth.uid() IN (
    SELECT user_id FROM team_members WHERE is_active = true
  ));

-- Registro inmutable de cada transición de fase
CREATE TABLE project_phase_transitions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  from_phase TEXT NOT NULL,
  to_phase TEXT NOT NULL,
  confirmed_by UUID REFERENCES auth.users(id),
  confirmed_by_name TEXT NOT NULL,
  justification TEXT,                   -- Nota del CEO al confirmar
  conditions_met JSONB NOT NULL DEFAULT '[]',
  -- Array de { label, met: bool } — snapshot de condiciones al momento de confirmar
  transitioned_at TIMESTAMPTZ DEFAULT now()
  -- Inmutable — sin UPDATE ni DELETE
);

ALTER TABLE project_phase_transitions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "team_read" ON project_phase_transitions
  FOR SELECT USING (auth.uid() IN (
    SELECT user_id FROM team_members WHERE is_active = true
  ));
CREATE POLICY "team_insert" ON project_phase_transitions
  FOR INSERT WITH CHECK (auth.uid() IN (
    SELECT user_id FROM team_members WHERE is_active = true
  ));

-- Registro del cierre formal del proyecto
CREATE TABLE project_closure (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID UNIQUE NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

  -- Checklist de cierre
  deliverables_accepted BOOLEAN DEFAULT false,
  credentials_revoked BOOLEAN DEFAULT false,
  final_payment_received BOOLEAN DEFAULT false,
  acta_signed BOOLEAN DEFAULT false,
  lessons_documented BOOLEAN DEFAULT false,

  -- Datos del acta
  client_signer_name TEXT,
  client_signer_role TEXT,
  close_date DATE,

  -- Evaluación post-proyecto
  client_satisfaction TEXT CHECK (client_satisfaction IN (
    'excelente', 'bueno', 'regular', 'malo'
  )),
  client_comments TEXT,
  team_rating INTEGER CHECK (team_rating BETWEEN 1 AND 5),

  -- Lecciones aprendidas (resumen)
  what_worked TEXT,
  what_failed TEXT,
  next_time TEXT,

  status TEXT NOT NULL DEFAULT 'pendiente' CHECK (status IN (
    'pendiente', 'en_proceso', 'cerrado'
  )),

  closed_by UUID REFERENCES auth.users(id),
  closed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TRIGGER closure_updated_at
  BEFORE UPDATE ON project_closure
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

ALTER TABLE project_closure ENABLE ROW LEVEL SECURITY;
CREATE POLICY "team_access" ON project_closure
  FOR ALL USING (auth.uid() IN (
    SELECT user_id FROM team_members WHERE is_active = true
  ));
