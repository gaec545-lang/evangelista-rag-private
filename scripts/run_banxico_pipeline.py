import sys
import os
import datetime

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
        
        # Guardaremos el último dato de cada serie
        latest_data = {}
        
        # Mapeo inverso de ids a nombres
        id_to_name = {
            "SF43783": "TIIE_28",
            "SF43936": "CETES_28",
            "SP68257": "INFLACION",
            "SF43718": "FIX"
        }
        
        # Validar y procesar la respuesta
        if 'bmx' in data and 'series' in data['bmx']:
            for s in data['bmx']['series']:
                datos = s.get('datos', [])
                records_processed += len(datos)
                if datos:
                    # El último dato suele ser el más reciente
                    ultimo = datos[-1]
                    id_serie = s.get('idSerie')
                    nombre = id_to_name.get(id_serie, id_serie)
                    latest_data[nombre] = {
                        "fecha": ultimo.get("fecha", ""),
                        "valor": ultimo.get("dato", "")
                    }
                    
        print(f"Éxito: Se extrajeron {records_processed} registros de Banxico.")
        log_run("Banxico_Pipeline", "SUCCESS", records_processed)
        
        # Crear archivo Markdown
        hoy = datetime.datetime.now()
        fecha_str = hoy.strftime("%Y-%m-%d")
        
        vault_path = r"e:\Evangelista & Co\Evangelista Intelligence Platform\Evangelista-Obsidian\evangelista-vault"
        benchmarks_path = os.path.join(vault_path, "benchmarks", "banxico")
        os.makedirs(benchmarks_path, exist_ok=True)
        
        filename = f"DAT-BANXICO-{fecha_str}.md"
        filepath = os.path.join(benchmarks_path, filename)
        
        md_content = f"""---
id: DAT-BANXICO-{fecha_str}
tipo: benchmark_sectorial
subtipo: indicadores_macro
nivel_geografico: nacional
fecha_extraccion: {fecha_str}
---

## Indicadores Macro (Banxico)

| Indicador | Última Fecha | Valor |
| --- | --- | --- |
"""
        for ind in ["TIIE_28", "CETES_28", "INFLACION", "FIX"]:
            if ind in latest_data:
                md_content += f"| {ind} | {latest_data[ind]['fecha']} | {latest_data[ind]['valor']} |\n"
                
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md_content)
            
        print(f"Archivo Markdown guardado en: {filepath}")
        
    except Exception as e:
        print(f"Error en la ejecución del pipeline: {e}")
        log_run("Banxico_Pipeline", "FAILED", 0, str(e))

if __name__ == "__main__":
    main()
