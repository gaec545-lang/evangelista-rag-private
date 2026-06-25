from src.config import settings
import datetime
from sqlalchemy import text
from src.tools.database_connector import SessionLocal
from pydantic import BaseModel

DOCUMENT_TYPE_CODES = {
    'propuesta': 'P',
    'nda': 'N',
    'contrato': 'C',
    'orden_servicio': 'OS',
    'dictamen': 'D',
    'reporte_avance': 'RA',
    'reporte_parcial': 'RP',
    'reporte_final': 'RF',
    'acta_entrega': 'AE',
    'manual_usuario': 'MU',
    'expediente_operativo': 'EXP',
    'orden_servicio_interna': 'OSI',
    'lecciones_aprendidas': 'LA'
}

def derive_client_code(company_name: str) -> str:
    """Fallback if client_code is not present in DB."""
    import re
    if not company_name:
        return 'XXX'
    
    cleaned = re.sub(r'\b(S\.A\.|DE\s+C\.V\.|S\.A\.\s+DE\s+C\.V\.|S\.R\.L\.|SA|DE|CV|LA|EL|LOS|LAS|Y|&)\b', '', company_name, flags=re.IGNORECASE).strip()
    words = [w for w in re.split(r'\s+', cleaned) if w]
    
    if len(words) == 1:
        return words[0][:3].ljust(3, 'X').upper()
    if len(words) == 2:
        return (words[0][:2] + words[1][:1]).upper()
    if len(words) >= 3:
        return ''.join([w[0] for w in words[:3]]).upper()
    return 'XXX'

async def generate_folio_atomic(client_id: str, doc_type: str) -> str:
    """Generates an atomic folio for a document using the database."""
    # ponytail: reuse the same db session to avoid connection leaks/double connection overhead
    client_code = 'XXX'
    sequence = 1
    
    if SessionLocal is None:
        print("Database not configured, using fallback client code.")
    else:
        db = SessionLocal()
        try:
            # 1. Query client table with fallback for casing & column names
            row = None
            try:
                # Try case-insensitive fields in lowercase
                res = db.execute(
                    text("SELECT name, client_code FROM clients WHERE id = :client_id"),
                    {"client_id": client_id}
                ).first()
                if res:
                    row = dict(res._mapping)
            except Exception:
                try:
                    # Try uppercase Client table & column names for Azure SQL
                    res = db.execute(
                        text("SELECT Name FROM Clients WHERE Id = :client_id"),
                        {"client_id": client_id}
                    ).first()
                    if res:
                        row = dict(res._mapping)
                except Exception as e:
                    print(f"Failed to fetch client: {e}")
            
            if row:
                name = row.get('name') or row.get('Name') or ''
                client_code = row.get('client_code')
                if not client_code and name:
                    client_code = derive_client_code(name)
                    
            # 2. Calculate sequence
            try:
                # Azure SQL casing
                query = text("""
                    SELECT COUNT(*) 
                    FROM Deliverables d
                    JOIN Projects p ON d.ProjectId = p.Id
                    WHERE p.ClientId = :client_id AND d.DeliverableType = :doc_type
                """)
                sequence = db.execute(query, {"client_id": client_id, "doc_type": doc_type}).scalar() + 1
            except Exception:
                try:
                    # PostgreSQL casing
                    query = text("""
                        SELECT COUNT(*) 
                        FROM deliverables d
                        JOIN projects p ON d.project_id = p.id
                        WHERE p.client_id = :client_id AND d.deliverable_type = :doc_type
                    """)
                    sequence = db.execute(query, {"client_id": client_id, "doc_type": doc_type}).scalar() + 1
                except Exception as e:
                    print(f"Error calculating sequence, falling back to 1: {e}")
                    sequence = 1
        except Exception as e:
            print(f"Error in generate_folio_atomic: {e}")
        finally:
            db.close()

    if not client_code:
        client_code = 'XXX'
    
    type_code = DOCUMENT_TYPE_CODES.get(doc_type, 'DOC')
    year_suffix = datetime.datetime.now().strftime("%y") # e.g. "26"
    return f"EVA-{client_code}-{type_code}-{year_suffix}-{sequence:03d}"
