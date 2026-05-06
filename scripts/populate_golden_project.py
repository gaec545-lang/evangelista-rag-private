import os
import uuid
import datetime
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(url, key)

def populate():
    # 1. Crear Cliente Elite
    client_id = str(uuid.uuid4())
    supabase.table("clients").insert({
        "id": client_id,
        "name": "Bayer Global Operations",
        "sector": "Farmacéutico",
        "city": "Leverkusen",
        "sucursales": 140,
        "status": "active",
        "factor_gamma": 0.92,
        "factor_alpha": 0.88
    }).execute()

    # 2. Crear Proyecto Golden
    project_id = str(uuid.uuid4())
    supabase.table("projects").insert({
        "id": project_id,
        "client_id": client_id,
        "name": "Optimización de Hemofilia Operativa en Logística",
        "area": "supply_chain",
        "status": "entrega",
        "total_price": 125000.00,
        "current_phase": "delivery"
    }).execute()

    # 3. Crear Fases
    phases = [
        ("scoping", "completada"),
        ("immersion", "completada"),
        ("analysis", "completada"),
        ("delivery", "en_curso"),
        ("closure", "pendiente")
    ]
    for idx, (name, status) in enumerate(phases):
        supabase.table("project_phases").insert({
            "project_id": project_id,
            "phase_name": name,
            "status": status,
            "phase_order": idx + 1
        }).execute()

    # 4. Crear Hipótesis
    hypotheses = [
        ("Fuga de margen en fletes de última milla", "validada", 0.85),
        ("Inconsistencia en inventario cíclico por merma administrativa", "validada", 0.92),
        ("Duplicidad de protocolos en recepción de aduanas", "refutada", 0.15)
    ]
    for title, status, prob in hypotheses:
        supabase.table("hypotheses").insert({
            "project_id": project_id,
            "statement": title,
            "status": status,
            "priority": 1
        }).execute()

    # 5. Crear Hallazgos
    findings = [
        ("Sobrecosto logístico por rutas no optimizadas", "validado", 450000),
        ("Merma administrativa en CEDIS Norte", "identificado", 120000)
    ]
    for idx, (title, status, impact) in enumerate(findings):
        supabase.table("findings").insert({
            "project_id": project_id,
            "title": title,
            "status": status,
            "economic_impact": impact,
            "folio": f"H-{idx+1:02d}",
            "description": f"Descripción ejecutiva de {title}",
            "severity": "critico"
        }).execute()

    # 6. Crear Pagos
    supabase.table("project_payments").insert({
        "project_id": project_id,
        "payment_type": "anticipo",
        "amount": 62500.00,
        "received": True,
        "due_date": str(datetime.date.today()),
        "description": "Anticipo 50% — Proyecto Golden"
    }).execute()

    # 7. Crear Cierre
    supabase.table("project_closure").insert({
        "project_id": project_id,
        "status": "en_proceso",
        "deliverables_accepted": True,
        "credentials_revoked": False
    }).execute()

    print(f"Proyecto Golden creado: {project_id}")
    print(f"URL: http://localhost:5173/dashboard/projects/{project_id}")

if __name__ == "__main__":
    populate()
