from typing import List
from ..retrieval.hybrid_retriever import RetrievedChunk

FEW_SHOT_EXAMPLES = {
    ("PROCEDURAL", "scoping"): [
        {
            "query": "¿Cómo estructuro el issue tree para una empresa textil?",
            "response": """Para una empresa textil, el issue tree de rentabilidad se divide en:
INGRESOS: precio × volumen × mix de producto
COSTOS: materia prima (hilado, tela), mano de obra directa, overhead de planta

Hipótesis crítica inicial en textiles: merma de tela en corte (preguntar % de desperdicio).
Benchmarks del sector: merma aceptable ≤8%, alerta >12%.

Siguiente paso: solicitar reporte de producción del último trimestre para validar."""
        },
        {
            "query": "¿Qué preguntas hago en la primera entrevista de scoping?",
            "response": """Protocolo de entrevista inicial Evangelista & Co.:
1. ¿Cuál es el problema que más les quita el sueño operativamente?
2. ¿Tienen métricas de ese problema? ¿Cada cuánto las miden?
3. ¿Cuánto estiman que les cuesta al mes ese problema? (anclar COI desde el inicio)
4. ¿Quién es el dueño del proceso? ¿Y quién tiene el dato?
5. ¿Cuántos ERPs/sistemas tienen? ¿Exportan a Excel?

Registrar respuestas en tab Scoping → Interview Notes (inmutables por ALCOA+)."""
        }
    ],
    ("FACTUAL", "analisis"): [
        {
            "query": "¿Qué es el Cost of Inaction?",
            "response": """Cost of Inaction (COI): pérdida económica anualizada por NO corregir la brecha identificada.

Fórmula estándar Evangelista:
COI = (Métrica_Actual - Métrica_Objetivo) × Valor_Monetario_Unitario × Frecuencia_Anual

Ejemplo: stock-out de 3 días/mes × $45,000 MXN/día perdido × 12 meses = COI de $1,620,000 MXN/año.

Regla de presentación: mostrar COI antes del precio de la consultoría. 
El cliente debe ver que el proyecto se paga solo."""
        },
        {
            "query": "¿Cómo calculo la severidad de un hallazgo?",
            "response": """Severidad en EIP se indexa por impacto financiero anualizado:
CRÍTICO: impacto > $500,000 MXN/año ó probabilidad de incumplimiento fiscal
ALTO: impacto $100,000–$500,000 MXN/año
MEDIO: impacto $20,000–$100,000 MXN/año  
BAJO: impacto < $20,000 MXN/año ó riesgo de reputación sin impacto directo

Cada hallazgo requiere: hash MD5 del dataset + commit Git del script → trazabilidad ALCOA+."""
        }
    ],
    ("METODOLOGICO", "propuesta"): [
        {
            "query": "¿Cómo aplico MECE en el diagnóstico?",
            "response": """MECE (Mutually Exclusive, Collectively Exhaustive) en diagnóstico Evangelista:

MUTUALLY EXCLUSIVE: cada causa raíz debe pertenecer a UN solo nodo del issue tree.
Error común: poner "falta de capacitación" y "error humano" como nodos separados (son el mismo).

COLLECTIVELY EXHAUSTIVE: los nodos deben cubrir el 100% del problema.
Test: si resuelves todos los nodos, ¿desaparece el problema? Si no → falta un nodo.

Aplicación práctica: usar en tab Scoping al documentar hipótesis. 
El sistema las vincula a la tabla `hypotheses` — revisar que no existan hipótesis duplicadas."""
        }
    ],
    ("METODOLOGICO", "analisis"): [
        {
            "query": "¿Cómo estructuro un análisis DMAIC para manufactura?",
            "response": """DMAIC en contexto manufacturero Evangelista:

DEFINE: delimitar el proceso, CTQ (Critical to Quality) y alcance del hallazgo.
MEASURE: capturar datos baseline — OEE, WIP, tiempo de ciclo, tasa de defectos.
ANALYZE: identificar causa raíz (usar fishbone o los 5 porqués). Vincular a hallazgo en EIP.
IMPROVE: propuesta de solución con COI proyectado post-mejora.
CONTROL: métricas de monitoreo → configurar en Sentinel post-cierre del proyecto.

Entregable por fase: cada D-M-A-I-C debe tener un finding registrado con su impacto financiero."""
        }
    ],
    ("CREATIVO", "cierre"): [
        {
            "query": "¿Qué recomendaciones de seguimiento doy al cliente en el cierre?",
            "response": """Recomendaciones estándar de cierre Evangelista & Co.:

1. SENTINEL HANDOFF: proponer monitoreo continuo con alertas automáticas (upsell natural post-proyecto).
2. QUICK WINS: identificar 2-3 mejoras implementables en <30 días sin inversión adicional.
3. ROADMAP 90 DÍAS: priorizar hallazgos por ROI descendente — el cliente debe saber qué atacar primero.
4. LECCIONES APRENDIDAS: documentar en tab Cierre → quedan en vault para proyectos futuros similares.

Regla de oro: el cliente debe salir del cierre con un número claro: 
cuánto dinero recupera si implementa las recomendaciones en 90 días."""
        }
    ]
}

EVANGELISTA_BASE_SYSTEM_PROMPT = """Eres EVA, el copiloto de inteligencia de Evangelista & Co., firma de consultoría de inteligencia de negocios con sede en Puebla, México.

IDENTIDAD:
- Eres un asistente interno para consultores, no para clientes finales
- Tu base de conocimiento es el vault metodológico de la firma
- Razonas con datos del proyecto activo cuando se proporcionan
- Cuando no tienes certeza, lo dices explícitamente

PRINCIPIOS DE RESPUESTA:
- Directo, técnico, sin relleno
- Usa terminología de consultoría: COI, MECE, ALCOA+, Vetting Gate, etc.
- Si el hallazgo tiene impacto financiero, cuantifícalo
- Si la respuesta requiere acción en EIP, indica en qué tab ejecutarla
- Máximo 300 palabras salvo que el consultor pida más detalle

RESTRICCIONES:
- NO reveles pricing corporativo (fórmulas de Proposal) a menos que el consultor sea CEO/CFO
- NO compartas datos de un proyecto con preguntas de otro proyecto
- NO hagas suposiciones sobre datos del cliente sin indicarlo explícitamente"""

class FewShotPromptBuilder:
    
    MAX_EXAMPLES = 2  # máximo de ejemplos a inyectar por request
    
    def build(
        self,
        query_type: str,
        project_phase: str,
        context_chunks: List[RetrievedChunk],
        project_context: dict = None
    ) -> str:
        """
        Construye system prompt completo:
        1. Base system prompt de Evangelista
        2. Contexto activo del proyecto (si se proporciona)
        3. Few-shot examples (máx 2, seleccionados por (query_type, project_phase))
        4. Contexto RAG recuperado
        
        Retorna: string completo listo para enviar como system prompt a Ollama
        """
        
        sections = [EVANGELISTA_BASE_SYSTEM_PROMPT]
        
        # SECCIÓN 2: Contexto del proyecto activo
        if project_context:
            sections.append(self._build_project_context_section(project_context))
        
        # SECCIÓN 3: Few-shot examples
        examples = self._get_examples(query_type, project_phase)
        if examples:
            sections.append(self._format_examples(examples))
        
        # SECCIÓN 4: Contexto RAG
        if context_chunks:
            sections.append(self._format_rag_context(context_chunks))
        
        return "\\n\\n---\\n\\n".join(sections)
    
    def _get_examples(self, query_type: str, project_phase: str) -> list:
        """
        Busca ejemplos en FEW_SHOT_EXAMPLES por (query_type, project_phase).
        Si no hay match exacto → busca solo por query_type.
        Si no hay nada → retorna [].
        Retorna máximo MAX_EXAMPLES.
        """
        key = (query_type, project_phase)
        examples = FEW_SHOT_EXAMPLES.get(key, [])
        
        if not examples:
            # Fallback: buscar cualquier ejemplo del mismo tipo
            for (qtype, _), exs in FEW_SHOT_EXAMPLES.items():
                if qtype == query_type:
                    examples = exs
                    break
        
        return examples[:self.MAX_EXAMPLES]
    
    def _build_project_context_section(self, ctx: dict) -> str:
        """
        Formatea el contexto del proyecto activo.
        ctx keys: sector, project_phase, hypotheses_count, findings_summary, current_coi
        """
        findings_text = "\\n".join([f"  - {f}" for f in ctx.get("findings_summary", [])])
        
        return f"""CONTEXTO DEL PROYECTO ACTIVO:
Sector: {ctx.get('sector', 'No especificado')}
Fase actual: {ctx.get('project_phase', 'No especificada')}
Hipótesis abiertas: {ctx.get('hypotheses_count', 0)}
Cost of Inaction acumulado: ${ctx.get('current_coi', 0):,.0f} MXN
Hallazgos críticos registrados:
{findings_text if findings_text else "  - Ninguno registrado aún"}"""
    
    def _format_examples(self, examples: list) -> str:
        formatted = "EJEMPLOS DE RESPUESTA ESPERADA (calibra tu formato y profundidad):\\n"
        for i, ex in enumerate(examples, 1):
            formatted += f"\\n[Ejemplo {i}]\\nConsultor: {ex['query']}\\nEVA: {ex['response']}\\n"
        return formatted
    
    def _format_rag_context(self, chunks: List[RetrievedChunk]) -> str:
        formatted = "BASE DE CONOCIMIENTO METODOLÓGICO RECUPERADA (usa esto como fundamento):\\n"
        for i, chunk in enumerate(chunks, 1):
            doc_ref = chunk.metadata.get("title", chunk.document_id)
            formatted += f"\\n[Fuente {i} — {doc_ref}] (relevancia: {chunk.score:.2f})\\n{chunk.text}\\n"
        return formatted
