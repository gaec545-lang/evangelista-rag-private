"""
generate_supabase_keys.py
Genera los tres tokens JWT necesarios para un despliegue
self-hosted de Supabase: JWT_SECRET, ANON_KEY y SERVICE_ROLE_KEY.
"""
import hmac, hashlib, base64, json, time

JWT_SECRET = "20f85b60200e3eb9416bc58ad9aa9d2ed2bd31a58a084838744c6a6776668e7c"

def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def make_jwt(payload: dict, secret: str) -> str:
    header = b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body   = b64url(json.dumps(payload).encode())
    msg    = f"{header}.{body}".encode()
    sig    = b64url(hmac.new(secret.encode(), msg, hashlib.sha256).digest())
    return f"{header}.{body}.{sig}"

now = int(time.time())
exp = now + (10 * 365 * 24 * 3600)  # 10 años

anon_payload = {
    "role": "anon",
    "iss": "supabase",
    "iat": now,
    "exp": exp,
}

service_role_payload = {
    "role": "service_role",
    "iss": "supabase",
    "iat": now,
    "exp": exp,
}

anon_key         = make_jwt(anon_payload, JWT_SECRET)
service_role_key = make_jwt(service_role_payload, JWT_SECRET)

print(f"JWT_SECRET={JWT_SECRET}")
print(f"ANON_KEY={anon_key}")
print(f"SERVICE_ROLE_KEY={service_role_key}")
