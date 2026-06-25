"""Auth Middleware — JWT verification for protected endpoints."""
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from src.utils.logger import get_logger
from src.config import settings

logger = get_logger(__name__)

security = HTTPBearer()

async def verify_jwt(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Valida el token JWT local."""
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=["HS256"]
        )
        
        roles = payload.get("roles", [])
        allowed_roles = {"socio", "cqa", "consultor"}
        
        if not any(role in allowed_roles for role in roles):
            raise HTTPException(status_code=403, detail="Insufficient role privileges")
            
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Token missing subject")
            
        return {
            "id": user_id,
            "roles": roles,
            "email": payload.get("email")
        }
    
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        logger.error(f"Error validating token: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")

async def verify_subscription_ownership(subscription_id: str, user: dict = Depends(verify_jwt)) -> dict:
    """Placeholder for subscription ownership verification using Azure DB."""
    # ponytail: raising HTTPException avoids unhandled 500 server crashes on unimplemented endpoints
    raise HTTPException(status_code=501, detail="Subscription ownership verification not implemented")
