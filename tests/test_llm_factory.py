import os
from src.llm.factory import get_llm_client
from src.llm.providers.generic_openai import GenericOpenAIProvider

def test_gemma_local_factory_instantiation():
    # Establecer variable de entorno temporalmente
    os.environ["LOCAL_LLM_URL"] = "http://mock-llm-host:8080/v1"
    
    # Obtener el cliente
    client = get_llm_client("gemma-local")
    
    # Verificar tipo de cliente
    assert isinstance(client, GenericOpenAIProvider)
    assert client.config.name == "gemma-local"
    assert client.config.provider == "openai_generic"
    assert client.config.base_url in ["http://localhost:8080/v1", "http://mock-llm-host:8080/v1"]
    assert client.config.api_key_env == "NONE"
    
    # Limpiar
    del os.environ["LOCAL_LLM_URL"]
