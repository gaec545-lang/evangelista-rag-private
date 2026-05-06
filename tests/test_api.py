"""Tests de la API FastAPI."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from src.graph.state import GraphState


@pytest.fixture
def mock_state():
    """Estado de orquestador simulado para tests de API."""
    return GraphState(
        question="Analiza la empresa XYZ",
        context={},
        documents=[],
        generation="Análisis financiero completo.",
        final_response="Resumen ejecutivo de la empresa XYZ.",
        confidence=0.85,
        execution_time_ms=1200,
        node_history=["router", "retriever", "generator"],
        errors=[],
    )


@pytest.fixture
def app_with_mocked_agents():
    """App FastAPI con agentes mock registrados."""
    from src.api.server import app
    from src.agents.registry import AgentRegistry

    mock_agent = MagicMock()
    mock_agent.name = "financial"
    mock_agent.domains = ["finanzas", "pricing"]
    mock_agent.tools = ["rag_query", "calculate"]

    mock_result = MagicMock()
    mock_result.confidence = 0.9
    mock_result.analysis = "Análisis de prueba"
    mock_result.recommendations = ["Recomendación 1"]
    mock_result.sources_used = ["source-1"]
    mock_result.escalation_needed = False
    mock_result.escalation_reason = None
    mock_agent.execute = AsyncMock(return_value=mock_result)

    AgentRegistry._agents = {"financial": mock_agent}
    return app


# --- Tests de health ---

class TestHealthEndpoints:
    @pytest.mark.asyncio
    async def test_health_returns_200(self, app_with_mocked_agents):
        async with AsyncClient(
            transport=ASGITransport(app=app_with_mocked_agents), base_url="http://test"
        ) as client:
            response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "evangelista-intelligence-platform"

    @pytest.mark.asyncio
    async def test_readiness_returns_checks(self, app_with_mocked_agents):
        async with AsyncClient(
            transport=ASGITransport(app=app_with_mocked_agents), base_url="http://test"
        ) as client:
            response = await client.get("/readiness")

        data = response.json()
        assert "checks" in data
        assert "ready" in data
        assert "agents" in data["checks"]


# --- Tests del endpoint de análisis ---

class TestAnalyzeEndpoint:
    @pytest.mark.asyncio
    async def test_analyze_returns_response(self, app_with_mocked_agents, mock_state):
        with patch("src.api.routes.analyze.run_graph", AsyncMock(return_value=mock_state)):
            async with AsyncClient(
                transport=ASGITransport(app=app_with_mocked_agents), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/analyze",
                    json={"task": "Analiza la empresa XYZ", "context": {}},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["response"] == "Resumen ejecutivo de la empresa XYZ."
        assert data["confidence"] == 0.85
        assert data["execution_time_ms"] == 1200

    @pytest.mark.asyncio
    async def test_analyze_requires_task(self, app_with_mocked_agents):
        async with AsyncClient(
            transport=ASGITransport(app=app_with_mocked_agents), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/analyze", json={"context": {}})

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_analyze_task_too_short(self, app_with_mocked_agents):
        async with AsyncClient(
            transport=ASGITransport(app=app_with_mocked_agents), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/analyze", json={"task": "abc"})

        assert response.status_code == 422


# --- Tests de agentes ---

class TestAgentsEndpoints:
    @pytest.mark.asyncio
    async def test_list_agents_returns_financial(self, app_with_mocked_agents):
        async with AsyncClient(
            transport=ASGITransport(app=app_with_mocked_agents), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/agents")

        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert any(a["name"] == "financial" for a in data["agents"])

    @pytest.mark.asyncio
    async def test_execute_agent_direct(self, app_with_mocked_agents):
        async with AsyncClient(
            transport=ASGITransport(app=app_with_mocked_agents), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/agents/financial/execute",
                json={"task": "Calcula el ROI del proyecto"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["agent"] == "financial"
        assert "confidence" in data
        assert "analysis" in data

    @pytest.mark.asyncio
    async def test_execute_unknown_agent_returns_404(self, app_with_mocked_agents):
        async with AsyncClient(
            transport=ASGITransport(app=app_with_mocked_agents), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/agents/nonexistent/execute",
                json={"task": "algo"},
            )

        assert response.status_code == 404
