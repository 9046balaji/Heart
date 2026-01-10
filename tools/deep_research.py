"""
Deep Research Tool - Web Search, Crawl, and Synthesis for Agentic RAG System

This module provides advanced research capabilities by combining web search,
web crawling, and content synthesis to answer complex research queries.

This is a compatibility wrapper that imports from the actual implementation
in agents.deep_research_agent.deep_research
"""

# Import from the actual implementation
from agents.deep_research_agent.deep_research import (
    get_search_results,
    deep_crawl_research as crawl_and_extract,
    synthesize_report,
    ResearchInsight
)

__all__ = [
    'get_search_results',
    'crawl_and_extract',
    'synthesize_report',
    'ResearchInsight'
]