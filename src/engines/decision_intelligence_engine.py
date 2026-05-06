"""
Decision Intelligence Engine - Fase 4
Genera recomendaciones prescriptivas usando IA (Groq/Llama 3) con fallback rule-based.

Zero-Crash Policy: nunca colapsa aunque la API de IA esté offline, sin credenciales
o devuelva una respuesta malformada. El análisis matemático de las Fases 1-3 siempre
se preserva independientemente del estado de la IA.
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional

import pandas as pd
from src.configuration_manager import ConfigurationManager

try:
    import streamlit as st
except ImportError:
    st = None

try:
    from groq import Groq
except ImportError:
    Groq = None  # type: ignore[assignment,misc]


# ==============================================================================
# PROMPT ESTRATÉGICO — NO MODIFICAR
# ==============================================================================
PROMPT_STRATEGIC_ADVISOR = """
Eres el "Socio Director de Decisiones Estratégicas" de Evangelista & Co. (Puebla, México).
Tu mandato exclusivo es convertir datos estadísticos de simulación Monte Carlo en un
plan de acción ejecutivo concreto, accionable y priorizado.

================================================================================
LEYES ABSOLUTAS (ZERO-HALLUCINATION POLICY)
================================================================================
1. Responde ÚNICAMENTE en JSON válido. Sin texto extra. Sin markdown. Sin comentarios.
2. Cero suposiciones: basa cada recomendación EXCLUSIVAMENTE en los datos estadísticos
   proporcionados. No inventes variables ni escenarios no presentes.
3. Español mexicano profesional. Sin regionalismos extremos.
4. Cada recomendación debe tener un responsable real (CFO, Gerente de Compras, etc.)
   y un plazo en días concreto.
5. Prioridad 1 = acción inmediata (crisis). Prioridad 3 = mejora táctica.

================================================================================
FORMATO JSON OBLIGATORIO (respeta exactamente estas llaves)
================================================================================
{
    "executive_summary": "Párrafo ejecutivo de 3-5 oraciones describiendo la situación de riesgo, el escenario base y la urgencia de acción.",
    "confidence_level": "ALTO — [justificación de 1 línea] / MEDIO — [...] / BAJO — [...]",
    "recommendations": [
        {
            "title": "Título ejecutivo breve (máx. 8 palabras)",
            "priority": 1,
            "description": "Descripción accionable del riesgo y la estrategia de mitigación.",
            "actions": [
                {
                    "step": 1,
                    "action": "Acción concreta y medible",
                    "responsible": "Cargo responsable",
                    "deadline_days": 7
                }
            ]
        }
    ]
}
"""


class DecisionIntelligenceEngine:
    """Motor de recomendaciones prescriptivas — Fase 4. Zero-Crash Policy."""

    def __init__(self, config: ConfigurationManager):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.decision_rules = self._load_decision_rules()

        # ── Obtención robusta de credenciales ────────────────────────────────
        def _get_api_key() -> Optional[str]:
            """Lee GROQ_API_KEY desde os.getenv y st.secrets sin colapsar."""
            val = os.getenv("GROQ_API_KEY")
            if not val and st is not None and hasattr(st, "secrets"):
                try:
                    val = st.secrets.get("GROQ_API_KEY")
                except Exception:
                    val = None
            return val

        self.api_key = _get_api_key()

        # ── Cliente Groq (Zero-Crash: ningún error aquí mata el pipeline) ────
        self.client = None
        if self.api_key and Groq is not None:
            try:
                self.client = Groq(api_key=self.api_key)
            except Exception as e:
                self.logger.warning(
                    f"Groq no pudo inicializarse — operando en modo rule-based: {e}"
                )

    # ==========================================================================
    # FALLBACK DE CONTINGENCIA
    # ==========================================================================

    def _get_fallback_response(self, reason: str) -> Dict[str, Any]:
        """
        Retorna una respuesta estructurada de contingencia cuando la IA no está
        disponible. Garantiza que el dashboard no colapse y el usuario recibe
        orientación útil basada en las reglas de negocio predefinidas.

        Args:
            reason: Motivo por el que se activa el fallback (para logging y UI).

        Returns:
            Dict con executive_summary, confidence_level y recommendations.
        """
        return {
            "executive_summary": (
                "El análisis matemático de Monte Carlo se completó exitosamente. "
                "Las proyecciones estadísticas (Escudo 1), el análisis de estrés "
                "macroeconómico (Escudo 2) y las estrategias de optimización "
                "(Escudo 3) están disponibles en sus respectivos paneles. "
                f"La síntesis narrativa de IA está temporalmente offline ({reason}); "
                "las recomendaciones mostradas a continuación son generadas por el "
                "motor de reglas de negocio institucionales de Evangelista & Co."
            ),
            "confidence_level": (
                f"MEDIO — Análisis matemático completo. "
                f"Narrativa IA no disponible: {reason}"
            ),
            "recommendations": [
                {
                    "title": "Revisar Variable de Mayor Exposición",
                    "priority": 1,
                    "description": (
                        "Analice el gráfico tornado de sensibilidad para identificar "
                        "la variable que explica la mayor proporción de la varianza "
                        "en el resultado simulado. Implemente una cobertura o contrato "
                        "forward para neutralizar esa exposición."
                    ),
                    "actions": [
                        {
                            "step": 1,
                            "action": "Revisar análisis tornado y determinar variable crítica",
                            "responsible": "CFO",
                            "deadline_days": 1,
                        },
                        {
                            "step": 2,
                            "action": "Solicitar cotización de cobertura a banco o broker",
                            "responsible": "Gerente de Tesorería",
                            "deadline_days": 5,
                        },
                        {
                            "step": 3,
                            "action": "Presentar estrategia de cobertura a Dirección General",
                            "responsible": "CFO",
                            "deadline_days": 10,
                        },
                    ],
                },
                {
                    "title": "Monitorear Probabilidad de Pérdida",
                    "priority": 2,
                    "description": (
                        "Configure alertas periódicas para rastrear la evolución de la "
                        "probabilidad de pérdida. Si supera el umbral del 25%, active "
                        "el protocolo de contingencia financiera."
                    ),
                    "actions": [
                        {
                            "step": 1,
                            "action": "Establecer umbral de alerta en dashboard (>25% prob_loss)",
                            "responsible": "Consultor Evangelista & Co.",
                            "deadline_days": 3,
                        },
                        {
                            "step": 2,
                            "action": "Definir protocolo de respuesta ante alerta crítica",
                            "responsible": "Dirección General",
                            "deadline_days": 14,
                        },
                    ],
                },
            ],
        }

    # ==========================================================================
    # GENERATE RECOMMENDATIONS — FASE 4 PRINCIPAL
    # ==========================================================================

    def generate_recommendations(
        self, stats: Dict[str, float], sensitivity: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Genera recomendaciones prescriptivas vía IA (Groq/Llama 3).
        Zero-Crash Policy: nunca lanza excepción; en cualquier fallo retorna
        un dict de contingencia estructurado que preserva el dashboard.

        Args:
            stats:       Estadísticas del motor Monte Carlo (p10, p50, p90, prob_loss, var_95, mean).
            sensitivity: DataFrame con columnas 'variable' e 'importance'.

        Returns:
            Dict con executive_summary, confidence_level y recommendations.
        """
        # Guard clause: sin cliente activo no hay llamada a la API
        if not self.client:
            return self._get_fallback_response("API Key faltante o inválida")

        try:
            # ── Construir contexto de datos para el prompt ────────────────────
            top_risks: List[Dict] = []
            if (
                sensitivity is not None
                and not sensitivity.empty
                and "variable" in sensitivity.columns
            ):
                sort_col = "importance" if "importance" in sensitivity.columns else sensitivity.columns[-1]
                top_df = sensitivity.nlargest(3, sort_col)
                top_risks = top_df[["variable", sort_col]].rename(
                    columns={sort_col: "importance"}
                ).to_dict("records")

            context = {
                "cliente": self.config.get("client.name", "Cliente"),
                "industria": self.config.get("client.industry", "General"),
                "estadisticas_monte_carlo": {
                    "p10":       round(stats.get("p10", 0), 2),
                    "p50":       round(stats.get("p50", 0), 2),
                    "p90":       round(stats.get("p90", 0), 2),
                    "mean":      round(stats.get("mean", 0), 2),
                    "prob_loss": round(stats.get("prob_loss", 0), 4),
                    "var_95":    round(stats.get("var_95", 0), 2),
                },
                "top_3_variables_de_riesgo": top_risks,
            }

            # ── Llamada a la API de Groq ──────────────────────────────────────
            response = self.client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[
                    {"role": "system", "content": PROMPT_STRATEGIC_ADVISOR},
                    {
                        "role": "user",
                        "content": (
                            "Genera el análisis estratégico basado en estos datos de simulación:\n"
                            + json.dumps(context, ensure_ascii=False, indent=2)
                        ),
                    },
                ],
                temperature=0.3,
                max_tokens=2048,
                response_format={"type": "json_object"},
            )

            # ── Parsear y validar la respuesta ────────────────────────────────
            raw_content = response.choices[0].message.content
            parsed: Dict[str, Any] = json.loads(raw_content)

            if "executive_summary" not in parsed or "recommendations" not in parsed:
                self.logger.warning(
                    "Respuesta Groq incompleta (faltan llaves obligatorias) — activando fallback."
                )
                return self._get_fallback_response("Respuesta IA incompleta o malformada")

            return parsed

        except Exception as e:
            self.logger.error(
                f"Error en Fase 4 (Decision Intelligence Engine): {e}", exc_info=True
            )
            return self._get_fallback_response(f"Intermitencia IA: {e}")

    # ==========================================================================
    # MÉTODOS RULE-BASED (preservados para compatibilidad y fallbacks internos)
    # ==========================================================================

    def _load_decision_rules(self) -> List[Dict]:
        rules = self.config.get("decision_rules", [])
        if not rules:
            print("⚠️ No hay decision_rules en YAML. Usando reglas default.")
            return self._get_default_rules()
        return rules

    def _get_default_rules(self) -> List[Dict]:
        return [
            {
                "rule_id": "R001_DEFAULT",
                "condition": "prob_loss > 0.15",
                "severity": "ALTO",
                "category": "financial_risk",
                "recommendation_template": (
                    "Probabilidad de pérdida elevada ({prob_loss:.1%}). "
                    "Revisar estructura de costos y estrategia de pricing."
                ),
            }
        ]

    def _evaluate_condition(self, condition: str, stats: Dict) -> bool:
        try:
            return eval(condition, {"__builtins__": {}}, stats)
        except Exception as e:
            print(f"⚠️ Error evaluando condición '{condition}': {e}")
            return False

    def _build_recommendation(
        self,
        rule: Dict,
        stats: Dict,
        primary_driver: str,
        primary_importance: float,
    ) -> Dict:
        rec_template = rule.get("recommendation_template", "")
        description = rec_template.format(
            prob_loss=stats["prob_loss"],
            primary_driver=primary_driver,
            primary_importance=primary_importance,
            **stats,
        )
        return {
            "rule_id":        rule["rule_id"],
            "priority":       self._calculate_priority(rule, stats),
            "category":       rule.get("category", "general"),
            "title":          f"Mitigar Exposición en {primary_driver}",
            "description":    description,
            "actions":        self._generate_action_steps(primary_driver, stats),
            "expected_impact": self._estimate_impact(primary_driver, primary_importance, stats),
        }

    def _calculate_priority(self, rule: Dict, stats: Dict) -> int:
        severity  = rule.get("severity", "MEDIO")
        prob_loss = stats["prob_loss"]
        if severity == "CRÍTICO" or prob_loss > 0.30:
            return 1
        elif severity == "ALTO" or prob_loss > 0.15:
            return 2
        return 3

    def _generate_action_steps(
        self, primary_driver: str, stats: Dict
    ) -> List[Dict]:
        return [
            {
                "step": 1,
                "action": f"Analizar exposición actual en {primary_driver}",
                "responsible": "CFO",
                "deadline_days": 3,
            },
            {
                "step": 2,
                "action": f"Negociar contratos forward para {primary_driver}",
                "responsible": "Gerente de Compras",
                "deadline_days": 14,
            },
            {
                "step": 3,
                "action": "Implementar cobertura y monitorear resultados",
                "responsible": "CFO + Operaciones",
                "deadline_days": 30,
            },
        ]

    def _estimate_impact(
        self, primary_driver: str, importance: float, stats: Dict
    ) -> Dict:
        current_prob_loss    = stats["prob_loss"]
        expected_reduction   = current_prob_loss * importance * 0.5
        expected_savings     = abs(stats["var_95"]) * 0.3
        implementation_cost  = 15_000
        roi = expected_savings / implementation_cost if implementation_cost > 0 else 0
        return {
            "prob_loss_reduction":    expected_reduction,
            "expected_savings_mxn":   expected_savings,
            "implementation_cost_mxn": implementation_cost,
            "roi_estimated":          roi,
        }
