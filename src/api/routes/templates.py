"""
Templates API — Evangelista Intelligence Platform
Endpoints para gestionar y generar plantillas de documentos pre-llenadas.
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
from pathlib import Path
import json
import io
import os
import datetime

router = APIRouter(prefix="/api/templates", tags=["templates"])

# ── Catálogo de plantillas ─────────────────────────────────────────────────

TEMPLATES_CATALOG = [
    # Foundation
    {
        "id": "TPL-F-001",
        "name": "Propuesta Foundation",
        "family": "foundation",
        "description": "Propuesta comercial del servicio Foundation para presentar al prospecto antes de Cita 2.",
        "formats": ["pdf", "docx"],
        "variables": ["cliente_nombre", "cliente_sector", "precio_foundation", "fecha_propuesta", "consultor_nombre"],
        "phase": "Antes de Cita 2",
        "source_file": "Propuesta_Foundation.docx",
    },
    {
        "id": "TPL-F-002",
        "name": "Contrato Foundation",
        "family": "foundation",
        "description": "Contrato oficial del servicio Foundation. Se firma al inicio de la Cita 2.",
        "formats": ["pdf", "docx"],
        "variables": ["cliente_nombre", "cliente_rfc", "representante_legal", "precio_foundation", "fecha_contrato", "lugar_firma"],
        "phase": "Inicio Cita 2",
        "source_file": "Contrato_Foundation.docx",
    },
    {
        "id": "TPL-F-003",
        "name": "NDA — Acuerdo de Confidencialidad",
        "family": "foundation",
        "description": "Acuerdo de confidencialidad bilateral. Prerequisito antes de revelar la metodología MEC.",
        "formats": ["pdf", "docx"],
        "variables": ["cliente_nombre", "cliente_rfc", "representante_legal", "fecha_nda"],
        "phase": "Inicio Cita 2",
        "source_file": "Contrato_Foundation.docx",
    },
    {
        "id": "TPL-F-004",
        "name": "Expediente Operativo Foundation",
        "family": "foundation",
        "description": "Documento de trabajo interno que registra el alcance, credenciales y notas del análisis.",
        "formats": ["docx"],
        "variables": ["cliente_nombre", "cliente_erp", "consultor_nombre", "fecha_inicio", "alcance_acordado"],
        "phase": "Cuadrante 1 CRH",
        "source_file": "Expediente_Operativo_Foundation.docx",
    },
    {
        "id": "TPL-F-006",
        "name": "Certificado de Integridad ALCOA+",
        "family": "foundation",
        "description": "Certificado firmado por el CQA que valida que el Dictamen cumple el estándar ALCOA+. Requerido por Regla G-05.",
        "formats": ["pdf"],
        "variables": ["consultor_nombre", "cqa_nombre", "fecha_certificado", "num_dictamen"],
        "phase": "Pre-Cita 3",
        "source_file": None,
    },
    {
        "id": "TPL-F-007",
        "name": "Factura / Orden de Servicio Foundation",
        "family": "foundation",
        "description": "Orden de servicio oficial para el servicio Foundation.",
        "formats": ["pdf"],
        "variables": ["cliente_nombre", "cliente_rfc", "monto_foundation", "fecha_factura", "num_orden"],
        "phase": "Post-pago",
        "source_file": "Factura_Orden_Servicio.docx",
    },
    # Architecture
    {
        "id": "TPL-A-001",
        "name": "Propuesta Architecture",
        "family": "architecture",
        "description": "Propuesta comercial del servicio Architecture para presentar en Cita 4.",
        "formats": ["pdf", "docx"],
        "variables": ["cliente_nombre", "precio_architecture", "num_tramos", "duracion_semanas", "fecha_propuesta"],
        "phase": "Antes de Cita 4",
        "source_file": "Propuesta_Architecture.docx",
    },
    {
        "id": "TPL-A-002",
        "name": "Contrato Architecture",
        "family": "architecture",
        "description": "Contrato oficial del servicio Architecture con estructura de Tramos y pagos escalonados.",
        "formats": ["pdf", "docx"],
        "variables": ["cliente_nombre", "cliente_rfc", "representante_legal", "precio_tramo_a", "precio_tramo_b", "precio_tramo_c", "fecha_inicio"],
        "phase": "Inicio de proyecto",
        "source_file": "Contrato_Architecture.docx",
    },
    {
        "id": "TPL-A-004",
        "name": "Acta de Entrega de Tramo",
        "family": "architecture",
        "description": "Acta de conformidad que firma el cliente al recibir cada Tramo de Architecture.",
        "formats": ["pdf"],
        "variables": ["cliente_nombre", "num_tramo", "entregables_tramo", "fecha_entrega"],
        "phase": "Final de cada Tramo",
        "source_file": None,
    },
    # Comercial
    {
        "id": "TPL-C-002",
        "name": "Reporte de Vetting Gate",
        "family": "commercial",
        "description": "Documento interno de decisión Go/No-Go tras Foundation. Contiene factores α/β/Γ y justificación.",
        "formats": ["pdf"],
        "variables": ["cliente_nombre", "factor_alpha", "factor_beta", "factor_gamma", "decision_go_nogo", "justificacion"],
        "phase": "Post Cita 3",
        "source_file": None,
    },
]

# ── Modelos ────────────────────────────────────────────────────────────────

class TemplateGenerateRequest(BaseModel):
    variables: Dict[str, Any]
    format: str = "pdf"  # "pdf" | "docx"


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/")
async def list_templates(family: Optional[str] = None):
    """Lista todas las plantillas disponibles, con filtro opcional por familia."""
    catalog = TEMPLATES_CATALOG
    if family:
        catalog = [t for t in catalog if t["family"] == family]
    return {
        "total": len(catalog),
        "families": ["foundation", "architecture", "commercial"],
        "templates": catalog,
    }


@router.get("/{template_id}")
async def get_template(template_id: str):
    """Retorna la metadata de una plantilla específica."""
    template = next((t for t in TEMPLATES_CATALOG if t["id"] == template_id), None)
    if not template:
        raise HTTPException(status_code=404, detail=f"Plantilla '{template_id}' no encontrada")
    return template


@router.post("/{template_id}/generate")
async def generate_template(template_id: str, request: TemplateGenerateRequest):
    """
    Genera un documento a partir de una plantilla con variables pre-llenadas.
    Retorna el documento como descarga directa.
    
    En la implementación actual devuelve un JSON-preview.
    Para producción, usar python-docx + reportlab para generar PDF/DOCX real.
    """
    template = next((t for t in TEMPLATES_CATALOG if t["id"] == template_id), None)
    if not template:
        raise HTTPException(status_code=404, detail=f"Plantilla '{template_id}' no encontrada")

    if request.format not in template["formats"]:
        raise HTTPException(
            status_code=400,
            detail=f"Formato '{request.format}' no disponible para esta plantilla. Formatos disponibles: {template['formats']}"
        )

    # Validar variables requeridas
    missing = [v for v in template["variables"] if v not in request.variables]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Variables faltantes: {missing}. Se requieren: {template['variables']}"
        )

    # Agregar variables globales automáticas
    auto_vars = {
        "fecha_hoy": datetime.date.today().strftime("%d/%m/%Y"),
        "num_expediente": f"EVA-{datetime.date.today().strftime('%Y%m')}-{template_id}",
        "ceo_nombre": "Evangelista & Co. — Dirección General",
    }
    merged_vars = {**auto_vars, **request.variables}

    # Intentar generar desde archivo fuente si existe
    source_file = template.get("source_file")
    vault_templates_path = Path(__file__).parents[4] / "Evangelista-info" / "Interno" / "Sistema de transformacion de valor" / "Desglose Operacional"
    
    # Para Foundation
    foundation_path = vault_templates_path / "Foundation"
    architecture_path = vault_templates_path / "Architecture"

    # Respuesta de preview (en producción retornaría el archivo real)
    return {
        "status": "preview",
        "template_id": template_id,
        "template_name": template["name"],
        "format": request.format,
        "variables_applied": merged_vars,
        "message": "El documento se generará al implementar el motor de exportación PDF/DOCX. Variables validadas correctamente.",
        "download_ready": False,
    }


@router.get("/source-files/list")
async def list_source_files():
    """Lista los archivos fuente disponibles en Evangelista-info."""
    source_dirs = [
        Path(__file__).parents[4] / "Evangelista-info" / "Interno" / "Sistema de transformacion de valor" / "Desglose Operacional" / "Foundation",
        Path(__file__).parents[4] / "Evangelista-info" / "Interno" / "Sistema de transformacion de valor" / "Desglose Operacional" / "Architecture",
        Path(__file__).parents[4] / "Evangelista-info" / "Interno" / "Modelo Financiero",
    ]
    
    files = []
    for directory in source_dirs:
        if directory.exists():
            for f in directory.iterdir():
                if f.suffix.lower() in [".pdf", ".docx", ".dotx", ".doc"]:
                    files.append({
                        "name": f.name,
                        "folder": directory.name,
                        "size_kb": round(f.stat().st_size / 1024, 1),
                        "type": f.suffix.lower().strip(".")
                    })
    
    return {"total": len(files), "files": files}
