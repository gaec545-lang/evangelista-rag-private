-- =============================================================
-- MIGRACIÓN: time_entries (H1-A: Time Tracker)
-- Plan de Innovación Evangelista v1.0 · 2026-05-06
-- Aplicar en: Supabase → SQL Editor → Run
-- =============================================================

CREATE TABLE IF NOT EXISTS public.time_entries (
  id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  team_member_id    UUID        NOT NULL REFERENCES team_members(id) ON DELETE CASCADE,
  project_id        UUID        REFERENCES projects(id) ON DELETE SET NULL,
  foundation_id     UUID        REFERENCES foundation_engagements(id) ON DELETE SET NULL,
  sentinel_id       UUID        REFERENCES sentinel_subscriptions(id) ON DELETE SET NULL,
  architecture_id   UUID        REFERENCES architecture_projects(id) ON DELETE SET NULL,

  category          TEXT        NOT NULL CHECK (category IN (
                      'scoping','analisis','presentacion','documentacion',
                      'reunion_cliente','administracion','otro'
                    )),
  description       TEXT        NOT NULL,
  date              DATE        NOT NULL DEFAULT CURRENT_DATE,
  hours             NUMERIC(5,2) NOT NULL CHECK (hours > 0 AND hours <= 24),
  billable          TEXT        NOT NULL DEFAULT 'facturable' CHECK (billable IN (
                      'facturable','no_facturable','interno'
                    )),
  hourly_rate       NUMERIC(10,2) DEFAULT 0,
  notes             TEXT,

  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Auto-update updated_at
CREATE OR REPLACE TRIGGER set_time_entries_updated_at
  BEFORE UPDATE ON public.time_entries
  FOR EACH ROW EXECUTE FUNCTION moddatetime(updated_at);

-- Indices para consultas frecuentes
CREATE INDEX idx_time_entries_member    ON public.time_entries(team_member_id);
CREATE INDEX idx_time_entries_project   ON public.time_entries(project_id);
CREATE INDEX idx_time_entries_date      ON public.time_entries(date DESC);
CREATE INDEX idx_time_entries_billable  ON public.time_entries(billable);

-- RLS: Cada consultor ve sus propias entradas. CEO/Socios ven todas.
ALTER TABLE public.time_entries ENABLE ROW LEVEL SECURITY;

CREATE POLICY "time_entries_own" ON public.time_entries
  FOR ALL TO authenticated
  USING (
    team_member_id = (
      SELECT id FROM team_members WHERE user_id = auth.uid() LIMIT 1
    )
    OR EXISTS (
      SELECT 1 FROM team_members
      WHERE user_id = auth.uid() AND role IN ('ceo', 'cto', 'cfo_cqa')
    )
  );

-- Vista: rentabilidad por proyecto (para Dashboard de Socio)
CREATE OR REPLACE VIEW public.v_project_profitability AS
SELECT
  project_id,
  SUM(hours)                                              AS total_hours,
  SUM(CASE WHEN billable = 'facturable' THEN hours END)  AS billable_hours,
  SUM(CASE WHEN billable = 'facturable' THEN hours * hourly_rate END) AS estimated_revenue,
  ROUND(
    100.0 * SUM(CASE WHEN billable = 'facturable' THEN hours END) / NULLIF(SUM(hours), 0), 1
  )                                                       AS efficiency_pct
FROM public.time_entries
WHERE project_id IS NOT NULL
GROUP BY project_id;
