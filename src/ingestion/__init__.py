"""Módulo de ingestión: parsing, chunking, embedding e indexación."""
from .parser import MarkdownParser
from .chunker import SemanticChunker
from .embedder import Embedder
from .indexer import Indexer

__all__ = ["MarkdownParser", "SemanticChunker", "Embedder", "Indexer"]
