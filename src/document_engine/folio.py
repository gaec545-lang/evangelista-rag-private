from src.config import settings
from supabase import create_client
from pydantic import BaseModel

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

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
    """Generates an atomic folio for a document using the Supabase rpc."""
    # First, get client info - Using 'name' as it's the standard column in dim_clients
    response = supabase.table('clients').select('name, client_code').eq('id', client_id).execute()
    
    if not response.data:
        client_code = 'XXX'
    else:
        client_data = response.data[0]
        client_code = client_data.get('client_code')
        if not client_code:
            client_code = derive_client_code(client_data.get('name', ''))
    
    type_code = DOCUMENT_TYPE_CODES.get(doc_type, 'DOC')
    
    # Use RPC to generate atomic folio
    rpc_response = supabase.rpc(
        'generate_folio',
        {
            'p_client_id': client_id,
            'p_doc_type': type_code,
            'p_client_code': client_code
        }
    ).execute()
    
    return rpc_response.data
