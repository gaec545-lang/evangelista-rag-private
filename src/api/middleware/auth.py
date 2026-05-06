"""Auth Middleware — JWT verification for protected endpoints."""
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

security = HTTPBearer()

_supabase = None


def get_supabase():
    global _supabase
    if _supabase is None:
        _supabase = create_client(
            settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY
        )
    return _supabase


async def verify_jwt(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Verifica el JWT de Supabase y retorna el payload del usuario.

    Raises HTTPException(401) si el token es invalido o expirado.
    """
    sb = get_supabase()
    try:
        user_resp = sb.auth.get_user(credentials.credentials)
        if not user_resp or not user_resp.user:
            raise HTTPException(status_code=401, detail="Token invalido")
        return {
            "user_id": user_resp.user.id,
            "email": user_resp.user.email,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("jwt_verification_failed", error=str(e))
        raise HTTPException(status_code=401, detail="No autorizado")


# Dependencia que verifica que el subscription_id pertenece al usuario
async def verify_subscription_ownership(
    subscription_id: str,
    user: dict = Depends(verify_jwt),
) -> dict:
    """Verifica que el subscription_id existe y pertenece al usuario autenticado."""
    sb = get_supabase()
    try:
        result = (
            sb.table("sentinel_subscriptions")
            .select("id, client_id, assigned_to")
            .eq("id", subscription_id)
            .single()
            .execute()
        )
        if not result.data:
            raise HTTPException(
                status_code=404, detail="Suscripcion no encontrada"
            )
        return {"user": user, "subscription": result.data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("subscription_verification_failed", error=str(e))
        raise HTTPException(
            status_code=403, detail="No tiene acceso a esta suscripcion"
        )
