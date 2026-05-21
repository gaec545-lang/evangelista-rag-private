"""
init_azure_postgres_psycopg2.py
Inicializa Azure PostgreSQL usando psycopg2 (sin depender de psql en PATH).
"""
import sys
import os

try:
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
except ImportError:
    print("ERROR: psycopg2 no instalado. Ejecuta: pip install psycopg2-binary")
    sys.exit(1)

DB_URL = "postgresql://evangelista_admin:EIP_S3cur3!2025#@pg-evangelista-prod.postgres.database.azure.com:5432/postgres?sslmode=require"

INIT_SQL = """
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

DO $$ BEGIN CREATE ROLE anon NOLOGIN NOINHERIT; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE ROLE authenticated NOLOGIN NOINHERIT; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE ROLE service_role NOLOGIN NOINHERIT BYPASSRLS; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE ROLE supabase_admin NOLOGIN BYPASSRLS; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE ROLE supabase_auth_admin NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE ROLE supabase_storage_admin NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE ROLE authenticator NOINHERIT LOGIN PASSWORD 'EIP_S3cur3!2025#'; EXCEPTION WHEN duplicate_object THEN NULL; END $$;

GRANT anon TO authenticator;
GRANT authenticated TO authenticator;
GRANT service_role TO authenticator;
GRANT supabase_admin TO authenticator;

GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO anon, authenticated, service_role;

CREATE SCHEMA IF NOT EXISTS auth;
GRANT ALL ON SCHEMA auth TO supabase_auth_admin;
GRANT USAGE ON SCHEMA auth TO anon, authenticated, service_role;

CREATE SCHEMA IF NOT EXISTS storage;
GRANT ALL ON SCHEMA storage TO supabase_storage_admin;
GRANT USAGE ON SCHEMA storage TO anon, authenticated, service_role;

CREATE SCHEMA IF NOT EXISTS graphql_public;
GRANT USAGE ON SCHEMA graphql_public TO anon, authenticated, service_role;
"""

def main():
    print("Conectando a Azure PostgreSQL...")
    try:
        conn = psycopg2.connect(DB_URL)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        print("Conexion exitosa!")

        print("Ejecutando script de inicializacion...")
        cur.execute(INIT_SQL)
        print("Extensiones, roles y schemas creados.")

        # Ejecutar migraciones del proyecto
        migrations_dir = os.path.join(os.path.dirname(__file__), "..", "supabase", "migrations")
        if os.path.isdir(migrations_dir):
            for f in sorted(os.listdir(migrations_dir)):
                if f.endswith(".sql"):
                    path = os.path.join(migrations_dir, f)
                    with open(path, encoding="utf-8") as fp:
                        sql = fp.read()
                    try:
                        cur.execute(sql)
                        print(f"Migracion aplicada: {f}")
                    except Exception as e:
                        print(f"WARN en {f}: {e}")
                        conn.rollback()
                        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

        cur.close()
        conn.close()
        print("\nBase de datos inicializada exitosamente!")
        print(f"Host: pg-evangelista-prod.postgres.database.azure.com")

    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
