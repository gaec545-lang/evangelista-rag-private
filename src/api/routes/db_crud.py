from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

from src.api.middleware.auth import verify_jwt
from src.db.database import get_db
from src.db.models import Client, Project, Finding, Hypothesis, ProjectPhase
from src.db.repositories import BaseRepository

router = APIRouter(prefix="/api/v1", tags=["DB CRUD"])

# --- Client Schemas ---
class ClientBase(BaseModel):
    name: str

class ClientCreate(ClientBase):
    pass

class ClientUpdate(BaseModel):
    name: Optional[str] = None

class ClientResponse(ClientBase):
    id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# --- Project Schemas ---
class ProjectBase(BaseModel):
    client_id: UUID
    name: str
    status: str = "active"
    current_phase: str = "Scoping"
    total_price: str = "0.00"

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(BaseModel):
    client_id: Optional[UUID] = None
    name: Optional[str] = None
    status: Optional[str] = None
    current_phase: Optional[str] = None
    total_price: Optional[str] = None

class ProjectResponse(ProjectBase):
    id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# --- Finding Schemas ---
class FindingBase(BaseModel):
    project_id: UUID
    title: str
    content: Optional[str] = None

class FindingCreate(FindingBase):
    pass

class FindingUpdate(BaseModel):
    project_id: Optional[UUID] = None
    title: Optional[str] = None
    content: Optional[str] = None

class FindingResponse(FindingBase):
    id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# --- Hypothesis Schemas ---
class HypothesisBase(BaseModel):
    project_id: UUID
    title: str
    content: Optional[str] = None

class HypothesisCreate(HypothesisBase):
    pass

class HypothesisUpdate(BaseModel):
    project_id: Optional[UUID] = None
    title: Optional[str] = None
    content: Optional[str] = None

class HypothesisResponse(HypothesisBase):
    id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# --- ProjectPhase Schemas ---
class ProjectPhaseBase(BaseModel):
    project_id: UUID
    phase_name: str
    name: Optional[str] = None
    phase_order: int = 0
    status: str = "pendiente"
    responsible: Optional[str] = None
    assigned_to_role: Optional[str] = None
    notes: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class ProjectPhaseCreate(ProjectPhaseBase):
    pass

class ProjectPhaseUpdate(BaseModel):
    project_id: Optional[UUID] = None
    phase_name: Optional[str] = None
    name: Optional[str] = None
    phase_order: Optional[int] = None
    status: Optional[str] = None
    responsible: Optional[str] = None
    assigned_to_role: Optional[str] = None
    notes: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class ProjectPhaseResponse(ProjectPhaseBase):
    id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ==========================================
# Client Endpoints
# ==========================================

@router.get("/clients", response_model=List[ClientResponse])
async def list_clients(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(verify_jwt)
):
    stmt = select(Client)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/clients/{id}", response_model=ClientResponse)
async def get_client(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(verify_jwt)
):
    stmt = select(Client).where(Client.id == id)
    result = await db.execute(stmt)
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client

@router.post("/clients", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    client_in: ClientCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(verify_jwt)
):
    client = Client(**client_in.model_dump())
    db.add(client)
    await db.commit()
    await db.refresh(client)
    repo = BaseRepository(db, client.id)
    await repo.log_to_bitacora("CREATE_CLIENT", "Client", str(client.id), user.get("oid"))
    return client

@router.put("/clients/{id}", response_model=ClientResponse)
async def update_client(
    id: UUID,
    client_in: ClientUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(verify_jwt)
):
    stmt = select(Client).where(Client.id == id)
    result = await db.execute(stmt)
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    update_data = client_in.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(client, field, val)
    
    await db.commit()
    await db.refresh(client)
    repo = BaseRepository(db, client.id)
    await repo.log_to_bitacora("UPDATE_CLIENT", "Client", str(client.id), user.get("oid"))
    return client

@router.delete("/clients/{id}")
async def delete_client(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(verify_jwt)
):
    stmt = select(Client).where(Client.id == id)
    result = await db.execute(stmt)
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    await db.delete(client)
    await db.commit()
    repo = BaseRepository(db, client.id)
    await repo.log_to_bitacora("DELETE_CLIENT", "Client", str(client.id), user.get("oid"))
    return {"status": "success", "message": "Client deleted"}


# ==========================================
# Project Endpoints
# ==========================================

@router.get("/projects", response_model=List[ProjectResponse])
async def list_projects(
    client_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(verify_jwt)
):
    stmt = select(Project)
    if client_id:
        stmt = stmt.where(Project.client_id == client_id)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/projects/{id}", response_model=ProjectResponse)
async def get_project(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(verify_jwt)
):
    stmt = select(Project).where(Project.id == id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_in: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(verify_jwt)
):
    project = Project(**project_in.model_dump())
    db.add(project)
    await db.commit()
    await db.refresh(project)
    repo = BaseRepository(db, project.client_id)
    await repo.log_to_bitacora("CREATE_PROJECT", "Project", str(project.id), user.get("oid"))
    return project

@router.put("/projects/{id}", response_model=ProjectResponse)
async def update_project(
    id: UUID,
    project_in: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(verify_jwt)
):
    stmt = select(Project).where(Project.id == id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    update_data = project_in.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(project, field, val)
    
    await db.commit()
    await db.refresh(project)
    repo = BaseRepository(db, project.client_id)
    await repo.log_to_bitacora("UPDATE_PROJECT", "Project", str(project.id), user.get("oid"))
    return project

@router.delete("/projects/{id}")
async def delete_project(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(verify_jwt)
):
    stmt = select(Project).where(Project.id == id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    client_id = project.client_id
    await db.delete(project)
    await db.commit()
    repo = BaseRepository(db, client_id)
    await repo.log_to_bitacora("DELETE_PROJECT", "Project", str(project.id), user.get("oid"))
    return {"status": "success", "message": "Project deleted"}


# ==========================================
# Finding Endpoints
# ==========================================

@router.get("/findings", response_model=List[FindingResponse])
async def list_findings(
    project_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(verify_jwt)
):
    stmt = select(Finding)
    if project_id:
        stmt = stmt.where(Finding.project_id == project_id)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/findings/{id}", response_model=FindingResponse)
async def get_finding(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(verify_jwt)
):
    stmt = select(Finding).where(Finding.id == id)
    result = await db.execute(stmt)
    finding = result.scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    return finding

@router.post("/findings", response_model=FindingResponse, status_code=status.HTTP_201_CREATED)
async def create_finding(
    finding_in: FindingCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(verify_jwt)
):
    finding = Finding(**finding_in.model_dump())
    db.add(finding)
    await db.commit()
    await db.refresh(finding)
    return finding

@router.put("/findings/{id}", response_model=FindingResponse)
async def update_finding(
    id: UUID,
    finding_in: FindingUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(verify_jwt)
):
    stmt = select(Finding).where(Finding.id == id)
    result = await db.execute(stmt)
    finding = result.scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    
    update_data = finding_in.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(finding, field, val)
    
    await db.commit()
    await db.refresh(finding)
    return finding

@router.delete("/findings/{id}")
async def delete_finding(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(verify_jwt)
):
    stmt = select(Finding).where(Finding.id == id)
    result = await db.execute(stmt)
    finding = result.scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    
    await db.delete(finding)
    await db.commit()
    return {"status": "success", "message": "Finding deleted"}


# ==========================================
# Hypothesis Endpoints
# ==========================================

@router.get("/hypotheses", response_model=List[HypothesisResponse])
async def list_hypotheses(
    project_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(verify_jwt)
):
    stmt = select(Hypothesis)
    if project_id:
        stmt = stmt.where(Hypothesis.project_id == project_id)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/hypotheses/{id}", response_model=HypothesisResponse)
async def get_hypothesis(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(verify_jwt)
):
    stmt = select(Hypothesis).where(Hypothesis.id == id)
    result = await db.execute(stmt)
    hypothesis = result.scalar_one_or_none()
    if not hypothesis:
        raise HTTPException(status_code=404, detail="Hypothesis not found")
    return hypothesis

@router.post("/hypotheses", response_model=HypothesisResponse, status_code=status.HTTP_201_CREATED)
async def create_hypothesis(
    hypothesis_in: HypothesisCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(verify_jwt)
):
    hypothesis = Hypothesis(**hypothesis_in.model_dump())
    db.add(hypothesis)
    await db.commit()
    await db.refresh(hypothesis)
    return hypothesis

@router.put("/hypotheses/{id}", response_model=HypothesisResponse)
async def update_hypothesis(
    id: UUID,
    hypothesis_in: HypothesisUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(verify_jwt)
):
    stmt = select(Hypothesis).where(Hypothesis.id == id)
    result = await db.execute(stmt)
    hypothesis = result.scalar_one_or_none()
    if not hypothesis:
        raise HTTPException(status_code=404, detail="Hypothesis not found")
    
    update_data = hypothesis_in.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(hypothesis, field, val)
    
    await db.commit()
    await db.refresh(hypothesis)
    return hypothesis

@router.delete("/hypotheses/{id}")
async def delete_hypothesis(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(verify_jwt)
):
    stmt = select(Hypothesis).where(Hypothesis.id == id)
    result = await db.execute(stmt)
    hypothesis = result.scalar_one_or_none()
    if not hypothesis:
        raise HTTPException(status_code=404, detail="Hypothesis not found")
    
    await db.delete(hypothesis)
    await db.commit()
    return {"status": "success", "message": "Hypothesis deleted"}


# ==========================================
# ProjectPhase (projects_phases) Endpoints
# ==========================================

@router.get("/projects_phases", response_model=List[ProjectPhaseResponse])
async def list_project_phases(
    project_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(verify_jwt)
):
    stmt = select(ProjectPhase)
    if project_id:
        stmt = stmt.where(ProjectPhase.project_id == project_id)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/projects_phases/{id}", response_model=ProjectPhaseResponse)
async def get_project_phase(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(verify_jwt)
):
    stmt = select(ProjectPhase).where(ProjectPhase.id == id)
    result = await db.execute(stmt)
    phase = result.scalar_one_or_none()
    if not phase:
        raise HTTPException(status_code=404, detail="Project phase not found")
    return phase

@router.post("/projects_phases", response_model=ProjectPhaseResponse, status_code=status.HTTP_201_CREATED)
async def create_project_phase(
    phase_in: ProjectPhaseCreate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(verify_jwt)
):
    phase = ProjectPhase(**phase_in.model_dump())
    db.add(phase)
    await db.commit()
    await db.refresh(phase)
    return phase

@router.put("/projects_phases/{id}", response_model=ProjectPhaseResponse)
async def update_project_phase(
    id: UUID,
    phase_in: ProjectPhaseUpdate,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(verify_jwt)
):
    stmt = select(ProjectPhase).where(ProjectPhase.id == id)
    result = await db.execute(stmt)
    phase = result.scalar_one_or_none()
    if not phase:
        raise HTTPException(status_code=404, detail="Project phase not found")
    
    update_data = phase_in.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(phase, field, val)
    
    await db.commit()
    await db.refresh(phase)
    return phase

@router.delete("/projects_phases/{id}")
async def delete_project_phase(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(verify_jwt)
):
    stmt = select(ProjectPhase).where(ProjectPhase.id == id)
    result = await db.execute(stmt)
    phase = result.scalar_one_or_none()
    if not phase:
        raise HTTPException(status_code=404, detail="Project phase not found")
    
    await db.delete(phase)
    await db.commit()
    return {"status": "success", "message": "Project phase deleted"}
