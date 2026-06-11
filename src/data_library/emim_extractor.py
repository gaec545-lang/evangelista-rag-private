import os
import requests
import json
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv

from .base_extractor import BaseExtractor

INDICATORS = {
    "444084": "personal_ocupado_total",
    "444085": "obreros_total",
    "444087": "horas_trabajadas_obreros_mm",
    "444090": "remuneraciones_totales_mmxn",
    "444091": "sueldos_obreros_mmxn",
    "444094": "produccion_bruta_total_mmxn",
    "444096": "consumo_materia_prima_mmxn",
    "444097": "valor_agregado_censal_mmxn",
}

GEOGRAPHIC_LEVELS = {
    "nacional": "0700",
    "puebla":   "2100",
}

class EMIMExtractor(BaseExtractor):
    def __init__(self, token=None):
        super().__init__()
        if token:
            self.token = token
        else:
            load_dotenv()
            self.token = os.getenv("INEGI_TOKEN")

    def _safe_get(self, url):
        import time
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                time.sleep(2 ** attempt)
        raise Exception(f"Failed to fetch {url} after {max_retries} retries")

    def extract(self, months_back: int = 24) -> dict:
        results = {"nacional": {}, "puebla": {}}
        
        for region_name, region_code in GEOGRAPHIC_LEVELS.items():
            for ind_id, ind_name in INDICATORS.items():
                url = f"https://www.inegi.org.mx/app/api/indicadores/desarrolladores/jsonxml/INDICATOR/{ind_id}/es/{region_code}/false/BIE/2.0/{self.token}?type=json"
                try:
                    data = self._safe_get(url)
                    series = data.get("Series", [])
                    if series and "OBSERVATIONS" in series[0]:
                        obs = series[0]["OBSERVATIONS"]
                        # Filter to months_back
                        obs = obs[:months_back]
                        df = pd.DataFrame(obs)
                        # DataFrame has columns: TIME_PERIOD, OBS_VALUE
                        results[region_name][ind_name] = df
                except Exception as e:
                    print(f"Error extracting {ind_name} for {region_name}: {e}")
        
        return results

    def calculate_derived(self, results: dict):
        derived = {"nacional": {}, "puebla": {}}
        for region in ["nacional", "puebla"]:
            try:
                # Merge logic across months to align dates
                dfs = []
                for ind_name, df in results[region].items():
                    df = df.copy()
                    df = df.rename(columns={"OBS_VALUE": ind_name, "TIME_PERIOD": "period"})
                    df = df[["period", ind_name]]
                    # Convert to numeric
                    df[ind_name] = pd.to_numeric(df[ind_name], errors="coerce")
                    dfs.append(df)
                
                if not dfs:
                    continue
                
                # Merge all on 'period'
                merged = dfs[0]
                for i in range(1, len(dfs)):
                    merged = pd.merge(merged, dfs[i], on="period", how="outer")
                
                # Sort by period descending
                merged = merged.sort_values(by="period", ascending=False)
                
                # Derived 1: Costo laboral por hora obrero
                if "sueldos_obreros_mmxn" in merged.columns and "horas_trabajadas_obreros_mm" in merged.columns:
                    merged["costo_laboral_por_hora_mxn"] = merged["sueldos_obreros_mmxn"] / merged["horas_trabajadas_obreros_mm"]
                
                # Derived 2: Consumo de materia prima (%)
                if "consumo_materia_prima_mmxn" in merged.columns and "produccion_bruta_total_mmxn" in merged.columns:
                    merged["consumo_materia_prima_pct"] = (merged["consumo_materia_prima_mmxn"] / merged["produccion_bruta_total_mmxn"]) * 100
                
                # Derived 3: Valor agregado por empleado
                if "valor_agregado_censal_mmxn" in merged.columns and "personal_ocupado_total" in merged.columns:
                    merged["valor_agregado_por_empleado_mxn"] = (merged["valor_agregado_censal_mmxn"] * 1_000_000) / merged["personal_ocupado_total"]
                
                # Derived 4: Productividad por hora
                if "produccion_bruta_total_mmxn" in merged.columns and "horas_trabajadas_obreros_mm" in merged.columns:
                    merged["productividad_por_hora_mxn"] = merged["produccion_bruta_total_mmxn"] / merged["horas_trabajadas_obreros_mm"]
                
                # Derived 5: Variacion YoY personal ocupado
                if "personal_ocupado_total" in merged.columns:
                    # Sort ascending for pct_change then revert
                    merged = merged.sort_values(by="period")
                    merged["personal_ocupado_yoy"] = merged["personal_ocupado_total"].pct_change(periods=12) * 100
                    merged = merged.sort_values(by="period", ascending=False)
                    
                derived[region] = merged
            except Exception as e:
                print(f"Error calculating derived metrics for {region}: {e}")
        return derived

    def to_vault_document(self, data: dict, derived: dict, nivel: str, fecha_referencia: str) -> str:
        # Get the latest row from derived
        df = derived.get(nivel)
        if df is None or df.empty:
            return ""
        
        latest = df[df["period"] == fecha_referencia]
        if latest.empty:
            latest = df.iloc[0]
            fecha_referencia = latest["period"]
        else:
            latest = latest.iloc[0]
            
        def safe_get(col, decimals=2, is_pct=False):
            if col in latest.index and pd.notnull(latest[col]):
                val = latest[col]
                return f"{val:,.{decimals}f}"
            return "N/A"
            
        period_formatted = fecha_referencia.replace("/", "-")
        fecha_extraccion = datetime.now().strftime("%Y-%m-%d")
        
        md = f\"\"\"---
id: DAT-EMIM-{nivel}-{period_formatted}
tipo: benchmark_sectorial
subtipo: manufactura_indicadores_emim
nivel_geografico: {nivel}
periodo_referencia: {period_formatted}
fecha_extraccion: {fecha_extraccion}
agent_access: [all]
perecedero: true
vigencia_dias: 35
---

## Indicadores Manufactura EMIM - {nivel} - {period_formatted}

### Personal e Horas
- Personal ocupado total: {safe_get('personal_ocupado_total', 0)} personas ({safe_get('personal_ocupado_yoy', 2)}%)
- Obreros: {safe_get('obreros_total', 0)} personas
- Horas trabajadas: {safe_get('horas_trabajadas_obreros_mm')} millones de horas

### Costos Laborales
- Costo laboral por hora obrero: ${safe_get('costo_laboral_por_hora_mxn')} MXN
- Sueldos y salarios obreros: ${safe_get('sueldos_obreros_mmxn')} millones MXN
- Remuneraciones totales: ${safe_get('remuneraciones_totales_mmxn')} millones MXN

### Producción y Valor
- Producción bruta total: ${safe_get('produccion_bruta_total_mmxn')} millones MXN
- Consumo de materia prima: ${safe_get('consumo_materia_prima_mmxn')} millones MXN ({safe_get('consumo_materia_prima_pct')}%)
- Valor agregado por empleado: ${safe_get('valor_agregado_por_empleado_mxn')} MXN/persona/mes
- Productividad por hora: ${safe_get('productividad_por_hora_mxn')} MXN/hora

### Benchmarks para diagnóstico
Un costo laboral por hora de ${safe_get('costo_laboral_por_hora_mxn')} MXN en manufactura {nivel} se observa en el periodo {period_formatted}.

### Variaciones históricas (últimos 12 meses)
| Mes | Personal | Producción (mmxn) | Costo/hora (MXN) |
|-----|----------|-------------------|------------------|
\"\"\"
        
        # Add table rows for last 12 periods
        hist = df.head(12)
        for _, row in hist.iterrows():
            p = row.get('period', 'N/A')
            pers = f"{row.get('personal_ocupado_total', 0):,.0f}" if pd.notnull(row.get('personal_ocupado_total')) else "N/A"
            prod = f"{row.get('produccion_bruta_total_mmxn', 0):,.2f}" if pd.notnull(row.get('produccion_bruta_total_mmxn')) else "N/A"
            cost = f"{row.get('costo_laboral_por_hora_mxn', 0):,.2f}" if pd.notnull(row.get('costo_laboral_por_hora_mxn')) else "N/A"
            md += f"| {p} | {pers} | {prod} | {cost} |\n"
            
        return md
