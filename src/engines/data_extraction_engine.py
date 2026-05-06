import pandas as pd
import logging
from supabase import create_client, Client

class DataExtractionEngine:
    def __init__(self, supabase_creds: dict, config):
        """
        Recibe las credenciales ya desencriptadas por el Orquestador 
        y la configuración del cliente.
        """
        self.supabase_creds = supabase_creds
        self.config = config
        self.client_id = config.get('client.id')

    def extract_data(self, table_name: str) -> pd.DataFrame:
        logging.info(f"Iniciando extracción API (service_role) para cliente {self.client_id} | Tabla: {table_name}")
        try:
            # 1. Tomamos las llaves directamente de la memoria inyectada
            url = self.supabase_creds.get("url")
            key = self.supabase_creds.get("key")

            if not url or not key:
                raise ValueError("Las credenciales API inyectadas por el Orquestador están incompletas.")

            # 2. Forjamos el túnel HTTPS de alta velocidad
            supabase: Client = create_client(url, key)

            # 3. Extraemos los datos (Atravesando cualquier bloqueo de red)
            response = supabase.table(table_name).select("*").limit(50000).execute()
            
            data = response.data
            if not data:
                raise ValueError(f"La tabla '{table_name}' está vacía o no existe en el Supabase del cliente.")
            
            df = pd.DataFrame(data)
            logging.info(f"Extracción exitosa: {len(df)} registros vectorizados.")
            
            return df

        except Exception as e:
            logging.error(f"Fallo crítico en la extracción de datos: {str(e)}")
            raise
