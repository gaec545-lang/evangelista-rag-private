# -*- coding: utf-8 -*-
"""Agents package initialization.
Imports specialist agents to ensure they are auto‑registered with AgentRegistry.
"""
from .base import BaseAgent
from .registry import AgentRegistry
from .financial import FinancialAgent
from .process import ProcessAgent
from .data_engineer import DataEngineerAgent

__all__ = ["AgentRegistry"]
