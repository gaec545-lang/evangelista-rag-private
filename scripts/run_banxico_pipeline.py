import sys
import os

# Agrega la raíz del Backend al path para importaciones absolutas
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.data_library.banxico_extractor import BanxicoExtractor
from src.db.azure_logger import log_run

def main():
    print("Iniciando pipeline de Banxico...")
    extractor = BanxicoExtractor()
    
    try:
        data = extractor.extract()
        records_processed = 0
        
        # Validar y procesar la respuesta
        if 'bmx' in data and 'series' in data['bmx']:
            for s in data['bmx']['series']:
                records_processed += len(s.get('datos', []))
                
        print(f"Éxito: Se extrajeron {records_processed} registros de Banxico.")
        log_run("Banxico_Pipeline", "SUCCESS", records_processed)
        
    except Exception as e:
        print(f"Error en la ejecución del pipeline: {e}")
        log_run("Banxico_Pipeline", "FAILED", 0, str(e))

if __name__ == "__main__":
    main()
