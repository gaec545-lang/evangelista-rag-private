from pydantic import BaseModel, Field
from typing import Any, Optional
from uuid import UUID

class SnapshotCreate(BaseModel):
    client_id: UUID
    name: str = Field(..., min_length=1)
    data: dict[str, Any]

class CoiCalculoCreate(BaseModel):
    client_id: UUID
    parameters: dict[str, Any]
    results: dict[str, Any]

class BitacoraCreate(BaseModel):
    client_id: UUID
    action: str = Field(..., min_length=1)
    entity: str = Field(..., min_length=1)
    entity_id: str = Field(..., min_length=1)
    details: Optional[dict[str, Any]] = None

class DocumentoCreate(BaseModel):
    client_id: UUID
    project_id: Optional[UUID] = None
    name: str = Field(..., min_length=1)
    path: str = Field(..., min_length=1)

class CredencialCreate(BaseModel):
    client_id: UUID
    service_name: str = Field(..., min_length=1)
    encrypted_token: str = Field(..., min_length=1) # base64 or similar

class ExpedientePdfRequest(BaseModel):
    client_id: UUID
    project_id: Optional[UUID] = None
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
