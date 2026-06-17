from pydantic import BaseModel
from typing import Any, Optional
from datetime import datetime
from uuid import UUID

class SnapshotCreate(BaseModel):
    client_id: UUID
    name: str
    data: dict[str, Any]

class CoiCalculoCreate(BaseModel):
    client_id: UUID
    parameters: dict[str, Any]
    results: dict[str, Any]

class BitacoraCreate(BaseModel):
    client_id: UUID
    action: str
    entity: str
    entity_id: str
    details: Optional[dict[str, Any]] = None

class DocumentoCreate(BaseModel):
    client_id: UUID
    project_id: Optional[UUID] = None
    name: str
    path: str

class CredencialCreate(BaseModel):
    client_id: UUID
    service_name: str
    encrypted_token: str # base64 or similar

class ExpedientePdfRequest(BaseModel):
    client_id: UUID
    project_id: Optional[UUID] = None
    title: str
    content: str
