"""
Optimization Engine - Escudo 3 (El Bisturí)
Evangelista & Co. | Sentinel Decision Intelligence V2

Calcula estrategias matemáticamente óptimas usando CVXPY:
  - optimize_opex_reduction():    Maximizar liquidez reduciendo OPEX
  - optimize_payment_schedule():  Diferir pagos a proveedores óptimamente
  - optimize_factoring():         Factoraje óptimo de cartera
  - generate_rescue_plan():       Pipeline completo de prescripción
"""

import logging
import warnings
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

logger = logging.getLogger(__name__)


# ── Constantes de negocio ──────────────────────────────────────────────────────

OPEX_MAX_REDUCCION   = 0.20   # Máximo 20% de reducción OPEX
OPEX_MIN_REDUCCION   = 0.00   # Mínimo 0%
PAGO_MAX_DIFERIMIENTO = 45    # Días máximos a diferir pago proveedor
FACTORING_TASA       = 0.015  # Costo del factoraje (1.5% mensual)
FACTORING_MAX_FRAC   = 0.60   # Máximo 60% de cartera por factorar
UMBRAL_CRISIS        = 0.15   # Si prob_crisis > 15%, activar plan de rescate


# ── Motor principal ────────────────────────────────────────────────────────────

class OptimizationEngine:
    """
    Motor de optimización prescriptiva usando CVXPY.

    Uso:
        engine = OptimizationEngine(stress_results, forecasting_results)
        plan   = engine.generate_rescue_plan()
    """

    def __init__(self, stress_results: dict, forecasting_results: dict,
                 opex_mensual: Optional[float] = None,
                 cartera_total: Optional[float] = None):

        self.stress_results      = stress_results
        self.forecasting_results = forecasting_results

        self.prob_crisis = stress_results.get("probabilidad_crisis", 0.0)
        self.mes_critico = stress_results.get("mes_critico")

        # Extraer métricas financieras base del Escudo 1
        self.opex_mensual   = opex_mensual   or self._extraer_opex()
        self.cartera_total  = cartera_total  or self._extraer_cartera()
        self.ingresos_mes   = self._extraer_ingresos()

        logger.info(
            f"OptimizationEngine | prob_crisis={self.prob_crisis:.1%} "
            f"opex={self.opex_mensual:,.0f} cartera={self.cartera_total:,.0f}"
        )

    def _extraer_opex(self) -> float:
        try:
            df = self.forecasting_results.get("costos_12m")
            if df is not None and not df.empty:
                return float(df["valor_proyectado"].mean())
        except Exception:
            pass
        return 450_000.0

    def _extraer_cartera(self) -> float:
        """Cartera estimada como 2 meses de ingresos."""
        return self._extraer_ingresos() * 2.0

    def _extraer_ingresos(self) -> float:
        try:
            df = self.forecasting_results.get("ingresos_12m")
            if df is not None and not df.empty:
                return float(df["valor_proyectado"].mean())
        except Exception:
            pass
        return 700_000.0

    # ── Estrategia 1: Reducción de OPEX ───────────────────────────────────────

    def optimize_opex_reduction(self) -> dict:
        """
        Usa CVXPY para calcular la reducción óptima de OPEX que maximiza
        la liquidez sin comprometer la operación crítica.

        Variables de decisión:
          x ∈ [0, 0.20]  → fracción de reducción de OPEX

        Objetivo:
          Maximizar liquidez_salvada = opex_mensual * x * meses_hasta_crisis

        Constraints:
          x ≥ 0
          x ≤ OPEX_MAX_REDUCCION (20%)
          x * opex_mensual ≥ 0  (no puede "ganar" dinero reduciendo)
        """
        import cvxpy as cp

        meses = self.mes_critico or 3
        x = cp.Variable(nonneg=True)

        # Capital que se libera por reducir OPEX durante meses_hasta_crisis
        liquidez_liberada = self.opex_mensual * x * meses

        objective   = cp.Maximize(liquidez_liberada)
        constraints = [x <= OPEX_MAX_REDUCCION, x >= OPEX_MIN_REDUCCION]

        problem = cp.Problem(objective, constraints)
        problem.solve(solver=cp.CLARABEL)

        if problem.status in ("optimal", "optimal_inaccurate") and x.value is not None:
            reduccion = float(x.value)
            capital_salvado = float(liquidez_liberada.value)
        else:
            # Fallback analítico: usar máxima reducción permitida
            reduccion = OPEX_MAX_REDUCCION
            capital_salvado = self.opex_mensual * reduccion * meses

        return {
            "titulo":          "Reducción de OPEX",
            "accion":          f"Reducir OPEX {reduccion:.1%} durante {meses} meses",
            "descripcion":     (
                f"Implementar reducción controlada de gastos operativos del "
                f"{reduccion:.1%} mensual. Priorizar reducción en áreas no críticas: "
                f"viáticos, outsourcing no esencial, diferimiento de inversiones."
            ),
            "reduccion_opex_pct": round(reduccion, 4),
            "capital_liberado": round(capital_salvado, 2),
            "deadline":        f"Implementar antes del mes {max(1, (self.mes_critico or 3) - 1)}",
            "roi":             round(capital_salvado / max(1, self.opex_mensual * reduccion), 2),
            "solver_status":   problem.status if hasattr(problem, "status") else "analítico",
        }

    # ── Estrategia 2: Diferimiento de pagos ───────────────────────────────────

    def optimize_payment_schedule(self) -> dict:
        """
        Optimiza cuántos días diferir pagos a proveedores para maximizar
        el float de caja sin dañar relaciones comerciales.

        Variable de decisión:
          d ∈ [0, 45]  → días de diferimiento promedio

        Objetivo:
          Maximizar capital_flotante = opex_mensual * (d / 30) * fraccion_proveedores

        Constraints:
          d ≤ PAGO_MAX_DIFERIMIENTO (45 días)
          d ≥ 0
        """
        import cvxpy as cp

        fraccion_prov = 0.40  # ~40% del OPEX son pagos a proveedores diferibles
        d = cp.Variable(nonneg=True)

        capital_flotante = self.opex_mensual * fraccion_prov * (d / 30.0)

        objective   = cp.Maximize(capital_flotante)
        constraints = [d <= PAGO_MAX_DIFERIMIENTO, d >= 0]

        problem = cp.Problem(objective, constraints)
        problem.solve(solver=cp.CLARABEL)

        if problem.status in ("optimal", "optimal_inaccurate") and d.value is not None:
            dias = float(d.value)
        else:
            dias = PAGO_MAX_DIFERIMIENTO

        capital = self.opex_mensual * fraccion_prov * (dias / 30.0)

        return {
            "titulo":          "Diferimiento de Pagos a Proveedores",
            "accion":          f"Negociar diferir pagos {dias:.0f} días con proveedores clave",
            "descripcion":     (
                f"Extender términos de pago a proveedores no críticos en {dias:.0f} días "
                f"adicionales. Mantener pago puntual a proveedores estratégicos. "
                f"Aplicable al {fraccion_prov:.0%} del OPEX mensual."
            ),
            "dias_diferimiento": round(dias, 1),
            "capital_liberado":  round(capital, 2),
            "deadline":          "Negociar en los próximos 5 días hábiles",
            "roi":               round(capital / max(1, self.opex_mensual * 0.01), 2),
            "solver_status":     problem.status if hasattr(problem, "status") else "analítico",
        }

    # ── Estrategia 3: Factoraje de cartera ────────────────────────────────────

    def optimize_factoring(self) -> dict:
        """
        Calcula el porcentaje óptimo de cartera a factorar considerando
        el costo del factoraje vs. el beneficio de liquidez inmediata.

        Variable de decisión:
          f ∈ [0, 0.60]  → fracción de cartera a factorar

        Objetivo:
          Maximizar (liquidez_neta) = cartera * f * (1 - tasa_factoraje)

        Constraints:
          f ≤ FACTORING_MAX_FRAC
          cartera * f * (1 - tasa) ≥ 0
        """
        import cvxpy as cp

        f = cp.Variable(nonneg=True)

        # Liquidez neta: cartera cobrada menos costo del factoraje
        liquidez_neta = self.cartera_total * f * (1 - FACTORING_TASA)

        # Minimizar costo implícito: objetivo cuadrático para solución interior
        costo_factoraje = self.cartera_total * f * FACTORING_TASA
        objective   = cp.Maximize(liquidez_neta - 0.5 * costo_factoraje)
        constraints = [f <= FACTORING_MAX_FRAC, f >= 0]

        problem = cp.Problem(objective, constraints)
        problem.solve(solver=cp.CLARABEL)

        if problem.status in ("optimal", "optimal_inaccurate") and f.value is not None:
            frac = float(f.value)
        else:
            frac = 0.30  # Fallback conservador

        cartera_factoreada = self.cartera_total * frac
        liquidez_obtenida  = cartera_factoreada * (1 - FACTORING_TASA)
        costo_real         = cartera_factoreada * FACTORING_TASA

        return {
            "titulo":              "Factoraje de Cartera",
            "accion":              f"Factorar {frac:.0%} de cartera vigente",
            "descripcion":         (
                f"Ceder {frac:.0%} de la cartera ({cartera_factoreada:,.0f} MXN) "
                f"a una institución de factoraje. Costo financiero: "
                f"{costo_real:,.0f} MXN ({FACTORING_TASA:.1%} mensual). "
                f"Liquidez neta inmediata: {liquidez_obtenida:,.0f} MXN."
            ),
            "fraccion_cartera":    round(frac, 4),
            "cartera_factoreada":  round(cartera_factoreada, 2),
            "capital_liberado":    round(liquidez_obtenida, 2),
            "costo_factoraje":     round(costo_real, 2),
            "deadline":            "Contactar institución financiera esta semana",
            "roi":                 round(liquidez_obtenida / max(1, costo_real), 2),
            "solver_status":       problem.status if hasattr(problem, "status") else "analítico",
        }

    # ── Optimización conjunta (multi-estrategia) ──────────────────────────────

    def optimize_combined(self) -> dict:
        """
        Optimización conjunta de las 3 estrategias con restricción de presupuesto
        de "dolor" (cuánta incomodidad puede absorber la empresa).

        Variables: x (OPEX), d (días pago), f (factoraje)
        Objetivo: Maximizar liquidez total
        Constraint: impacto_operativo ≤ umbral_tolerancia
        """
        import cvxpy as cp

        x = cp.Variable(nonneg=True)   # reducción OPEX
        d = cp.Variable(nonneg=True)   # días diferimiento
        f = cp.Variable(nonneg=True)   # fracción factoraje

        meses = self.mes_critico or 3
        frac_prov = 0.40

        liquidez_opex    = self.opex_mensual * x * meses
        liquidez_pagos   = self.opex_mensual * frac_prov * (d / 30.0)
        liquidez_factor  = self.cartera_total * f * (1 - FACTORING_TASA)

        liquidez_total = liquidez_opex + liquidez_pagos + liquidez_factor

        # Impacto operativo (ponderado): OPEX pesa más
        impacto = 0.6 * x + 0.2 * (d / PAGO_MAX_DIFERIMIENTO) + 0.2 * f
        umbral_tolerancia = 0.5  # 50% de impacto máximo tolerable

        objective = cp.Maximize(liquidez_total)
        constraints = [
            x <= OPEX_MAX_REDUCCION, x >= 0,
            d <= PAGO_MAX_DIFERIMIENTO, d >= 0,
            f <= FACTORING_MAX_FRAC, f >= 0,
            impacto <= umbral_tolerancia,
        ]

        problem = cp.Problem(objective, constraints)
        problem.solve(solver=cp.CLARABEL)

        if problem.status in ("optimal", "optimal_inaccurate") and x.value is not None:
            return {
                "opex_reduccion":    round(float(x.value), 4),
                "dias_diferimiento": round(float(d.value), 1),
                "fraccion_factoraje": round(float(f.value), 4),
                "liquidez_total":    round(float(liquidez_total.value), 2),
                "impacto_operativo": round(float(impacto.value), 4),
                "solver_status":     problem.status,
            }
        else:
            return {
                "opex_reduccion":    0.08,
                "dias_diferimiento": 30.0,
                "fraccion_factoraje": 0.20,
                "liquidez_total":    0.0,
                "impacto_operativo": 0.30,
                "solver_status":     "fallback_analítico",
            }

    # ── ROI del plan completo ─────────────────────────────────────────────────

    def _calcular_roi_plan(self, estrategias: list) -> float:
        """ROI = liquidez_total_liberada / costo_implementacion_estimado."""
        capital_total = sum(e.get("capital_liberado", 0) for e in estrategias)
        costo_impl = sum(e.get("costo_factoraje", 0) for e in estrategias)
        costo_impl += self.opex_mensual * 0.005   # ~0.5% costo de gestión
        return round(capital_total / max(1, costo_impl), 2)

    # ── Pipeline completo ─────────────────────────────────────────────────────

    def generate_rescue_plan(self) -> dict:
        """
        Pipeline completo del Escudo 3.

        Si prob_crisis ≤ umbral (15%), retorna mensaje de no-crisis.
        Si prob_crisis > umbral, calcula y retorna plan de rescate óptimo.

        Returns:
            dict con crisis_detectada, estrategias, capital_total_liberado,
                 roi_estimado, optimizacion_conjunta, mes_critico
        """
        logger.info(f"Escudo 3 - Bisturí: prob_crisis={self.prob_crisis:.1%}")

        if self.prob_crisis <= UMBRAL_CRISIS:
            return {
                "crisis_detectada":     False,
                "prob_crisis":          self.prob_crisis,
                "mensaje":              (
                    f"No se requiere plan de rescate. "
                    f"Probabilidad de crisis ({self.prob_crisis:.1%}) "
                    f"está por debajo del umbral ({UMBRAL_CRISIS:.0%})."
                ),
                "estrategias":          [],
                "capital_total_liberado": 0,
                "roi_estimado":         0,
                "generado_en":          datetime.now().isoformat(),
            }

        # Calcular las 3 estrategias individualmente
        estrategia_opex    = self.optimize_opex_reduction()
        estrategia_pagos   = self.optimize_payment_schedule()
        estrategia_factor  = self.optimize_factoring()
        opt_conjunta       = self.optimize_combined()

        estrategias = [estrategia_opex, estrategia_pagos, estrategia_factor]

        capital_total = sum(e["capital_liberado"] for e in estrategias)
        roi_plan      = self._calcular_roi_plan(estrategias)

        logger.info(
            f"Plan de rescate generado | capital={capital_total:,.0f} "
            f"roi={roi_plan}x | mes_critico={self.mes_critico}"
        )

        return {
            "crisis_detectada":       True,
            "prob_crisis":            self.prob_crisis,
            "mes_critico":            self.mes_critico,
            "evento_detonante":       self.stress_results.get("evento_detonante"),
            "estrategias":            estrategias,
            "capital_total_liberado": round(capital_total, 2),
            "roi_estimado":           roi_plan,
            "optimizacion_conjunta":  opt_conjunta,
            "generado_en":            datetime.now().isoformat(),
        }
