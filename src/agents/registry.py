from .base import BaseAgent

class AgentRegistry:
    """Registro dinámico de agentes. Agregar un agente = 1 línea."""
    _agents: dict[str, BaseAgent] = {}

    @classmethod
    def register(cls, agent: BaseAgent):
        if agent.name in cls._agents:
            # En lugar de error, logeamos y saltamos para evitar fallos en hot-reload
            return
        cls._agents[agent.name] = agent

    @classmethod
    def get(cls, name: str) -> BaseAgent:
        if name not in cls._agents:
            raise ValueError(f"Agente '{name}' no registrado. Disponibles: {list(cls._agents.keys())}")
        return cls._agents[name]

    @classmethod
    def list_agents(cls) -> list[str]:
        return list(cls._agents.keys())

    @classmethod
    def get_agent_for_domain(cls, domain: str) -> list[BaseAgent]:
        """Retorna todos los agentes que cubren un dominio."""
        return [a for a in cls._agents.values() if domain in a.domains]
