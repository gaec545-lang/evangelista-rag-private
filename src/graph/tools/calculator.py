import re
import math
import structlog

logger = structlog.get_logger()

class PricingCalculator:
    """Cálculos de pricing de Evangelista & Co."""
    
    def estimate_from_text(self, text: str) -> str:
        """Extrae números del texto y calcula pricing."""
        # Intentar extraer sucursales
        suc_match = re.search(r'(\d+)\s*(sucursal|planta|sede|punto)', text.lower())
        sucursales = int(suc_match.group(1)) if suc_match else None
        
        # Intentar extraer ERPs
        erp_match = re.search(r'(\d+)\s*(erp|sistema|sap|contpaqi)', text.lower())
        erps = int(erp_match.group(1)) if erp_match else None
        
        if sucursales is not None and erps is not None:
            gamma = 1 + (0.5 * sucursales) + (0.2 * erps)
            setup = 180000 * gamma
            return (f"**Cálculo exacto:**\n"
                    f"- Sucursales/plantas: {sucursales}\n"
                    f"- Sistemas ERP: {erps}\n"  
                    f"- Factor Γ = 1 + (0.5 × {sucursales}) + (0.2 × {erps}) = {gamma:.2f}\n"
                    f"- Setup Fee = $180,000 × {gamma:.2f} = **${setup:,.0f} MXN**\n"
                    f"- Tramo A (70%): ${setup * 0.7:,.0f} MXN\n"
                    f"- Tramo B (30%): ${setup * 0.3:,.0f} MXN")
        elif sucursales is not None:
            gamma_min = 1 + (0.5 * sucursales) + (0.2 * 1)
            gamma_max = 1 + (0.5 * sucursales) + (0.2 * 3)
            return (f"**Estimación (falta número de ERPs):**\n"
                    f"- Sucursales: {sucursales}\n"
                    f"- ERPs estimados: 1-3\n"
                    f"- Rango Γ: {gamma_min:.2f} — {gamma_max:.2f}\n"
                    f"- Rango Setup Fee: **${180000*gamma_min:,.0f} — ${180000*gamma_max:,.0f} MXN**")
        else:
            return ("**No se detectaron datos suficientes para un cálculo preciso.**\n"
                    "Necesito: número de sucursales/plantas y sistemas ERP.")
    
    def estimate_roi(self, text: str) -> str:
        """Estima ROI basado en texto."""
        return "El ROI se calcula formalmente post-Foundation con datos reales del Dictamen de Hallazgos. Basado en casos similares, el ROI esperado varía entre 2x y 4x el costo del proyecto en el primer año."
    
    def calculate_alpha_from_text(self, text: str) -> str:
        """Calcula factor α desde texto."""
        reg_match = re.search(r'([\d,.]+)\s*(registro|transac|movimiento)', text.lower())
        if reg_match:
            try:
                registros = float(reg_match.group(1).replace(",", ""))
                alpha = math.log10(max(registros, 1)) - 4
                return f"α (Complejidad de Datos) = log10({registros:,.0f}) - 4 = {alpha:.2f}"
            except ValueError:
                return "Error al parsear el número de registros."
        return "Necesito el número de registros (transacciones mensuales) para calcular el factor α."
