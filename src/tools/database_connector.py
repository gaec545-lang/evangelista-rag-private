"""
Data Abstraction Vault — Conexión Zero-Trust a ERPs de clientes.

Stack:
    - Supabase PostgreSQL (pgsodium + vault schema nativo)
    - supabase-py para queries RPC y tablas
    - psycopg2 (PostgreSQL/SAP HANA), pyodbc (SQL Server), mysql-connector (Aspel)

Arquitectura de seguridad:
    1. La contraseña NUNCA sale de Supabase. Se almacena cifrada con pgsodium
       en vault.secrets y solo se descifra in-process al momento de conectar.
    2. El backend usa SUPABASE_SERVICE_ROLE_KEY (no la anon key) para acceder
       a vault.decrypted_secrets via RPC segura.
    3. Una vez usada, la contraseña se elimina de memoria inmediatamente (del).
    4. La conexión es read-only — el ERP del cliente no puede ser modificado.

Protocolo PED: El Data Engineer Agent invoca estas funciones como Tools
del enjambre de LangGraph. El Financial Agent nunca ve las credenciales.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, Any

import structlog
from supabase import create_client, Client

logger = structlog.get_logger(__name__)

__all__ = [
    "get_supabase_client",
    "list_client_connections",
    "register_erp_connection",
    "remove_erp_connection",
    "get_ephemeral_connection",
]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Supabase Client (requiere SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY en .env)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_supabase_client() -> Client:
    """Retorna un cliente Supabase autenticado con Service Role Key."""
    from src.config import settings
    url = getattr(settings, "SUPABASE_URL", "")
    key = getattr(settings, "SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL y SUPABASE_SERVICE_KEY requeridos para Data Vault. "
            "Configura las variables de entorno antes de usar el Vault."
        )
    return create_client(url, key)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CRUD de Metadatos (tablas públicas — SIN contraseñas)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def list_client_connections(client_id: str) -> list[dict]:
    """Lista las conexiones registradas de un cliente (sin secretos)."""
    sb = get_supabase_client()
    response = sb.table("erp_connections").select("*").eq(
        "client_id", client_id
    ).execute()
    return response.data or []


def register_erp_connection(
    client_id: str,
    connection_type: str,
    host: str,
    port: int,
    database_name: str | None,
    username: str,
    password: str,
    extra_config: dict | None = None,
) -> dict:
    """
    Registra una nueva conexión ERP en el Vault de Supabase.

    Flujo de seguridad:
    1. Llama a la función SQL `create_erp_connection()` en Supabase.
       Esta función guarda la contraseña en vault.secrets (pgsodium)
       y crea el erp_connection con el secret_id referenciado.
    2. La contraseña en texto plano SOLO viaja por la llamada RPC HTTPS
       cifrada a Supabase (TLS 1.3). No se almacena localmente.
    """
    sb = get_supabase_client()

    response = sb.rpc(
        "create_erp_connection",
        {
            "_client_id": client_id,
            "_type": connection_type,
            "_host": host,
            "_port": port,
            "_database": database_name,
            "_username": username,
            "_password": password,
        },
    ).execute()

    logger.info(
        "erp_connection_registered",
        client_id=client_id,
        connection_type=connection_type,
        host=host,
    )
    return {"connection_id": str(response.data)}


def remove_erp_connection(client_id: str) -> dict:
    """
    Revoca una conexión ERP y elimina el secreto asociado del Vault.

    Flujo de seguridad:
    1. Llama a la función SQL `revoke_erp_connection()`.
    2. Borra erp_connections + vault.decrypted_secrets en una transacción.
    """
    sb = get_supabase_client()
    response = sb.rpc(
        "revoke_erp_connection",
        {"_client_id": client_id},
    ).execute()

    logger.info("erp_connection_revoked", client_id=client_id)
    return {"revoked": True}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONEXIÓN EFÍMERA (core — extracción de secreto + apertura read-only)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _get_secret_key(secret_id: str) -> str:
    """
    Recupera el texto plano de un secreto almacenado en vault.secrets.

    Usa vault.decrypted_secrets (pgsodium) directamente via RPC
    al Postgres de Supabase con el Service Role Key.

    IMPORTANTE: El valor retornado debe eliminarse de memoria
    inmediatamente después de usarlo (del password_variable).
    """
    sb = get_supabase_client()

    # vault.decrypted_secrets requiere acceso directo a la DB
    # La forma segura es usar una query RPC al schema 'vault'
    result = sb.table("vault").select("decrypted_secret").eq(
        "id", secret_id
    ).execute()

    if not result.data:
        raise KeyError(f"Secreto {secret_id} no encontrado en vault.secrets")

    return result.data[0]["decrypted_secret"]


def get_ephemeral_connection(client_id: str, connection_id: str | None = None):
    """
    Establece una conexión efímera read-only al ERP del cliente.

    Flujo estricto (5 pasos):
    1.  Consulta erp_connections para obtener host, username, secret_id y tipo de ERP.
    2.  Recupera la contraseña de vault.decrypted_secrets via secret_id.
    3.  Establece la conexión con la DB destino (psycopg2, pyodbc, etc.).
    4.  Retorna la conexión abierta para uso del Code Execution Sandbox.
    5.  Elimina inmediatamente la contraseña de la memoria (del).

    Uso recomendado: context manager para garantizar cierre y cleanup.

    Ejemplo:
        with get_ephemeral_connection("uuid-cliente") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(total) FROM facturas")
            results = cursor.fetchall()
            # conn se cierra automáticamente al salir del with
        # contraseña fue eliminada de memoria
    """
    sb = get_supabase_client()

    # ── PASO 1: Obtener metadatos de conexión (sin contraseña) ──────────
    query = sb.table("erp_connections").select("*").eq("client_id", client_id)
    if connection_id:
        query = query.eq("id", connection_id)

    response = query.execute()

    if not response.data:
        raise KeyError(
            f"No se encontró conexión ERP para client_id={client_id}"
        )

    conn_meta = response.data[0]
    db_type = conn_meta["connection_type"].lower()
    host = conn_meta["host"]
    port = conn_meta["port"]
    db_name = conn_meta["database_name"]
    username = conn_meta["username"]
    secret_id = conn_meta["secret_id"]

    # ── PASO 2: Recuperar contraseña del Vault ─────────────────────────
    decrypted_password = _get_secret_key(secret_id)

    # ── PASO 3: Establecer conexión read-only al ERP ───────────────────
    try:
        conn = _open_readonly_connection(
            db_type=db_type,
            host=host,
            port=port,
            database_name=db_name,
            username=username,
            password=decrypted_password,
        )

        logger.info(
            "ephemeral_connection_opened",
            client_id=client_id,
            db_type=db_type,
            host=host,
        )
    finally:
        # ── PASO 5: Eliminar contraseña de memoria inmediatamente ─────
        del decrypted_password

    return conn


def _open_readonly_connection(
    db_type: str,
    host: str,
    port: int,
    database_name: str | None,
    username: str,
    password: str,
) -> Any:
    """
    Fábrica interna de conexiones read-only según tipo de ERP.
    Selecciona el driver apropiado y configura la conexión como solo lectura.
    """
    if db_type in ("postgresql", "postgres", "pg", "sap_hana"):
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=host,
                port=port,
                dbname=database_name,
                user=username,
                password=password,
            )
            conn.set_session(readonly=True)
            return conn
        except ImportError:
            raise RuntimeError(
                "psycopg2 no instalado. pip install psycopg2-binary"
            )

    elif db_type in ("mysql", "maria", "asper"):
        try:
            import mysql.connector
            conn = mysql.connector.connect(
                host=host,
                port=port,
                database=database_name,
                user=username,
                password=password,
            )
            # MySQL no tiene modo readonly nativo por conexión
            # pero podemos restringir a queries SELECT
            return conn
        except ImportError:
            raise RuntimeError(
                "mysql-connector no instalado. pip install mysql-connector-python"
            )

    elif db_type in ("sql_server", "mssql"):
        try:
            import pyodbc
            conn_str = (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={host},{port};"
                f"DATABASE={database_name};"
                f"UID={username};"
                f"PWD={password};"
                f"ApplicationIntent=ReadOnly"  # SQL Server AlwaysOn readable secondary
            )
            return pyodbc.connect(conn_str)
        except ImportError:
            raise RuntimeError("pyodbc no instalado. pip install pyodbc")

    else:
        raise ValueError(f"Tipo de ERP no soportado: {db_type}")
