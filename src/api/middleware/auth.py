"""Auth Middleware — JWT verification for protected endpoints using Entra ID."""
import json
from urllib.request import urlopen
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from src.utils.logger import get_logger
from src.config import settings

logger = get_logger(__name__)

security = HTTPBearer()

_jwks = None

def get_jwks():
    global _jwks
    if _jwks is None:
        tenant_id = settings.ENTRA_ID_TENANT_ID
        if not tenant_id:
            logger.error("ENTRA_ID_TENANT_ID is not configured.")
            raise HTTPException(status_code=500, detail="Identity provider not configured.")
        
        jwks_url = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
        try:
            with urlopen(jwks_url) as response:
                _jwks = json.loads(response.read().decode("utf-8"))
        except Exception as e:
            logger.error(f"Failed to fetch JWKS: {e}")
            raise HTTPException(status_code=500, detail="Failed to fetch JWKS")
    return _jwks

async def verify_jwt(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Valida el token JWT de Entra ID contra el JWKS público."""
    token = credentials.credentials
    try:
        unverified_header = jwt.get_unverified_header(token)
        rsa_key = {}
        
        jwks = get_jwks()
        for key in jwks.get("keys", []):
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"]
                }
                break
                
        if rsa_key:
            client_id = settings.ENTRA_ID_CLIENT_ID
            tenant_id = settings.ENTRA_ID_TENANT_ID
            # issuer typically looks like this for v2.0
            issuer = f"https://login.microsoftonline.com/{tenant_id}/v2.0"
            
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=["RS256"],
                audience=client_id,
                issuer=issuer
            )
            
            roles = payload.get("roles", [])
            allowed_roles = {"socio", "cqa", "consultor"}
            
            if not any(role in allowed_roles for role in roles):
                raise HTTPException(status_code=403, detail="Insufficient role privileges")
                
            user_oid = payload.get("oid")
            if not user_oid:
                raise HTTPException(status_code=401, detail="Token missing oid")
                
            return {
                "oid": user_oid,
                "roles": roles,
                "preferred_username": payload.get("preferred_username")
            }
        
        raise HTTPException(status_code=401, detail="Unable to find appropriate key")
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.JWTClaimsError:
        raise HTTPException(status_code=401, detail="Invalid claims. Check audience and issuer.")
    except Exception as e:
        logger.error(f"Error validating token: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")

async def verify_subscription_ownership(subscription_id: str, user: dict = Depends(verify_jwt)) -> dict:
    """Placeholder for subscription ownership verification using Azure DB."""
    # To be implemented
    raise NotImplementedError("Subscription ownership verification not implemented")
