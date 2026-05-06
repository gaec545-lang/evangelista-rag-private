"""Team Management router — Evangelista Intelligence Platform.
Crea usuarios en Supabase Auth y los registra en team_members con permisos por rol.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.utils.logger import get_logger
from src.config import settings
import httpx

logger = get_logger(__name__)

router = APIRouter()

ROLE_PERMISSIONS = {
    "ceo":         {"operations": True,  "architecture_rag": True,  "erp_connections": True,  "team_management": True  },
    "cto":         {"operations": True,  "architecture_rag": True,  "erp_connections": True,  "team_management": False },
    "cfo_cqa":     {"operations": True,  "architecture_rag": False, "erp_connections": False, "team_management": False },
    "consultant":  {"operations": True,  "architecture_rag": False, "erp_connections": False, "team_management": False },
    "viewer":      {"operations": True,  "architecture_rag": False, "erp_connections": False, "team_management": False },
}

SUPABASE_URL = settings.SUPABASE_URL
SERVICE_KEY = settings.SUPABASE_SERVICE_KEY


# ─── Schemas ───

class InviteRequest(BaseModel):
    email: str
    full_name: str
    role: str

class UpdatePermissionsRequest(BaseModel):
    permissions: dict

class UpdateMemberRequest(BaseModel):
    full_name: Optional[str] = None
    is_active: Optional[bool] = None


# ─── Helpers ───

def _headers():
    return {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


# ─── Endpoints ───

@router.get("/api/v1/team/list", tags=["Team"])
async def team_list():
    """Listar todos los miembros del equipo."""
    if not SERVICE_KEY:
        return []

    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"{SUPABASE_URL}/rest/v1/team_members?select=*&order=role.asc",
            headers=_headers()
        )
        if res.status_code != 200:
            raise HTTPException(status_code=res.status_code, detail=res.text)

        members = res.json()
        # Normalizar permisos por rol para cada miembro
        for m in members:
            if not m.get("permissions"):
                m["permissions"] = ROLE_PERMISSIONS.get(m["role"], ROLE_PERMISSIONS["viewer"])

        return members


@router.post("/api/v1/team/invite", tags=["Team"])
async def team_invite(data: InviteRequest):
    """Invitar un nuevo miembro.
    1. Crea el usuario en Supabase Auth (service role)
    2. Inserta el registro en team_members con permisos del rol
    """
    if not SERVICE_KEY:
        raise HTTPException(status_code=500, detail="SUPABASE_SERVICE_KEY no configurado")

    if data.role not in ROLE_PERMISSIONS:
        raise HTTPException(status_code=400, detail=f"Rol inválido: {data.role}. Validos: {list(ROLE_PERMISSIONS.keys())}")

    # 1. Crear usuario en Supabase Auth
    password = f"EvCo@{data.full_name.split()[0]}2026!"
    auth_url = f"{SUPABASE_URL}/auth/v1/admin/users"

    async with httpx.AsyncClient() as client:
        auth_res = await client.post(
            auth_url,
            headers=_headers(),
            json={
                "email": data.email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"full_name": data.full_name},
            },
        )

        if auth_res.status_code not in (200, 201, 409):
            raise HTTPException(
                status_code=auth_res.status_code,
                detail=f"Error creando usuario: {auth_res.text}",
            )

        # Obtener la respuesta
        if auth_res.status_code == 409:
            raise HTTPException(status_code=409, detail=f"El email {data.email} ya está registrado.")

        auth_data = auth_res.json()
        user_id = auth_data["id"]

        # 2. Insertar en team_members
        team_res = await client.post(
            f"{SUPABASE_URL}/rest/v1/team_members",
            headers=_headers(),
            json={
                "user_id": user_id,
                "full_name": data.full_name,
                "role": data.role,
                "email": data.email,
                "permissions": ROLE_PERMISSIONS[data.role],
                "is_active": True,
            },
        )

        if team_res.status_code not in (200, 201):
            raise HTTPException(status_code=team_res.status_code, detail=f"Error en team_members: {team_res.text}")

    logger.info("team_member_invited", email=data.email, role=data.role)

    return {
        "message": "Miembro invitado exitosamente",
        "email": data.email,
        "role": data.role,
        "temporary_password": password,
    }


@router.patch("/api/v1/team/{member_id}", tags=["Team"])
async def team_update(member_id: str, data: UpdateMemberRequest):
    """Actualizar nombre o estado de un miembro."""
    updates = {}
    if data.full_name is not None:
        updates["full_name"] = data.full_name
    if data.is_active is not None:
        updates["is_active"] = data.is_active

    async with httpx.AsyncClient() as client:
        res = await client.patch(
            f"{SUPABASE_URL}/rest/v1/team_members?id=eq.{member_id}",
            headers=_headers(),
            json=updates,
        )
        if res.status_code != 200:
            raise HTTPException(status_code=res.status_code, detail=res.text)

    return {"message": "Miembro actualizado"}


@router.patch("/api/v1/team/{member_id}/permissions", tags=["Team"])
async def team_update_permissions(member_id: str, data: UpdatePermissionsRequest):
    """Actualizar permisos de un miembro."""
    async with httpx.AsyncClient() as client:
        res = await client.patch(
            f"{SUPABASE_URL}/rest/v1/team_members?id=eq.{member_id}",
            headers=_headers(),
            json={"permissions": data.permissions},
        )
        if res.status_code != 200:
            raise HTTPException(status_code=res.status_code, detail=res.text)

    return {"message": "Permisos actualizados", "permissions": data.permissions}


@router.post("/api/v1/team/{member_id}/deactivate", tags=["Team"])
async def team_deactivate(member_id: str):
    """Desactivar un miembro del equipo."""
    async with httpx.AsyncClient() as client:
        res = await client.patch(
            f"{SUPABASE_URL}/rest/v1/team_members?id=eq.{member_id}",
            headers=_headers(),
            json={"is_active": False},
        )
        if res.status_code != 200:
            raise HTTPException(status_code=res.status_code, detail=res.text)

    return {"message": "Miembro desactivado"}
