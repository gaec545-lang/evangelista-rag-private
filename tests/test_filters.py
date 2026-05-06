"""Tests para los filtros de seguridad del retrieval."""
import pytest
from qdrant_client.models import Filter, FieldCondition, MatchAny

from src.retrieval.filters import (
    build_agent_filter,
    build_domain_filter,
    build_sector_filter,
    build_type_filter,
    combine_filters,
)


class TestFilters:
    def test_agent_filter_structure(self):
        f = build_agent_filter("financial")
        assert isinstance(f, Filter)
        assert f.must is not None
        assert len(f.must) == 1
        condition = f.must[0]
        assert isinstance(condition, FieldCondition)
        assert condition.key == "agent_access"
        assert isinstance(condition.match, MatchAny)
        assert "financial" in condition.match.any
        assert "all" in condition.match.any

    def test_agent_filter_includes_all(self):
        """El filtro de agente SIEMPRE incluye 'all' además del nombre del agente."""
        for agent in ["financial", "process", "data_eng", "analyst"]:
            f = build_agent_filter(agent)
            condition = f.must[0]
            assert "all" in condition.match.any
            assert agent in condition.match.any

    def test_domain_filter_structure(self):
        f = build_domain_filter(["finanzas", "procesos"])
        assert isinstance(f, Filter)
        condition = f.must[0]
        assert condition.key == "domain"
        assert "finanzas" in condition.match.any
        assert "procesos" in condition.match.any

    def test_sector_filter_structure(self):
        f = build_sector_filter(["textiles", "manufactura"])
        assert isinstance(f, Filter)
        condition = f.must[0]
        assert condition.key == "sector"
        assert "textiles" in condition.match.any

    def test_type_filter_structure(self):
        f = build_type_filter(["framework", "formula"])
        condition = f.must[0]
        assert condition.key == "type"

    def test_combine_filters_and_logic(self):
        """combine_filters debe combinar condiciones con AND."""
        f1 = build_agent_filter("financial")
        f2 = build_domain_filter(["finanzas"])
        combined = combine_filters(f1, f2)
        assert len(combined.must) == 2

    def test_combine_three_filters(self):
        f1 = build_agent_filter("analyst")
        f2 = build_domain_filter(["datos"])
        f3 = build_sector_filter(["textiles"])
        combined = combine_filters(f1, f2, f3)
        assert len(combined.must) == 3

    def test_agent_filter_all_agent(self):
        """El agente 'all' debe poder ver todos los documentos."""
        f = build_agent_filter("all")
        condition = f.must[0]
        assert "all" in condition.match.any
