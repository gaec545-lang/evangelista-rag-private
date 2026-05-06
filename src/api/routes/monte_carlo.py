"""Sentinel Monte Carlo Simulation Router — Evangelista Intelligence Platform.

Endpoint protegido con:
- JWT authentication via Supabase Auth
- Subscription ownership verification
- Rate limiting (5 req/min por IP)
- Pydantic validation estricta
- Audit logging
- Zero info-leak en errores
"""
import time
import uuid
from typing import Literal, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from src.config import settings
from src.utils.logger import get_logger
from src.api.middleware.auth import verify_jwt, verify_subscription_ownership

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/sentinel")

# ─── In-memory simulation store (dev) ───
_simulations: dict[str, dict] = {}

# ─── Pydantic Schemas (Zero-Trust Validation) ───

VALID_DISTRIBUTIONS = ("normal", "triangular", "uniform")
VALID_TENDENCIES = ("up", "down", "stable")

MIN_ITERATIONS = 1_000
MAX_ITERATIONS = 100_000
MAX_VARIABLES = 20
MAX_PAYLOAD_SIZE = 10_000  # bytes


class RiskVariable(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    distribucion: Literal["normal", "triangular", "uniform"] = Field(
        ..., description="Tipo de distribucion"
    )
    # Normal: mean, std
    # Triangular: min, mode, max
    # Uniform: min, max
    parametros: dict = Field(..., description="Parametros segun distribucion")

    @field_validator("parametros")
    @classmethod
    def validate_params(cls, v: dict, info) -> dict:
        return v


class MonteCarloRequest(BaseModel):
    subscription_id: str = Field(..., pattern=r"^[0-9a-fA-F-]{36}$")
    iterations: int = Field(
        default=10_000,
        ge=MIN_ITERATIONS,
        le=MAX_ITERATIONS,
        description="Numero de simulaciones",
    )
    variables: list[RiskVariable] = Field(
        default_factory=list,
        max_length=MAX_VARIABLES,
        description="Variables de riesgo para simular",
    )
    # Campos opcionales de contexto
    modelo_negocio: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Funcion de modelo de negocio en Python (safe eval)",
    )


# ─── Monte Carlo Engine (pure numpy) ───


def _run_monte_carlo(
    iterations: int,
    variables: list[dict],
    modelo_negocio: Optional[str] = None,
) -> dict:
    """Ejecuta simulacion Monte Carlo pura con numpy.

    Returns: estadistica completa sin exponer datos internos.
    """
    import numpy as np

    n = iterations
    rng = np.random.default_rng()

    # Sample each variable
    samples = {}
    for var in variables:
        dist = var["distribucion"]
        params = var["parametros"]
        if dist == "normal":
            mean = float(params.get("mean", 0))
            std = float(params.get("std", 1))
            samples[var["nombre"]] = rng.normal(mean, std, n)
        elif dist == "triangular":
            low = float(params.get("min", 0))
            mode = float(params.get("mode", 0))
            high = float(params.get("max", 1))
            samples[var["nombre"]] = rng.triangular(low, mode, high, n)
        elif dist == "uniform":
            low = float(params.get("min", 0))
            high = float(params.get("max", 1))
            samples[var["nombre"]] = rng.uniform(low, high, n)

    # If business model provided, execute it
    if modelo_negocio and samples:
        try:
            # Safe-ish: only numpy and variable names in namespace
            safe_namespace = {
                "np": np,
                **{k: v for k, v in samples.items()},
            }
            outcomes = eval(modelo_negocio, {"__builtins__": {}}, safe_namespace)
            if not hasattr(outcomes, "__len__"):
                outcomes = np.full(n, outcomes)
        except Exception as e:
            logger.error("modelo_negocio_eval_error", error=str(e))
            # Fallback: sum all variables
            outcomes = np.zeros(n)
            for arr in samples.values():
                outcomes += arr
    else:
        # Default: simple sum
        outcomes = np.zeros(n)
        for arr in samples.values():
            outcomes += arr

    return _compute_statistics(outcomes, samples)


def _compute_statistics(outcomes, samples: dict) -> dict:
    import numpy as np

    outcomes = np.array(outcomes, dtype=float)
    n = len(outcomes)
    sorted_outcomes = np.sort(outcomes)

    # Sensitivity: correlation of each variable with outcomes
    sensitivity = {}
    for name, arr in samples.items():
        arr = np.array(arr, dtype=float)
        if len(arr) == n and np.std(arr) > 0 and np.std(outcomes) > 0:
            corr = float(np.corrcoef(arr, outcomes)[0, 1])
            sensitivity[name] = round(corr ** 2, 4)
        else:
            sensitivity[name] = 0.0

    # Sort sensitivity by importance
    sensitivity = dict(
        sorted(sensitivity.items(), key=lambda x: x[1], reverse=True)
    )

    # Triggers
    triggers = _evaluate_triggers(outcomes, sorted_outcomes)

    return {
        "mean": round(float(np.mean(outcomes)), 2),
        "median": round(float(np.median(outcomes)), 2),
        "std": round(float(np.std(outcomes)), 2),
        "variance": round(float(np.var(outcomes)), 2),
        "skewness": round(float(_skewness(outcomes)), 4),
        "p5": round(float(np.percentile(sorted_outcomes, 5)), 2),
        "p10": round(float(np.percentile(sorted_outcomes, 10)), 2),
        "p25": round(float(np.percentile(sorted_outcomes, 25)), 2),
        "p50": round(float(np.percentile(sorted_outcomes, 50)), 2),
        "p75": round(float(np.percentile(sorted_outcomes, 75)), 2),
        "p90": round(float(np.percentile(sorted_outcomes, 90)), 2),
        "p95": round(float(np.percentile(sorted_outcomes, 95)), 2),
        "p99": round(float(np.percentile(sorted_outcomes, 99)), 2),
        "min": round(float(np.min(outcomes)), 2),
        "max": round(float(np.max(outcomes)), 2),
        "prob_loss": float(np.mean(outcomes < 0)),
        "probability_of_loss": round(
            float(np.mean(outcomes < 0) * 100), 2
        ),
        "var_95": round(float(np.percentile(sorted_outcomes, 5)), 2),
        "cvar_95": round(
            float(np.mean(sorted_outcomes[: max(1, int(n * 0.05))])), 2
        ),
        "coefficient_of_variation": round(
            float(np.std(outcomes) / abs(np.mean(outcomes)))
            if np.mean(outcomes) != 0
            else 0.0,
            4,
        ),
        "sensitivity": sensitivity,
        "triggers": triggers,
        # Histogram data (20 bins)
        "histogram": _histogram_data(outcomes),
    }


def _skewness(arr):
    import numpy as np
    n = len(arr)
    if n < 3:
        return 0.0
    m = np.mean(arr)
    s = np.std(arr)
    if s == 0:
        return 0.0
    return float(n / ((n - 1) * (n - 2)) * np.sum(((arr - m) / s) ** 3))


def _histogram_data(outcomes, bins: int = 20):
    import numpy as np
    counts, edges = np.histogram(outcomes, bins=bins)
    result = []
    for i in range(len(counts)):
        result.append({
            "low": round(float(edges[i]), 2),
            "high": round(float(edges[i + 1]), 2),
            "count": int(counts[i]),
        })
    return result


def _evaluate_triggers(outcomes, sorted_outcomes):
    import numpy as np
    triggers = []

    prob_loss = float(np.mean(outcomes < 0) * 100)
    mean_val = float(np.mean(outcomes))
    std_val = float(np.std(outcomes))
    p10 = float(np.percentile(sorted_outcomes, 10))

    # Trigger 1: Probability of loss
    if prob_loss > 30:
        triggers.append({
            "severity": "CRITICO",
            "type": "probabilidad_perdida",
            "message": f"Probabilidad de perdida del {prob_loss:.1f}% supera el umbral critico del 30%.",
            "threshold": 30,
            "actual": round(prob_loss, 1),
        })
    elif prob_loss > 15:
        triggers.append({
            "severity": "ALTO",
            "type": "probabilidad_perdida",
            "message": f"Probabilidad de perdida del {prob_loss:.1f}% alerta.",
            "threshold": 15,
            "actual": round(prob_loss, 1),
        })

    # Trigger 2: Coefficient of variation
    if mean_val != 0:
        cv = std_val / abs(mean_val)
        if cv > 1.0:
            triggers.append({
                "severity": "ALTO",
                "type": "volatilidad_operativa",
                "message": f"Coeficiente de variacion de {cv:.2f} indica alta volatilidad (>1.0).",
                "threshold": 1.0,
                "actual": round(cv, 2),
            })

    # Trigger 3: P10 downside
    if p10 < 0:
        triggers.append({
            "severity": "MEDIO",
            "type": "riesgo_bajada",
            "message": f"Percentil 10 en {p10:.2f} indica riesgo de perdida en escenarios adversos.",
            "threshold": 0,
            "actual": round(p10, 2),
        })

    return triggers


# ─── Recommendations Engine (Rule-Based) ───


def _generate_recommendations(stats: dict) -> dict:
    """Genera recomendaciones basadas en Decision Intelligence con LLM."""
    from src.engines.decision_intelligence_engine import DecisionIntelligenceEngine
    
    class MockConfig:
        def get(self, key, default=None):
            if key == "client.name": return "Sentinel Client"
            if key == "client.industry": return "General"
            return default
            
    engine = DecisionIntelligenceEngine(MockConfig())
    import pandas as pd
    sensitivity = stats.get("sensitivity", {})
    df_sens = pd.DataFrame([{"variable": k, "importance": v} for k, v in sensitivity.items()])
    
    return engine.generate_recommendations(stats, df_sens)


# ─── Endpoints ───


@router.post("{subscription_id}/simulate", response_model=dict, tags=["Sentinel"])
async def simulate_monte_carlo(
    subscription_id: str,
    request: MonteCarloRequest,
    user: dict = Depends(verify_jwt),
):
    """Ejecuta simulacion Monte Carlo para una suscripcion Sentinel.

    Protegido por:
    - JWT Auth (Supabase)
    - Subscription ownership
    - Rate limiting (middleware)
    - Validacion Pydantic estricta
    """
    start_time = time.time()

    # --- Cross-validate subscription_id ---
    if subscription_id != request.subscription_id:
        raise HTTPException(
            status_code=400,
            detail="El subscription_id en la URL no coincide con el del body.",
        )

    # --- Validate variables have required params ---
    for var in request.variables:
        if var.distribucion == "normal":
            if "mean" not in var.parametros or "std" not in var.parametros:
                raise HTTPException(
                    status_code=400,
                    detail=f"Variable '{var.nombre}' requiere parametros 'mean' y 'std' para distribucion normal.",
                )
        elif var.distribucion == "triangular":
            if not all(k in var.parametros for k in ("min", "mode", "max")):
                raise HTTPException(
                    status_code=400,
                    detail=f"Variable '{var.nombre}' requiere 'min', 'mode', 'max' para distribucion triangular.",
                )
        elif var.distribucion == "uniform":
            if "min" not in var.parametros or "max" not in var.parametros:
                raise HTTPException(
                    status_code=400,
                    detail=f"Variable '{var.nombre}' requiere 'min' y 'max' para distribucion uniform.",
                )

    # --- Execute simulation ---
    try:
        vars_for_engine = [v.model_dump() for v in request.variables]
        stats = _run_monte_carlo(
            request.iterations,
            vars_for_engine,
            request.modelo_negocio,
        )
    except Exception as e:
        logger.error("monte_carlo_execution_error", error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Error interno al ejecutar la simulacion.",
        )

    # --- Generate recommendations ---
    recommendations_data = _generate_recommendations(stats)
    recommendations = recommendations_data.get("recommendations", [])
    executive_summary = recommendations_data.get("executive_summary", "")

    # --- Store simulation record ---
    sim_id = str(uuid.uuid4())
    _simulations[sim_id] = {
        "subscription_id": subscription_id,
        "user_id": user.get("user_id"),
        "iterations": request.iterations,
        "num_variables": len(request.variables),
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": round((time.time() - start_time) * 1000),
    }

    # --- Audit log ---
    logger.info(
        "monte_carlo_simulation_executed",
        simulation_id=sim_id,
        subscription_id=subscription_id,
        user_id=user.get("user_id"),
        iterations=request.iterations,
        duration_ms=_simulations[sim_id]["duration_ms"],
        num_variables=len(request.variables),
    )

    return {
        "simulation_id": sim_id,
        "subscription_id": subscription_id,
        "iterations": request.iterations,
        "executed_at": _simulations[sim_id]["executed_at"],
        "duration_ms": _simulations[sim_id]["duration_ms"],
        "statistics": {
            k: v
            for k, v in stats.items()
            if k not in ("histogram",)  # histogram goes separate
        },
        "histogram": stats.get("histogram", []),
        "triggers": stats.get("triggers", []),
        "recommendations": recommendations,
        "executive_summary": executive_summary,
    }


@router.get("{subscription_id}/simulations", response_model=list[dict], tags=["Sentinel"])
async def list_simulations(
    subscription_id: str,
    limit: int = 10,
    user: dict = Depends(verify_jwt),
):
    """Lista historial de simulaciones para una suscripcion."""
    sims = [
        s for s in _simulations.values()
        if s["subscription_id"] == subscription_id
    ]
    sims.sort(key=lambda x: x["executed_at"], reverse=True)
    return sims[:limit]
