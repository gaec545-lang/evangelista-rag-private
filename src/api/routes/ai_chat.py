from fastapi import APIRouter, HTTPException, Request
from src.api.schemas.requests import ChatRequest, ChatResponse
from src.retrieval.query_engine import QueryEngine
from src.llm.factory import get_llm_client
from src.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, req: Request):
    logger.info("chat_request", agent=request.agent_name, query=request.message[:80])
    
    context_dict = None
    if request.project_context:
        context_dict = {
            "sector": request.project_context.sector,
            "project_phase": request.project_phase,
            "hypotheses_count": request.project_context.hypotheses_count,
            "findings_summary": request.project_context.findings_summary,
            "current_coi": request.project_context.current_coi
        }
    
    query_engine = QueryEngine()
    
    try:
        rag_result = await query_engine.retrieve_orchestrated(
            query=request.message,
            agent_name=request.agent_name,
            client_id=request.client_id,
            project_phase=request.project_phase,
            project_context=context_dict
        )
    except Exception as e:
        logger.error("rag_orchestration_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error in RAG pipeline: {str(e)}")
    
    if rag_result.status == "INSUFFICIENT_CONTEXT":
        return ChatResponse(
            message="""No encontré base metodológica suficiente en el vault para responder esto con certeza.\n\n¿Qué hacemos?\n1. ¿Escalamos al agente más adecuado?\n2. ¿Agrego una nota al proyecto para revisión posterior?""",
            agent_used=request.agent_name,
            rag_status="INSUFFICIENT_CONTEXT",
            avg_relevance=0.0
        )
    
    # Inyectar contexto según eva_mode
    system_prompt_extras = []
    
    if request.eva_mode == 'client' and request.client_context:
        system_prompt_extras.append(f"=== CONTEXTO DEL CLIENTE ===\n{request.client_context.model_dump_json(indent=2)}")
    elif request.eva_mode == 'project' and request.project_context_full:
        system_prompt_extras.append(f"=== CONTEXTO DEL PROYECTO (COMPLETO) ===\n{request.project_context_full.model_dump_json(indent=2)}")
        
    if request.tab_context:
        system_prompt_extras.append(f"=== CONTEXTO DEL TAB ACTUAL ===\n{request.tab_context.model_dump_json(indent=2)}")

    final_system_prompt = rag_result.system_prompt
    if system_prompt_extras:
        final_system_prompt += "\n\n" + "\n\n".join(system_prompt_extras)
        
    llm_client = get_llm_client()
    try:
        llm_response = await llm_client.generate(
            prompt=request.message,
            system_prompt=final_system_prompt
        )
    except Exception as e:
        logger.error("llm_generation_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error in LLM generation: {str(e)}")
    
    return ChatResponse(
        message=llm_response,
        agent_used=request.agent_name,
        rag_status=rag_result.status,
        avg_relevance=rag_result.avg_relevance,
        retriever_used=rag_result.retriever_used,
        hypothesis_used=rag_result.hypothesis_used
    )


@router.post("/internal/refresh-bm25")
async def refresh_bm25_index(request: Request):
    """
    Endpoint interno. Llamar después de re-indexar el Obsidian Vault en Qdrant.
    """
    if hasattr(request.app.state, "hybrid_retriever"):
        request.app.state.hybrid_retriever._bm25_index = None
        await request.app.state.hybrid_retriever._build_bm25_index()
        return {"status": "ok", "message": "BM25 index refreshed"}
    return {"status": "error", "message": "hybrid_retriever not initialized"}
