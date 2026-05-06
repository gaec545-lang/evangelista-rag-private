import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

@dataclass
class LLMModelConfig:
    name: str
    provider: str
    model_id: str
    api_key_env: str
    base_url: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 4096
    extra_params: Dict[str, Any] = field(default_factory=dict)

# Configuración de proveedores y modelos
MODELS: Dict[str, LLMModelConfig] = {
    # GROQ (Alta velocidad, limitado)
    "groq-llama-70b": LLMModelConfig(
        name="groq-llama-70b",
        provider="groq",
        model_id="llama-3.3-70b-versatile",
        api_key_env="GROQ_API_KEY",
        base_url="https://api.groq.com/openai/v1"
    ),
    
    # GROQ 8B (Mayor límite de velocidad en free tier)
    "groq-llama-8b": LLMModelConfig(
        name="groq-llama-8b",
        provider="groq",
        model_id="llama-3.1-8b-instant",
        api_key_env="GROQ_API_KEY",
        base_url="https://api.groq.com/openai/v1"
    ),
    
    # SAMBANOVA (Cloud rápido)
    "sambanova-llama": LLMModelConfig(
        name="sambanova-llama",
        provider="openai_generic",
        model_id="Meta-Llama-3.1-70B-Instruct",
        api_key_env="SAMBANOVA_API_KEY",
        base_url="https://api.sambanova.ai/v1"
    ),
    
    # TOGETHER AI
    "together-llama": LLMModelConfig(
        name="together-llama",
        provider="openai_generic",
        model_id="meta-llama/Llama-3.3-70B-Instruct-Turbo",
        api_key_env="TOGETHER_API_KEY",
        base_url="https://api.together.xyz/v2"
    ),
    
    # CEREBRAS
    "cerebras-llama": LLMModelConfig(
        name="cerebras-llama",
        provider="openai_generic",
        model_id="llama3.1-70b",
        api_key_env="CEREBRAS_API_KEY",
        base_url="https://api.cerebras.ai/v1"
    ),

    # OLLAMA (Local)
    "ollama-local": LLMModelConfig(
        name="ollama-local",
        provider="ollama",
        model_id="llama3.1",
        api_key_env="NONE",
        base_url="http://localhost:11434/v1"
    ),

    # KIMI (Moonshot AI) — Pro Logic & Long Context
    "kimi": LLMModelConfig(
        name="kimi",
        provider="openai_generic",
        model_id="moonshot-v1-32k",
        api_key_env="KIMI_API_KEY",
        base_url="https://api.moonshot.cn/v1",
        temperature=0.3
    ),

    # DEEPSEEK — High Performance Code & Reasoning
    "deepseek": LLMModelConfig(
        name="deepseek",
        provider="openai_generic",
        model_id="deepseek-chat",
        api_key_env="DEEPSEEK_API_KEY",
        base_url="https://api.deepseek.com",
        temperature=0.1
    ),
}

def get_model_config(name: str) -> LLMModelConfig:
    """Retorna la configuración de un modelo por su nombre corto."""
    if name not in MODELS:
        # Default a Groq si no se especifica
        return MODELS["groq-llama-70b"]
    return MODELS[name]
