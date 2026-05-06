"""
Tools del Enjambre Multi-Agente EIP.

Zero-Trust: credenciales nunca en texto plano.
Supabase Vault nativo (pgsodium) para almacenamiento de secretos.
"""
from .database_connector import get_ephemeral_connection
# from .sql_generator import sql_from_prompt

__all__ = ["get_ephemeral_connection"] # , "sql_from_prompt"]
