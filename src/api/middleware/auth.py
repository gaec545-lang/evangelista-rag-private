"""Auth Middleware — JWT verification for protected endpoints."""
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# Supabase integration removed – use Azure auth instead.
from src.utils.logger import get_logger

logger = get_logger(__name__)

security = HTTPBearer()

# Placeholder – Supabase client not required.

# Placeholder authentication functions – implement Azure JWT verification.
async def verify_jwt(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Placeholder for JWT verification using Azure AD or another provider."""
    raise NotImplementedError("JWT verification not implemented – replace with Azure auth logic")


# Dependencia que verifica que el subscription_id pertenece al usuario
async def verify_subscription_ownership(subscription_id: str, user: dict = Depends(verify_jwt)) -> dict:
    """Placeholder for subscription ownership verification using Azure DB."""
    raise NotImplementedError("Subscription ownership verification not implemented")
