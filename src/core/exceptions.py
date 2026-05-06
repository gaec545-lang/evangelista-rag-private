"""Excepciones custom de la plataforma."""

class EIPError(Exception):
    """Error base de Evangelista Intelligence Platform."""
    pass

class AgentNotFoundError(EIPError):
    """Agente no registrado."""
    pass

class RAGSearchError(EIPError):
    """Error en búsqueda RAG."""
    pass

class LLMProviderError(EIPError):
    """Error del provider LLM."""
    pass

class VaultParsingError(EIPError):
    """Error parseando documento del vault."""
    pass
