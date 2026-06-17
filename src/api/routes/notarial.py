from fastapi import APIRouter, Depends, HTTPException
from typing import List, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.middleware.auth import verify_jwt
from src.db.database import get_db
from src.db.models import Snapshot, CoiCalculo, Bitacora, Documento, Credencial
from src.db.repositories import BaseRepository
from sqlalchemy import select
from src.api.schemas.notarial import SnapshotCreate, CoiCalculoCreate, BitacoraCreate, DocumentoCreate, CredencialCreate, ExpedientePdfRequest

router = APIRouter(prefix="/api/v1/notarial", tags=["Notarial"])

# Ensure every endpoint depends on verify_jwt and correctly extracts user's oid and roles
@router.post("/snapshots")
async def create_snapshot(
    snapshot: SnapshotCreate,
    user: dict = Depends(verify_jwt),
    db: AsyncSession = Depends(get_db)
):
    repo = BaseRepository(db, snapshot.client_id)
    new_snapshot = Snapshot(client_id=snapshot.client_id, name=snapshot.name, data=snapshot.data)
    db.add(new_snapshot)
    await db.commit()
    await repo.log_to_bitacora("CREATE_SNAPSHOT", "Snapshot", str(new_snapshot.id), user.get("oid"))
    return {"status": "ok", "id": new_snapshot.id}

@router.post("/coi_calculos")
async def create_coi_calculo(
    coi: CoiCalculoCreate,
    user: dict = Depends(verify_jwt),
    db: AsyncSession = Depends(get_db)
):
    repo = BaseRepository(db, coi.client_id)
    new_coi = CoiCalculo(client_id=coi.client_id, parameters=coi.parameters, results=coi.results)
    db.add(new_coi)
    await db.commit()
    await repo.log_to_bitacora("CREATE_COI_CALCULO", "CoiCalculo", str(new_coi.id), user.get("oid"))
    return {"status": "ok", "id": new_coi.id}

@router.post("/bitacora")
async def create_bitacora(
    bitacora: BitacoraCreate,
    user: dict = Depends(verify_jwt),
    db: AsyncSession = Depends(get_db)
):
    repo = BaseRepository(db, bitacora.client_id)
    await repo.log_to_bitacora(bitacora.action, bitacora.entity, bitacora.entity_id, user.get("oid"), bitacora.details)
    await db.commit()
    return {"status": "ok"}

@router.post("/documentos")
async def create_documento(
    documento: DocumentoCreate,
    user: dict = Depends(verify_jwt),
    db: AsyncSession = Depends(get_db)
):
    repo = BaseRepository(db, documento.client_id)
    new_doc = Documento(client_id=documento.client_id, project_id=documento.project_id, name=documento.name, path=documento.path)
    db.add(new_doc)
    await db.commit()
    await repo.log_to_bitacora("CREATE_DOCUMENTO", "Documento", str(new_doc.id), user.get("oid"))
    return {"status": "ok", "id": new_doc.id}

@router.post("/credenciales")
async def create_credencial(
    cred: CredencialCreate,
    user: dict = Depends(verify_jwt),
    db: AsyncSession = Depends(get_db)
):
    repo = BaseRepository(db, cred.client_id)
    # Using encode to store string as bytes, in a real scenario encrypt properly with pgcrypto
    new_cred = Credencial(client_id=cred.client_id, service_name=cred.service_name, encrypted_token=cred.encrypted_token.encode())
    db.add(new_cred)
    await db.commit()
    await repo.log_to_bitacora("CREATE_CREDENCIAL", "Credencial", str(new_cred.id), user.get("oid"))
    return {"status": "ok", "id": new_cred.id}

@router.post("/expediente/pdf")
async def generate_expediente_pdf(
    req: ExpedientePdfRequest,
    user: dict = Depends(verify_jwt),
    db: AsyncSession = Depends(get_db)
):
    # Endpoint for PDF generation of the expediente
    repo = BaseRepository(db, req.client_id)
    
    # PDF generation logic mock
    import uuid
    pdf_id = uuid.uuid4()
    pdf_path = f"/azure/blob/storage/expedientes/{req.client_id}_{pdf_id}.pdf"
    
    await repo.log_to_bitacora("GENERATE_EXPEDIENTE_PDF", "Expediente", str(pdf_id), user.get("oid"), {"title": req.title})
    await db.commit()
    
    return {"status": "ok", "pdf_url": pdf_path, "pdf_id": str(pdf_id)}

