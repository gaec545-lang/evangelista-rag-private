import os
from datetime import datetime, timedelta
import requests
from .base_extractor import BaseExtractor

class BanxicoExtractor(BaseExtractor):
    def __init__(self, token_env_var="BANXICO_TOKEN", env_path=r"e:\Evangelista & Co\Evangelista Intelligence Platform\Evangelista-Obsidian\evangelista-vault\.env"):
        super().__init__(token_env_var, env_path)
        # Endpoint de Banxico para el último dato oportuno de la serie
        self.base_url = "https://www.banxico.org.mx/SieAPIRest/service/v1/series/{series}/datos/oportuno"
        
        # Series a extraer: TIIE 28, CETES 28, INPC, FIX
        self.series_map = {
            "TIIE_28": "SF43783",
            "CETES_28": "SF43936",
            "INFLACION": "SP68257", # SP1 es el INPC, a veces se usa SP68257
            "FIX": "SF43718"
        }
        
    def extract(self):
        if not self.token:
            raise ValueError("Token de Banxico no encontrado. Verifica tu archivo .env.")
            
        headers = {
            "Bmx-Token": self.token
        }
        
        resultados = {"bmx": {"series": []}}
        for nombre, id_serie in self.series_map.items():
            url = self.base_url.format(series=id_serie)
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                if 'bmx' in data and 'series' in data['bmx']:
                    resultados["bmx"]["series"].extend(data["bmx"]["series"])
            except requests.exceptions.HTTPError as e:
                if response.status_code == 404:
                    print(f"Serie {nombre} ({id_serie}) no encontrada (404).")
                else:
                    print(f"Error HTTP al consultar serie {nombre}: {e}")
            except Exception as e:
                print(f"Error al consultar serie {nombre}: {e}")
                
        return resultados
