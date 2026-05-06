"""
Stress Testing Engine - Escudo 2 (La Trituradora)
Evangelista & Co. | Sentinel Decision Intelligence V2

Aplica choques macroeconómicos correlacionados y simula efectos dominó:
  - Riskfolio-Lib / numpy: Cópulas gaussianas para generar 10,000 escenarios
  - PyMC (opcional): Probabilidad bayesiana de default de clientes
  - SimPy: Simulación de eventos discretos (cadena de pagos)
"""

import logging
import warnings
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Optional

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

logger = logging.getLogger(__name__)


# ── Helpers de importación segura ─────────────────────────────────────────────

def _import_simpy():
    import simpy
    return simpy


def _import_pymc():
    import pymc as pm
    import pytensor.tensor as pt
    return pm, pt


def _import_riskfolio():
    import riskfolio as rp
    return rp


# ── Definición de choques macroeconómicos ─────────────────────────────────────

# Correlaciones históricas entre variables macro mexicanas
MACRO_VARS = ["TIIE", "USD_MXN", "INPC", "IGAE", "SOBRECOSTO", "RETRASO_COBRO"]

# Matriz de correlación estimada (basada en comportamiento histórico México)
CORRELATION_MATRIX = np.array([
    # TIIE  USDMXN  INPC  IGAE  SOBRE  RETRASO
    [1.00,   0.45,  0.60, -0.35,  0.20,   0.15],  # TIIE
    [0.45,   1.00,  0.50, -0.55,  0.30,   0.25],  # USD_MXN
    [0.60,   0.50,  1.00, -0.40,  0.25,   0.20],  # INPC
    [-0.35, -0.55, -0.40,  1.00, -0.15,  -0.30],  # IGAE
    [0.20,   0.30,  0.25, -0.15,  1.00,   0.50],  # SOBRECOSTO
    [0.15,   0.25,  0.20, -0.30,  0.50,   1.00],  # RETRASO_COBRO
])

# Parámetros base de cada variable (media, std) en escenario normal
MACRO_PARAMS = {
    "TIIE":          {"mean": 0.00,  "std": 0.015},  # Δ% mensual
    "USD_MXN":       {"mean": 0.00,  "std": 0.025},
    "INPC":          {"mean": 0.004, "std": 0.008},
    "IGAE":          {"mean": 0.001, "std": 0.012},
    "SOBRECOSTO":    {"mean": 0.03,  "std": 0.08},   # Fracción de sobrecosto
    "RETRASO_COBRO": {"mean": 0.10,  "std": 0.15},   # Fracción de cartera retrasada
}


# ── SimPy: Simulación de cadena de pagos ──────────────────────────────────────

class CadenaPagosSimulation:
    """
    Simula el flujo de caja mensual bajo un escenario de estrés usando SimPy.

    Proceso:
      Cobro de facturas → Pago de proveedores → Nómina → Resultado de caja
    """

    def __init__(self, escenario: dict, caja_inicial: float = 500_000,
                 ingresos_base: float = 700_000, costos_base: float = 450_000,
                 n_meses: int = 12):
        self.escenario = escenario
        self.caja_inicial = caja_inicial
        self.ingresos_base = ingresos_base
        self.costos_base = costos_base
        self.n_meses = n_meses

        self.historial_caja = []
        self.crisis_mes = None
        self.evento_detonante = None

    def run(self) -> dict:
        simpy = _import_simpy()
        env = simpy.Environment()
        env.process(self._pipeline_financiero(env))
        env.run(until=self.n_meses)

        caja_final = self.historial_caja[-1]["caja"] if self.historial_caja else self.caja_inicial
        return {
            "historial_caja": self.historial_caja,
            "caja_final": caja_final,
            "crisis_detectada": self.crisis_mes is not None,
            "crisis_mes": self.crisis_mes,
            "evento_detonante": self.evento_detonante,
            "caja_minima": min(h["caja"] for h in self.historial_caja) if self.historial_caja else 0,
        }

    def _pipeline_financiero(self, env):
        """Generador SimPy: simula cada mes del ciclo financiero."""
        caja = self.caja_inicial

        # Parámetros del escenario
        sobrecosto   = max(0, self.escenario.get("SOBRECOSTO", 0.03))
        retraso_frac = min(0.99, max(0, self.escenario.get("RETRASO_COBRO", 0.10)))
        shock_tiie   = self.escenario.get("TIIE", 0.0)
        shock_fx     = self.escenario.get("USD_MXN", 0.0)

        # Impacto del alza de TIIE sobre costo de deuda (si hay)
        costo_deuda_adicional = max(0, shock_tiie) * self.costos_base * 0.1

        # Impacto del tipo de cambio sobre costos de insumos importados
        costo_fx = max(0, shock_fx) * self.costos_base * 0.15

        for mes in range(1, self.n_meses + 1):
            yield env.timeout(1)

            # --- Ingresos: parte llega retrasada ---
            ingresos_cobrados = self.ingresos_base * (1 - retraso_frac)
            ingresos_diferidos = self.ingresos_base * retraso_frac  # llegan en mes siguiente

            # --- Costos: incluye sobrecosto y shocks ---
            costos_reales = (
                self.costos_base * (1 + sobrecosto)
                + costo_deuda_adicional
                + costo_fx
            )

            # --- Flujo del mes ---
            flujo_mes = ingresos_cobrados - costos_reales
            caja += flujo_mes

            # Recuperar diferidos del mes anterior (simplificado)
            if mes > 1:
                caja += ingresos_diferidos * 0.7  # 70% se recupera al siguiente mes

            evento = None
            if caja < 0 and self.crisis_mes is None:
                self.crisis_mes = mes
                if sobrecosto > 0.15:
                    evento = f"Sobrecosto {sobrecosto:.0%} en proyectos → quiebra de liquidez en mes {mes}"
                elif retraso_frac > 0.30:
                    evento = f"Retraso de cobro {retraso_frac:.0%} de cartera → caja negativa en mes {mes}"
                elif shock_tiie > 0.02:
                    evento = f"Alza TIIE {shock_tiie:.1%} → costo financiero insostenible en mes {mes}"
                else:
                    evento = f"Combinación de shocks macroeconómicos → crisis en mes {mes}"
                self.evento_detonante = evento

            self.historial_caja.append({
                "mes": mes,
                "ingresos": round(ingresos_cobrados, 2),
                "costos": round(costos_reales, 2),
                "flujo": round(flujo_mes, 2),
                "caja": round(caja, 2),
            })


# ── Motor principal de estrés ──────────────────────────────────────────────────

class StressTestingEngine:
    """
    Motor de estrés macroeconómico usando cópulas gaussianas + SimPy.

    Uso:
        engine = StressTestingEngine(forecasting_results)
        results = engine.run_stress_tests(n_scenarios=10_000)
    """

    def __init__(self, forecasting_results: dict,
                 caja_inicial: float = 500_000,
                 ingresos_base: Optional[float] = None,
                 costos_base: Optional[float] = None):

        self.forecasting_results = forecasting_results

        # Extraer métricas base del Escudo 1 o usar defaults
        self.caja_inicial   = caja_inicial
        self.ingresos_base  = ingresos_base or self._extraer_ingreso_base()
        self.costos_base    = costos_base   or self._extraer_costo_base()

        logger.info(
            f"StressTestingEngine | caja={caja_inicial:,.0f} "
            f"ingresos={self.ingresos_base:,.0f} costos={self.costos_base:,.0f}"
        )

    def _extraer_ingreso_base(self) -> float:
        try:
            df = self.forecasting_results.get("ingresos_12m")
            if df is not None and not df.empty:
                return float(df["valor_proyectado"].mean())
        except Exception:
            pass
        return 700_000.0

    def _extraer_costo_base(self) -> float:
        try:
            df = self.forecasting_results.get("costos_12m")
            if df is not None and not df.empty:
                return float(df["valor_proyectado"].mean())
        except Exception:
            pass
        return 450_000.0

    # ── Generación de escenarios vía cópula gaussiana ─────────────────────────

    def generate_scenarios(self, n_scenarios: int = 10_000,
                            seed: int = 42) -> pd.DataFrame:
        """
        Genera n_scenarios vectores de choques macroeconómicos correlacionados
        usando una cópula gaussiana.

        Returns:
            DataFrame con columnas = MACRO_VARS, filas = escenarios
        """
        rng = np.random.default_rng(seed)

        # Descomposición de Cholesky para correlaciones
        L = np.linalg.cholesky(CORRELATION_MATRIX)

        # Muestras normales independientes
        Z = rng.standard_normal((n_scenarios, len(MACRO_VARS)))

        # Aplicar correlaciones
        correlated = Z @ L.T

        # Escalar a media y desviación estándar de cada variable
        means = np.array([MACRO_PARAMS[v]["mean"] for v in MACRO_VARS])
        stds  = np.array([MACRO_PARAMS[v]["std"]  for v in MACRO_VARS])

        scenarios_raw = means + correlated * stds

        df = pd.DataFrame(scenarios_raw, columns=MACRO_VARS)

        # Truncar variables que no pueden ser negativas
        df["SOBRECOSTO"]    = df["SOBRECOSTO"].clip(lower=0)
        df["RETRASO_COBRO"] = df["RETRASO_COBRO"].clip(lower=0, upper=0.99)

        logger.info(f"Generados {n_scenarios} escenarios correlacionados")
        return df

    # ── Probabilidad de default bayesiana (PyMC) ──────────────────────────────

    def calculate_default_probability(self,
                                       dias_retraso_promedio: float = 15.0) -> dict:
        """
        Calcula probabilidad de default de clientes usando modelo beta-binomial (PyMC).

        Args:
            dias_retraso_promedio: Promedio de días de retraso histórico en cobros

        Returns:
            dict con prob_default_media, intervalo_credible_90
        """
        try:
            pm, pt = _import_pymc()

            # Prior: beta(α, β) calibrado con días de retraso
            # Más días de retraso → prior más pesimista
            alpha_prior = max(1.0, 30.0 / max(dias_retraso_promedio, 1.0))
            beta_prior  = max(1.0, alpha_prior * 3)

            with pm.Model() as model:
                # Probabilidad de default como variable latente
                p_default = pm.Beta("p_default", alpha=alpha_prior, beta=beta_prior)

                # Muestras MCMC (pocas para rapidez)
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    trace = pm.sample(
                        draws=500, tune=200, chains=1,
                        progressbar=False, return_inferencedata=True,
                        compute_convergence_checks=False,
                    )

            samples = trace.posterior["p_default"].values.flatten()
            return {
                "prob_default_media":    float(np.mean(samples)),
                "intervalo_credible_p5": float(np.percentile(samples, 5)),
                "intervalo_credible_p95": float(np.percentile(samples, 95)),
                "metodo": "PyMC Beta-Binomial",
            }

        except Exception as e:
            logger.warning(f"PyMC falló ({e}), usando estimación analítica")
            # Fallback: estimación analítica con distribución Beta
            alpha = max(1.0, 30.0 / max(dias_retraso_promedio, 1.0))
            beta  = max(1.0, alpha * 3)
            media = alpha / (alpha + beta)
            var   = (alpha * beta) / ((alpha + beta) ** 2 * (alpha + beta + 1))
            std   = np.sqrt(var)
            return {
                "prob_default_media":     round(media, 4),
                "intervalo_credible_p5":  round(max(0, media - 1.645 * std), 4),
                "intervalo_credible_p95": round(min(1, media + 1.645 * std), 4),
                "metodo": "Beta analítica (fallback)",
            }

    # ── SimPy: Simular un escenario ───────────────────────────────────────────

    def simulate_scenario(self, escenario: dict, n_meses: int = 12) -> dict:
        """Simula un escenario de estrés con SimPy y retorna métricas de caja."""
        sim = CadenaPagosSimulation(
            escenario=escenario,
            caja_inicial=self.caja_inicial,
            ingresos_base=self.ingresos_base,
            costos_base=self.costos_base,
            n_meses=n_meses,
        )
        return sim.run()

    # ── Pipeline completo ─────────────────────────────────────────────────────

    def run_stress_tests(self, n_scenarios: int = 10_000,
                          n_meses: int = 12,
                          sample_simpy: int = 500) -> dict:
        """
        Pipeline completo del Escudo 2.

        1. Genera n_scenarios con cópula gaussiana
        2. Corre SimPy en una muestra (sample_simpy) para calcular estadísticas
        3. Estima probabilidad de crisis para todos los escenarios

        Returns:
            dict con escenarios_summary, probabilidad_crisis, mes_critico,
                 evento_detonante, percentiles_caja, default_probability
        """
        logger.info(f"Escudo 2 - Trituradora: {n_scenarios} escenarios | {n_meses} meses")

        # 1. Generar escenarios correlacionados
        df_scenarios = self.generate_scenarios(n_scenarios)

        # 2. SimPy en muestra representativa
        indices = np.random.default_rng(0).choice(n_scenarios, size=min(sample_simpy, n_scenarios), replace=False)
        simpy_results = []

        for idx in indices:
            escenario = df_scenarios.iloc[idx].to_dict()
            res = self.simulate_scenario(escenario, n_meses)
            simpy_results.append({
                "scenario_idx":    int(idx),
                "caja_final":      res["caja_final"],
                "caja_minima":     res["caja_minima"],
                "crisis_detectada": res["crisis_detectada"],
                "crisis_mes":      res["crisis_mes"],
                "evento_detonante": res["evento_detonante"],
                **escenario,
            })

        df_sim = pd.DataFrame(simpy_results)

        # 3. Estadísticas de crisis
        n_crisis = df_sim["crisis_detectada"].sum()
        prob_crisis = float(n_crisis / len(df_sim))

        mes_critico = None
        evento_detonante = "Sin crisis detectada"
        if n_crisis > 0:
            df_crisis = df_sim[df_sim["crisis_detectada"]]
            mes_critico = int(df_crisis["crisis_mes"].mode().iloc[0])
            evento_detonante = df_crisis["evento_detonante"].dropna().mode().iloc[0]

        # 4. Percentiles de caja final
        percentiles_caja = {
            "p10": float(df_sim["caja_final"].quantile(0.10)),
            "p25": float(df_sim["caja_final"].quantile(0.25)),
            "p50": float(df_sim["caja_final"].quantile(0.50)),
            "p75": float(df_sim["caja_final"].quantile(0.75)),
            "p90": float(df_sim["caja_final"].quantile(0.90)),
        }

        # 5. Probabilidad de default (PyMC / analítica)
        default_prob = self.calculate_default_probability(
            dias_retraso_promedio=df_scenarios["RETRASO_COBRO"].mean() * 30
        )

        # 6. Top 5 escenarios de riesgo (mayor sobrecosto + mayor retraso)
        df_sim["riesgo_score"] = df_sim["SOBRECOSTO"] + df_sim["RETRASO_COBRO"]
        top_riesgo = (
            df_sim.nlargest(5, "riesgo_score")
            [["SOBRECOSTO", "RETRASO_COBRO", "TIIE", "USD_MXN", "caja_final", "crisis_detectada"]]
            .round(4)
            .to_dict(orient="records")
        )

        # 7. Probabilidad de crisis por mes (para semáforo)
        prob_por_mes = {}
        for mes in range(1, n_meses + 1):
            prob_por_mes[mes] = float(
                df_sim[df_sim["crisis_mes"] == mes].shape[0] / len(df_sim)
            )

        result = {
            "n_scenarios":          n_scenarios,
            "n_simulated":          len(df_sim),
            "probabilidad_crisis":  round(prob_crisis, 4),
            "mes_critico":          mes_critico,
            "evento_detonante":     evento_detonante,
            "percentiles_caja":     percentiles_caja,
            "probabilidad_por_mes": prob_por_mes,
            "top_escenarios_riesgo": top_riesgo,
            "default_probability":  default_prob,
            "semaforo":             _calcular_semaforo(prob_por_mes),
            "generado_en":          datetime.now().isoformat(),
        }

        logger.info(
            f"Escudo 2 completado | prob_crisis={prob_crisis:.1%} "
            f"mes_critico={mes_critico}"
        )
        return result


# ── Semáforo predictivo ───────────────────────────────────────────────────────

def _calcular_semaforo(prob_por_mes: dict) -> dict:
    """
    Clasifica cada mes en VERDE / AMARILLO / ROJO según probabilidad de crisis.

    Umbrales:
      < 15%  → VERDE  (saludable)
      15-30% → AMARILLO (alerta)
      > 30%  → ROJO   (crisis)
    """
    semaforo = {}
    for mes, prob in prob_por_mes.items():
        if prob < 0.15:
            semaforo[mes] = {"estado": "VERDE",    "emoji": "🟢", "prob": prob}
        elif prob < 0.30:
            semaforo[mes] = {"estado": "AMARILLO", "emoji": "🟡", "prob": prob}
        else:
            semaforo[mes] = {"estado": "ROJO",     "emoji": "🔴", "prob": prob}
    return semaforo
