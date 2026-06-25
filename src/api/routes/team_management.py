"""Team Management router — Evangelista Intelligence Platform.

Supabase integration removed. Endpoints are placeholders pending Azure implementation.
"""

from fastapi import APIRouter, HTTPException

router = APIRouter()

def _not_impl():
    # ponytail: raising HTTPException avoids unhandled 500 server crashes
    raise HTTPException(status_code=501, detail="Funcionalidad de administracion de equipos no implementada.")

@router.get("/api/v1/team/list", tags=["Team"])
async def team_list():
    _not_impl()

@router.post("/api/v1/team/invite", tags=["Team"])
async def team_invite():
    _not_impl()

@router.patch("/api/v1/team/{member_id}", tags=["Team"])
async def team_update(member_id: str):
    _not_impl()

@router.patch("/api/v1/team/{member_id}/permissions", tags=["Team"])
async def team_update_permissions(member_id: str):
    _not_impl()

@router.post("/api/v1/team/{member_id}/deactivate", tags=["Team"])
async def team_deactivate(member_id: str):
    _not_impl()
