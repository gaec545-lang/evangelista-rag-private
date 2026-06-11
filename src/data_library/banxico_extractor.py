import os
from datetime import datetime, timedelta
import requests
from .base_extractor import BaseExtractor

class BanxicoExtractor(BaseExtractor):
    def __init__(self, token_env_var="BANXICO_TOKEN", env_path=r"e:\Evangelista & Co\Evangelista Intelligence Platform\Evangelista-Obsidian\evangelista-vault\.env"):
        super().__init__(token_env_var, env_path)
        # Endpoint de Banxico para series de tiempo (rango de fechas)
        self.base_url = "https://www.banxico.org.mx/SieAPIRest/series/{series}/datos/{fecha_inicio}/{fecha_fin}"
        
        # Series a extraer: TIIE 28, CETES 28, INPC, FIX
        self.series_map = {
            "TIIE_28": "SF43783",
            "CETES_28": "SF43936",
            "INFLACION": "SP1", # SP1 es el INPC, a veces se usa SP68257
            "FIX": "SF43718"
        }
        
    def extract(self):
        if not self.token:
            raise ValueError("Token de Banxico no encontrado. Verifica tu archivo .env.")
            
        headers = {
            "Bmx-Token": self.token
        }
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=24*30) # approx 24 meses
        
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        
        # Unir todas las series para la consulta
        series_str = ",".join(self.series_map.values())
        url = self.base_url.format(series=series_str, fecha_inicio=start_str, fecha_fin=end_str)
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        return response.json()
