-- ============================================================
-- SEED: Registrar usuario Admin (direccion@evangelistaco.com)
-- Ejecutar en Supabase Dashboard > SQL Editor UNA SOLA VEZ
-- ============================================================

-- 1. Obtener el user_id del usuario existente en Supabase Auth
--    Reemplaza este email si es diferente
DO $$
DECLARE
  v_user_id UUID;
BEGIN
  -- Buscar el user_id en auth.users
  SELECT id INTO v_user_id
  FROM auth.users
  WHERE email = 'direccion@evangelistaco.com';

  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'No se encontró el usuario direccion@evangelistaco.com en Supabase Auth. Primero crearlo desde Authentication > Users.';
  END IF;

  -- 2. Insertar o actualizar en team_members como CEO
  INSERT INTO team_members (user_id, full_name, role, email, permissions, is_active)
  VALUES (
    v_user_id,
    'Admin General',
    'ceo',
    'direccion@evangelistaco.com',
    '{"operations": true, "architecture_rag": true, "erp_connections": true, "team_management": true}',
    true
  )
  ON CONFLICT (email) DO UPDATE SET
    role = 'ceo',
    permissions = '{"operations": true, "architecture_rag": true, "erp_connections": true, "team_management": true}'::jsonb,
    is_active = true,
    updated_at = NOW();
END $$;
