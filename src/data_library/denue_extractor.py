import os
import requests
import logging
from collections import Counter
from src.data_library.base_extractor import BaseExtractor
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class DenueExtractor(BaseExtractor):
    def __init__(self, token_env_var='INEGI_TOKEN', env_path=None):
        super().__init__(token_env_var=token_env_var, env_path=env_path)
        self.base_url = "https://www.inegi.org.mx/app/api/denue/v1/consulta"
        if not self.token:
            logger.warning(f"No token found in env var: {token_env_var}")

    def extract(self, condition, lat, lon, meters=1000):
        """
        Extrae datos de la API DENUE de INEGI.
        condition: palabra clave, sector o 'todos'
        lat, lon: coordenadas de la zona
        meters: radio en metros (max 5000)
        """
        if not self.token:
            raise ValueError("Token INEGI_TOKEN is required for DENUE Extractor")

        endpoint = f"{self.base_url}/Buscar/{condition}/{lat},{lon}/{meters}/{self.token}"
        logger.info(f"Querying DENUE API: {endpoint.replace(self.token, '***')}")
        
        response = requests.get(endpoint)
        response.raise_for_status()
        
        data = response.json()
        
        # Procesamiento: agregando conteos de tamaño
        size_counts = Counter()
        processed_data = []
        for item in data:
            # item.get('Estrato') gives size like '0 a 5 personas'
            size_counts[item.get('Estrato', 'Desconocido')] += 1
            processed_data.append(item)
            
        logger.info(f"Extracted {len(processed_data)} records. Size counts: {dict(size_counts)}")
        return {
            "total_records": len(processed_data),
            "size_counts": dict(size_counts),
            "data": processed_data
        }
    
    def extract_paginated(self, condition, zones, meters=1000):
        """
        Extrae datos para múltiples zonas (paginación por zonas/sectores).
        zones: lista de diccionarios con 'lat' y 'lon'.
        """
        all_results = []
        aggregated_size_counts = Counter()
        
        for zone in zones:
            lat = zone.get("lat")
            lon = zone.get("lon")
            res = self.extract(condition, lat, lon, meters)
            all_results.extend(res["data"])
            aggregated_size_counts.update(res["size_counts"])
            
        return {
            "total_records": len(all_results),
            "size_counts": dict(aggregated_size_counts),
            "data": all_results
        }
