import uuid
import structlog
from typing import Optional, List, Dict
from datetime import datetime, timezone

from src.db.database import AsyncSessionLocal
from src.db.repositories import EvaConversacionRepository, EvaMensajeRepository, EvaMemoriaRepository
from src.retrieval.hybrid_retriever import HybridRetriever
from src.retrieval.query_engine import get_qdrant_client
from src.llm.factory import get_llm_client

logger = structlog.get_logger(__name__)

class EvaAgent:
    """
    Agente Conversacional Principal (Evangeline).
    Integra persistencia directa a PostgreSQL (via SA-DB) y RAG Híbrido (via Qdrant).
    """

    def __init__(self, client_id: str, conversacion_id: Optional[str] = None):
        self.client_id = uuid.UUID(client_id)
        self.conversacion_id = uuid.UUID(conversacion_id) if conversacion_id else None
        
        # Inicializar retrieval
        # Dummy embedder para inyección, asumiendo que el HybridRetriever 
        # utilizará el embedder interno de Qdrant o un mock para este scaffolding.
        class DummyEmbedder:
            async def embed(self, text): return [0.0] * 1536
            async def embed_single(self, text): return [0.0] * 1536
            
        self.retriever = HybridRetriever(
            qdrant_client=get_qdrant_client(), 
            embedder=DummyEmbedder()
        )
        self.llm = get_llm_client()

    async def _ensure_conversation(self, conv_repo: EvaConversacionRepository) -> uuid.UUID:
        if self.conversacion_id:
            return self.conversacion_id
            
        # Crear nueva conversación
        conv = await conv_repo.create_conversation(title="Nueva Conversación")
        self.conversacion_id = conv.id
        return conv.id

    async def _save_message(self, conv_repo: EvaConversacionRepository, msg_repo: EvaMensajeRepository, role: str, content: str):
        conv_id = await self._ensure_conversation(conv_repo)
        await msg_repo.create_message(
            conversacion_id=conv_id,
            role=role,
            content=content
        )

    async def _save_memory(self, mem_repo: EvaMemoriaRepository, key: str, value: dict):
        # Insertar o actualizar memoria de corto/largo plazo
        await mem_repo.save_memory(
            key=key,
            value=value
        )

    async def chat(self, user_message: str) -> str:
        """
        Flujo principal de la interacción.
        """
        logger.info("eva_chat_start", client_id=str(self.client_id), message=user_message[:50])

        # ponytail: use AsyncSessionLocal context manager to guarantee session closure and prevent connection leaks
        async with AsyncSessionLocal() as session:
            conv_repo = EvaConversacionRepository(session, self.client_id)
            msg_repo = EvaMensajeRepository(session, self.client_id)
            mem_repo = EvaMemoriaRepository(session, self.client_id)

            try:
                # 1. Guardar mensaje del usuario
                await self._save_message(conv_repo, msg_repo, role="user", content=user_message)

                # 2. Recuperar contexto vía Qdrant Híbrido (Denso + Disperso)
                # 'evangeline' is the agent_name filter
                chunks = await self.retriever.retrieve(
                    query=user_message,
                    agent_name="evangeline",
                    client_id=str(self.client_id),
                    top_k=5
                )
                
                context_str = "\n\n".join([f"- {c.text}" for c in chunks])
                
                # 3. Prompting & LLM
                system_prompt = (
                    "Eres Evangeline, la IA Estratégica de Evangelista & Co.\n"
                    "Responde con base en el siguiente contexto extraído del conocimiento institucional:\n"
                    f"{context_str}"
                )
                
                # Llamada al LLM
                response_content = await self.llm.generate(
                    prompt=user_message,
                    system_prompt=system_prompt,
                    temperature=0.4
                )
                
                # 4. Extraer posibles insights para memoria (Stub)
                # En producción, esto se extraería con un prompt secundario o function calling
                insight_key = f"insight_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
                await self._save_memory(mem_repo, key=insight_key, value={"topic": "extracted_from_chat", "query": user_message})

                # 5. Guardar respuesta del asistente
                await self._save_message(conv_repo, msg_repo, role="assistant", content=response_content)
                
                await session.commit()
                return response_content

            except Exception as e:
                await session.rollback()
                logger.error("eva_chat_failed", error=str(e))
                raise e
