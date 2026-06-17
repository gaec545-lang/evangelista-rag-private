import hashlib
import json
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .models import Client, Project, Hypothesis, Finding, Snapshot, CoiCalculo, Bitacora, Documento, Credencial, EvaConversacion, EvaMensaje, EvaMemoria

class BaseRepository:
    def __init__(self, session: AsyncSession, client_id: UUID):
        self.session = session
        self.client_id = client_id

    async def commit(self):
        await self.session.commit()

    async def rollback(self):
        await self.session.rollback()

    async def log_to_bitacora(self, action: str, entity: str, entity_id: str, user_id: str = None, details: dict = None):
        # Calculate hash for append-only log
        # Get previous hash
        stmt = select(Bitacora).where(Bitacora.client_id == self.client_id).order_by(Bitacora.created_at.desc()).limit(1)
        result = await self.session.execute(stmt)
        last_log = result.scalar_one_or_none()
        prev_hash = last_log.hash if last_log else None

        # Create string to hash
        data_to_hash = f"{self.client_id}{action}{entity}{entity_id}{json.dumps(details)}{prev_hash}"
        current_hash = hashlib.sha256(data_to_hash.encode()).hexdigest()

        log_entry = Bitacora(
            client_id=self.client_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            user_id=user_id,
            details=details,
            hash=current_hash,
            prev_hash=prev_hash
        )
        self.session.add(log_entry)
        await self.session.flush()

class ProjectRepository(BaseRepository):
    async def get_projects(self):
        stmt = select(Project).where(Project.client_id == self.client_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

class EvaConversacionRepository(BaseRepository):
    async def get_conversations(self):
        stmt = select(EvaConversacion).where(EvaConversacion.client_id == self.client_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create_conversation(self, title: str) -> EvaConversacion:
        conv = EvaConversacion(
            client_id=self.client_id,
            title=title
        )
        self.session.add(conv)
        await self.session.flush()
        return conv

class EvaMensajeRepository(BaseRepository):
    async def create_message(self, conversacion_id, role: str, content: str) -> EvaMensaje:
        msg = EvaMensaje(
            client_id=self.client_id,
            conversacion_id=conversacion_id,
            role=role,
            content=content
        )
        self.session.add(msg)
        await self.session.flush()
        return msg

class EvaMemoriaRepository(BaseRepository):
    async def get_memory(self, key: str):
        stmt = select(EvaMemoria).where(EvaMemoria.client_id == self.client_id, EvaMemoria.key == key)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def save_memory(self, key: str, value: dict) -> EvaMemoria:
        mem = EvaMemoria(
            client_id=self.client_id,
            key=key,
            value=value
        )
        self.session.add(mem)
        await self.session.flush()
        return mem
