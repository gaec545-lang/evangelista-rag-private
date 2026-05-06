"""Logging estructurado con structlog para el pipeline RAG."""
import structlog
import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    """Configura structlog con formato legible para desarrollo."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Retorna un logger con contexto del módulo solicitado."""
    configure_logging()
    return structlog.get_logger(name)
