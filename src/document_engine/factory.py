import subprocess, tempfile, os, json
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
from src.document_engine.folio import generate_folio_atomic
from src.config import settings
from sqlalchemy import text

router = APIRouter()

TEMPLATE_MAP = {
    'propuesta':              'propuesta.js',
    'nda':                    'nda.js',
    'contrato':               'contrato.js',
    'orden_servicio':         'orden_servicio.js',
    'dictamen':               'dictamen.js',
    'reporte_avance':         'reporte_avance.js',
    'reporte_parcial':        'reporte_avance.js',    # mismo template, variables distintas
    'reporte_final':          'reporte_final.js',
    'acta_entrega':           'acta_entrega.js',
    'expediente_operativo':   'expediente_operativo.js',
    'orden_servicio_interna': 'orden_servicio_interna.js',
    'lecciones_aprendidas':   'lecciones_aprendidas.js',
}

ACCENT_COLORS = {
    'propuesta':              '#c05538',
    'dictamen':               '#c05538',
    'nda':                    '#534ab7',
    'contrato':               '#534ab7',
    'orden_servicio':         '#534ab7',
    'reporte_avance':         '#4a5c3a',
    'reporte_parcial':        '#4a5c3a',
    'reporte_final':          '#0f6e56',
    'acta_entrega':           '#0f6e56',
    'expediente_operativo':   '#1a1a1a',
    'orden_servicio_interna': '#1a1a1a',
    'lecciones_aprendidas':   '#1a1a1a',
}

class DocumentGeneratePayload(BaseModel):
    doc_type: str
    client_id: str
    project_id: Optional[str] = None
    client_facing: bool = True
    output_format: str = 'docx'
    variables: Dict[str, Any] = {}

async def register_deliverable(project_id: str, client_id: str, doc_type: str, folio: str, file_path: str, client_facing: bool):
    """Register the deliverable in the database (Azure SQL / PostgreSQL)"""
    if not project_id:
        return
    
    file_name = os.path.basename(file_path)
    file_url = f"local://{file_path}"
    title = f"{doc_type.capitalize()} - {folio}"
    
    from src.tools.database_connector import SessionLocal
    if SessionLocal is None:
        print("Database session not configured, skipping deliverable registration.")
        return
        
    db = SessionLocal()
    try:
        # Try Azure SQL schema first
        query = text("""
            INSERT INTO Deliverables (ProjectId, DeliverableType, Title, Status, FileName, FileUrl)
            VALUES (:project_id, :doc_type, :title, 'borrador', :file_name, :file_url)
        """)
        db.execute(query, {
            "project_id": project_id,
            "doc_type": doc_type,
            "title": title,
            "file_name": file_name,
            "file_url": file_url
        })
        db.commit()
        print(f"Registered deliverable in Azure SQL: {folio}")
    except Exception as e:
        db.rollback()
        try:
            # Try PostgreSQL schema
            query = text("""
                INSERT INTO deliverables (project_id, deliverable_type, title, status, file_name, file_url, version)
                VALUES (:project_id, :doc_type, :title, 'borrador', :file_name, :file_url, 1)
            """)
            db.execute(query, {
                "project_id": project_id,
                "doc_type": doc_type,
                "title": title,
                "file_name": file_name,
                "file_url": file_url
            })
            db.commit()
            print(f"Registered deliverable in PostgreSQL: {folio}")
        except Exception as ex:
            db.rollback()
            print(f"Failed to register deliverable in both database systems: {e} | {ex}")
    finally:
        db.close()

@router.post("/generate")
async def generate_document(payload: DocumentGeneratePayload):
    """Generates a document."""
    if payload.doc_type not in TEMPLATE_MAP:
        raise HTTPException(status_code=400, detail=f"Tipo de documento no soportado: {payload.doc_type}")

    # Generate atomic folio
    try:
        folio = await generate_folio_atomic(payload.client_id, payload.doc_type)
    except Exception as e:
        print(f"Error generating folio: {e}")
        # Fallback if DB function fails
        folio = f"EVA-XXX-{payload.doc_type.upper()}-26-000"

    node_payload = {
        **payload.variables,
        'folio': folio,
        'accentColor': ACCENT_COLORS.get(payload.doc_type, '#c05538'),
        'isInternal': not payload.client_facing,
        'templateName': TEMPLATE_MAP[payload.doc_type],
        'outputFormat': payload.output_format,
    }

    suffix = '.docx' if node_payload['outputFormat'] == 'docx' else '.pdf'
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.docx', dir='/tmp') as tmp:
        output_path = tmp.name

    node_script = os.path.join(
        os.path.dirname(__file__),
        'templates',
        TEMPLATE_MAP[payload.doc_type]
    )
    
    if not os.path.exists(node_script):
        raise HTTPException(status_code=500, detail=f"Node template not implemented yet: {TEMPLATE_MAP[payload.doc_type]}")

    result = subprocess.run(
        ['node', node_script, json.dumps(node_payload), output_path],
        capture_output=True, text=True, timeout=30
    )

    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=f"Error generando documento: {result.stderr}")

    final_output_path = output_path
    
    if node_payload['outputFormat'] == 'pdf':
        pdf_path = output_path.replace('.docx', '.pdf')
        soffice_result = subprocess.run([
            'soffice', '--headless', '--convert-to', 'pdf', output_path,
            '--outdir', '/tmp'
        ], capture_output=True, text=True, timeout=30)
        
        if soffice_result.returncode == 0 and os.path.exists(pdf_path):
            final_output_path = pdf_path
        else:
            print(f"Warning: soffice failed. Falling back to docx. {soffice_result.stderr}")

    await register_deliverable(
        project_id=payload.project_id,
        client_id=payload.client_id,
        doc_type=payload.doc_type,
        folio=folio,
        file_path=final_output_path,
        client_facing=payload.client_facing,
    )

    filename = f"{folio}{'.pdf' if final_output_path.endswith('.pdf') else '.docx'}"
    mime = (
        'application/pdf' if final_output_path.endswith('.pdf')
        else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )

    return FileResponse(
        path=final_output_path, 
        media_type=mime, 
        filename=filename,
        headers={"x-document-folio": folio}
    )
