"""Filtros de metadata para búsqueda segura en Qdrant."""
from qdrant_client.models import Filter, FieldCondition, MatchAny, MatchValue


def build_agent_filter(agent_name: str) -> Filter:
    """
    Construye el filtro de seguridad por agente.
    Un agente solo ve documentos donde agent_access incluye su nombre o 'all'.
    Este filtro es OBLIGATORIO en toda búsqueda.
    """
    return Filter(
        must=[
            FieldCondition(
                key="agent_access",
                match=MatchAny(any=[agent_name, "all"]),
            )
        ]
    )


def build_domain_filter(domains: list[str]) -> Filter:
    """Filtro adicional por dominio funcional (finanzas, procesos, datos, etc.)."""
    return Filter(
        must=[
            FieldCondition(
                key="domain",
                match=MatchAny(any=domains),
            )
        ]
    )


def build_sector_filter(sectors: list[str]) -> Filter:
    """Filtro adicional por sector (manufactura, textiles, retail, etc.)."""
    return Filter(
        must=[
            FieldCondition(
                key="sector",
                match=MatchAny(any=sectors),
            )
        ]
    )


def build_type_filter(types: list[str]) -> Filter:
    """Filtro por tipo de documento (framework, formula, case, playbook, etc.)."""
    return Filter(
        must=[
            FieldCondition(
                key="type",
                match=MatchAny(any=types),
            )
        ]
    )


def combine_filters(*filters: Filter) -> Filter:
    """Combina múltiples filtros con AND lógico (todos deben cumplirse)."""
    all_conditions = []
    for f in filters:
        if f.must:
            all_conditions.extend(f.must)
    return Filter(must=all_conditions)
