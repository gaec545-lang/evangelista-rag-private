#!/usr/bin/env python3
"""
migrate_supabase_to_azure.py
────────────────────────────
Script para exportar la base de datos de Supabase (online) e importarla
en Azure PostgreSQL Flexible Server.

Prerequisitos:
  pip install psycopg2-binary
  pg_dump y psql en PATH (instalar desde: https://www.postgresql.org/download/)

Uso:
  python scripts/migrate_supabase_to_azure.py
"""

import os
import subprocess
import sys
from datetime import datetime

# ── Configuración ────────────────────────────────────────────────────────────
SUPABASE_DB_URL = os.environ.get(
    "SUPABASE_DB_URL",
    # Formato: postgresql://postgres.REFID:PASSWORD@aws-0-us-east-1.pooler.supabase.com:6543/postgres
    "postgresql://postgres.zqyqtcteqtbkadkflaku:EIP_PASSWORD@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
)

AZURE_DB_URL = os.environ.get(
    "AZURE_DB_URL",
    "postgresql://evangelista_admin:EIP_S3cur3!2025#@pg-evangelista-prod.postgres.database.azure.com:5432/postgres?sslmode=require"
)

DUMP_FILE = f"supabase_dump_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"

# Schemas a migrar (excluimos los internos de Supabase que serán re-creados)
SCHEMAS_TO_DUMP = ["public", "storage"]


def run(cmd: list[str], env: dict | None = None) -> int:
    """Ejecuta un comando y retorna el código de salida."""
    print(f"\n▶ Ejecutando: {' '.join(cmd)}")
    result = subprocess.run(cmd, env={**os.environ, **(env or {})})
    if result.returncode != 0:
        print(f"✗ Error (código {result.returncode})")
    else:
        print(f"✓ OK")
    return result.returncode


def main():
    print("=" * 60)
    print("  Migración Supabase → Azure PostgreSQL")
    print("=" * 60)

    # ── 1. Dump desde Supabase ───────────────────────────────────────────────
    print(f"\n[1/3] Exportando datos de Supabase → {DUMP_FILE}")
    schema_flags = []
    for schema in SCHEMAS_TO_DUMP:
        schema_flags.extend(["-n", schema])

    rc = run([
        "pg_dump",
        "--no-owner",           # No preservar ownership (usuarios diferentes)
        "--no-acl",             # No preservar ACLs (se re-configuran con RLS)
        "--if-exists",
        "--clean",
        "-Fp",                  # Formato texto plano
        *schema_flags,
        "-f", DUMP_FILE,
        SUPABASE_DB_URL
    ])

    if rc != 0:
        print("\n✗ Error al exportar. Verifica que pg_dump esté instalado y la URL de Supabase sea correcta.")
        sys.exit(1)

    print(f"✓ Dump guardado en: {DUMP_FILE}")

    # ── 2. Preparar Azure PostgreSQL ─────────────────────────────────────────
    print("\n[2/3] Preparando extensiones en Azure PostgreSQL")
    setup_sql = """
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "vector";
-- pgsodium puede requerir instalación manual en Azure
-- CREATE EXTENSION IF NOT EXISTS "pgsodium";
"""

    with open("_setup_extensions.sql", "w") as f:
        f.write(setup_sql)

    rc = run([
        "psql",
        "-f", "_setup_extensions.sql",
        AZURE_DB_URL
    ])

    os.remove("_setup_extensions.sql")

    if rc != 0:
        print("⚠️ Algunas extensiones pueden no haberse creado. Continúa con cautela.")

    # ── 3. Restore en Azure ─────────────────────────────────────────────────
    print(f"\n[3/3] Importando {DUMP_FILE} en Azure PostgreSQL")
    rc = run([
        "psql",
        "-f", DUMP_FILE,
        AZURE_DB_URL
    ])

    if rc != 0:
        print("\n✗ Error durante la importación. Revisa el archivo SQL para errores.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  ✓ Migración completada exitosamente")
    print(f"  Dump guardado en: {DUMP_FILE}")
    print("=" * 60)
    print("\nPróximos pasos:")
    print("  1. Verifica los datos en Azure con: psql $AZURE_DB_URL -c 'SELECT COUNT(*) FROM clients;'")
    print("  2. Ejecuta las migraciones pendientes del RAG MOAT v2.3")
    print("  3. Actualiza las variables de entorno del Backend y Frontend")


if __name__ == "__main__":
    main()
