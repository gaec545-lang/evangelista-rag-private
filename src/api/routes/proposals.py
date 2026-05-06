"""Routes de propuestas: Foundation y Architecture."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any
from src.utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


class FoundationRequest(BaseModel):
    name: str | None = None
    client_name: str | None = None  # Compatible con el frontend actual
    sector: str = "manufactura"
    sucursales: int = 1
    sistemas_erp: int = 1
    erp_type: str = "SAP"
    city: str = "Puebla"
    registros: int = 100000
    contact_name: str = ""
    beta: float = 0.3
    client_id: str | None = None
    tone: str = "profesional"  # profesional, agresivo, conservador, conciliador


class ArchitectureRequest(BaseModel):
    client_data: dict[str, Any]
    hallazgos: list[str] = []
    tone: str = "profesional"


class ProposalResponse(BaseModel):
    proposal: str
    type: str
    pricing: dict[str, Any] = {}


@router.post("/proposals/foundation", response_model=ProposalResponse)
async def generate_foundation(request: FoundationRequest):
    """Genera propuesta Foundation completa en Markdown."""
    client_name = request.name or request.client_name
    if not client_name:
        raise HTTPException(status_code=400, detail="Se requiere el nombre del cliente (name o client_name)")
    
    logger.info("proposal_foundation_request", client=client_name)
    try:
        from src.proposals.generator import ProposalGenerator
        gen = ProposalGenerator()
        markdown = await gen.generate_foundation(request.model_dump(), tone=request.tone)

        import math
        gamma = 1 + 0.5 * request.sucursales + 0.2 * request.sistemas_erp
        alpha = max(0.0, math.log10(max(request.registros, 1)) - 4)
        foundation_fee = 35000 * (1 + alpha + request.beta)
        if request.city.upper() not in ("PUEBLA", "PUE"):
            foundation_fee += 8000
        foundation_fee = round(foundation_fee, -2)

        return ProposalResponse(
            proposal=markdown,
            type="foundation",
            pricing={"foundation_fee": foundation_fee, "gamma": round(gamma, 2), "alpha": round(alpha, 2), "beta": request.beta},
        )
    except Exception as e:
        logger.error("proposal_foundation_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error generando propuesta: {str(e)}")


@router.post("/proposals/architecture", response_model=ProposalResponse)
async def generate_architecture(request: ArchitectureRequest):
    """Genera propuesta Architecture completa en Markdown."""
    client_data = request.client_data
    logger.info("proposal_architecture_request", client=client_data.get("name", "unknown"))
    try:
        from src.proposals.generator import ProposalGenerator
        gen = ProposalGenerator()
        markdown = await gen.generate_architecture(client_data, request.hallazgos, tone=request.tone)

        sucursales = int(client_data.get("sucursales", 1))
        erps = int(client_data.get("sistemas_erp", 1))
        gamma = 1 + 0.5 * sucursales + 0.2 * erps
        setup_fee = round(80000 * gamma, -2)
        success_fee = round(setup_fee * 0.25, -2)

        return ProposalResponse(
            proposal=markdown,
            type="architecture",
            pricing={"setup_fee": setup_fee, "success_fee": success_fee, "total": setup_fee + success_fee, "gamma": round(gamma, 2)},
        )
    except Exception as e:
        logger.error("proposal_architecture_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error generando propuesta: {str(e)}")
