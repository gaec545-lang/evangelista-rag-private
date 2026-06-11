import os
import sys
import argparse
from datetime import datetime

# Añadir src al PYTHONPATH
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from data_library.emim_extractor import EMIMExtractor
from db.azure_logger import log_run

def parse_args():
    parser = argparse.ArgumentParser(description="Ejecutar el pipeline de EMIM")
    parser.add_argument("--dry-run", action="store_true", help="No escribir en DB ni en Vault")
    parser.add_argument("--months-back", type=int, default=24, help="Meses de histórico")
    return parser.parse_args()

def main():
    args = parse_args()
    dry_run = args.dry_run or os.environ.get("DATA_LIBRARY_DRY_RUN", "false").lower() == "true"
    
    print(f"[{datetime.now()}] Iniciando pipeline de EMIM (dry_run={dry_run})")
    
    extractor = EMIMExtractor()
    try:
        data = extractor.extract(months_back=args.months_back)
        derived = extractor.calculate_derived(data)
        
        vault_dir = os.path.join(os.path.dirname(__file__), "..", "..", "Evangelista-Obsidian", "evangelista-vault", "benchmarks", "emim")
        if not dry_run:
            os.makedirs(vault_dir, exist_ok=True)
            
        records = 0
        for nivel in ["nacional", "puebla"]:
            df = derived.get(nivel)
            if df is not None and not df.empty:
                latest_period = df.iloc[0]["period"]
                md_content = extractor.to_vault_document(data, derived, nivel, latest_period)
                
                filename = f"DAT-EMIM-{nivel}-{latest_period.replace('/', '-')}.md"
                filepath = os.path.join(vault_dir, filename)
                
                if dry_run:
                    print(f"[{datetime.now()}] DRY RUN: Escribiendo {filename} ({len(md_content)} bytes)")
                else:
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(md_content)
                    print(f"[{datetime.now()}] Creado documento {filename}")
                records += 1

        if not dry_run:
            log_run("emim", "success", records)
            print(f"[{datetime.now()}] Log de ejecución registrado en Azure SQL.")
        else:
            print(f"[{datetime.now()}] DRY RUN: Log de ejecución omitido.")
            
        # Opcional: Llamar a rank-bm25 refresh
        if not dry_run:
            try:
                import requests
                # Asumiendo puerto de backend = 8000
                res = requests.post("http://localhost:8000/internal/refresh-bm25")
                if res.status_code == 200:
                    print(f"[{datetime.now()}] Refresh BM25 exitoso.")
            except Exception as e:
                print(f"[{datetime.now()}] Aviso: No se pudo conectar al endpoint BM25 ({e})")
                
    except Exception as e:
        print(f"[{datetime.now()}] Error en pipeline de EMIM: {e}")
        if not dry_run:
            log_run("emim", "failed", 0, str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()
