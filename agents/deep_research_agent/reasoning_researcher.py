"""
Reasoning Researcher - Chain-of-Thought Research Agent

Transforms linear research into a thinking, adaptive process.
Uses ThinkingAgent to reason about search strategies and retry on failure.

Performance Optimizations (v2.0):
- Search deduplication to prevent redundant API calls
- Reduced max_thinking_rounds (10 -> 4) for faster response
- Early termination when sufficient results found
- Query normalization for better cache hits
"""


import asyncio
import os
import logging
from typing import List, Dict, Any, Optional, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime
import hashlib

# Import existing components
try:
    from agents.components.thinking import ThinkingAgent, ThinkingResult
    from tools.web_search import VerifiedWebSearchTool
    from .search_tool import get_search_results
    from .crawler_tool import deep_crawl_research
    from .reporter import synthesize_report
    from .models import ResearchInsight
except ImportError:
    # Direct execution fallback
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from agents.components.thinking import ThinkingAgent, ThinkingResult
    from tools.web_search import VerifiedWebSearchTool
    from agents.deep_research_agent.search_tool import get_search_results
    from agents.deep_research_agent.crawler_tool import deep_crawl_research
    from agents.deep_research_agent.reporter import synthesize_report
    from agents.deep_research_agent.models import ResearchInsight

logger = logging.getLogger(__name__)


def _normalize_query(query: str) -> str:
    """Normalize search query for deduplication."""
    # Lowercase, strip whitespace, remove extra spaces
    normalized = ' '.join(query.lower().strip().split())
    return normalized


def _query_hash(query: str) -> str:
    """Create a hash for quick query comparison."""
    return hashlib.md5(_normalize_query(query).encode()).hexdigest()[:12]


@dataclass
class ResearchSession:
    """Tracks a complete research session."""
    query: str
    started_at: datetime = field(default_factory=datetime.utcnow)
    urls_searched: List[str] = field(default_factory=list)
    urls_crawled: List[str] = field(default_factory=list)
    insights: List[Dict] = field(default_factory=list)
    reasoning_trace: str = ""
    final_report: Optional[str] = None
    # v2.0: Track executed queries to prevent duplicates
    _executed_queries: Set[str] = field(default_factory=set)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "started_at": self.started_at.isoformat(),
            "urls_searched": self.urls_searched,
            "urls_crawled": self.urls_crawled,
            "insights_count": len(self.insights),
            "has_report": self.final_report is not None,
            "unique_searches": len(self._executed_queries),
        }
    
    def is_query_executed(self, query: str) -> bool:
        """Check if a query has already been executed."""
        return _query_hash(query) in self._executed_queries
    
    def mark_query_executed(self, query: str) -> None:
        """Mark a query as executed."""
        self._executed_queries.add(_query_hash(query))


class ReasoningResearcher:
    """
    Chain-of-Thought Research Agent.
    
    Instead of blindly searching and crawling, this agent:
    1. Thinks about what to search for
    2. Evaluates search results
    3. Reasons about which URLs to crawl
    4. Reflects on findings and adjusts strategy
    
    v2.0 Performance Improvements:
    - Search deduplication prevents redundant API calls
    - Reduced thinking rounds (10 -> 4) for faster completion
    - Early termination when enough URLs/insights found
    - Better prompt to encourage diverse searches
    
    Example:
        researcher = ReasoningResearcher(llm)
        result = await researcher.research("Latest breakthroughs in quantum computing")
        
        print(result.reasoning_trace)  # See the agent's thinking
        print(result.final_report)     # The synthesized report
    """
    
    # v2.0: Configurable limits
    DEFAULT_MAX_ROUNDS = 4  # Reduced from 10 - usually enough for good results
    MIN_URLS_FOR_COMPLETION = 3  # Early exit threshold
    MAX_URLS_TO_COLLECT = 10  # Don't search forever
    
    def __init__(
        self,
        llm,
        max_thinking_rounds: int = DEFAULT_MAX_ROUNDS,
        verbose: bool = True,
    ):
        """
        Initialize the reasoning researcher.
        
        Args:
            llm: Language model (must support ainvoke)
            max_thinking_rounds: Maximum think-act cycles (default: 4)
            verbose: Log thinking process
        """
        self.llm = llm
        self.max_thinking_rounds = max_thinking_rounds
        self.verbose = verbose
        
        # Initialize search tool
        self.search_tool = VerifiedWebSearchTool(use_cache=True)
        
        # Research session tracking
        self.current_session: Optional[ResearchSession] = None
    
    async def research(self, query: str) -> ResearchSession:
        """
        Conduct intelligent research on a topic.
        
        The agent will:
        1. Analyze the query
        2. Search with reasoning
        3. Select URLs to crawl based on relevance
        4. Extract insights
        5. Synthesize report
        
        Args:
            query: Research topic
            
        Returns:
            ResearchSession with all findings and reasoning
        """
        logger.info(f"🧠 Starting reasoning research: {query}")
        
        self.current_session = ResearchSession(query=query)
        
        # Create tool wrappers that the ThinkingAgent can call
        tools = self._create_research_tools()
        
        # Initialize thinking agent
        agent = ThinkingAgent(
            llm=self.llm,
            tools=tools,
            max_thinking_rounds=self.max_thinking_rounds,
            verbose=self.verbose,
        )
        
        # Research prompt - v2.0: Encourage diverse searches, mention deduplication
        research_prompt = f"""You are an expert research assistant. Your task is to conduct thorough research on:

"{query}"

Available tools:
1. perform_search(query, search_pdfs) - Search the web for articles or PDFs
2. perform_deep_crawl(urls, question) - Crawl specific URLs to extract information
3. finalize_research(summary) - Complete the research with final summary

IMPORTANT RULES:
- Do NOT repeat the same search query - each search must be DIFFERENT
- After finding good URLs, use perform_deep_crawl to extract information
- If you have collected enough information (3+ good sources), call finalize_research
- Vary your search queries: try different keywords, angles, or add "recent" / "2024"

Research Strategy:
1. Start with a focused search on the main topic
2. If you need more, search with DIFFERENT keywords or angles
3. Select 2-3 relevant URLs and crawl them for details
4. Once you have useful findings, summarize and finalize

Begin your research now."""

        # Run the thinking agent
        result = await agent.run(research_prompt)
        
        # Store reasoning trace
        self.current_session.reasoning_trace = result.get_reasoning_trace()
        
        # Generate final report if not already done
        if not self.current_session.final_report:
            self.current_session.final_report = self._synthesize_final_report()
        
        logger.info(f"✅ Research complete: {len(self.current_session.insights)} insights")
        
        return self.current_session
    
    def _create_research_tools(self) -> List[Callable]:
        """Create tool functions for the ThinkingAgent."""
        
        async def perform_search(query: str, search_pdfs: bool = False) -> str:
            """
            Search the web for articles or academic papers.
            
            Args:
                query: Search query (must be DIFFERENT from previous searches)
                search_pdfs: If True, search specifically for PDF papers
                
            Returns:
                Summary of search results with URLs
            """
            # v2.0: Check for duplicate query
            if self.current_session.is_query_executed(query):
                logger.info(f"🔄 Skipping duplicate search: '{query[:50]}...'")
                return (
                    f"⚠️ This search query was already executed. "
                    f"You have {len(self.current_session.urls_searched)} URLs collected. "
                    f"Please try a DIFFERENT search query with new keywords, "
                    f"or use perform_deep_crawl to extract information from existing URLs, "
                    f"or call finalize_research if you have enough information."
                )
            
            # v2.0: Check if we have enough URLs already
            if len(self.current_session.urls_searched) >= self.MAX_URLS_TO_COLLECT:
                return (
                    f"✅ Already collected {len(self.current_session.urls_searched)} URLs. "
                    f"Please use perform_deep_crawl to extract insights, "
                    f"or call finalize_research to complete."
                )
            
            try:
                # Mark query as executed
                self.current_session.mark_query_executed(query)
                
                urls = await get_search_results(
                    query, 
                    max_results=5, 
                    search_pdfs=search_pdfs
                )
                
                self.current_session.urls_searched.extend(urls)
                
                if urls:
                    result = f"Found {len(urls)} URLs (total collected: {len(self.current_session.urls_searched)}):\n"
                    for i, url in enumerate(urls, 1):
                        type_label = "[PDF]" if url.lower().endswith(".pdf") else "[WEB]"
                        result += f"  {i}. {type_label} {url}\n"
                    
                    # v2.0: Hint for early completion
                    if len(self.current_session.urls_searched) >= self.MIN_URLS_FOR_COMPLETION:
                        result += f"\n💡 You have enough URLs. Consider using perform_deep_crawl or finalize_research."
                    
                    return result
                else:
                    return "No results found. Try a different search query with different keywords."
                    
            except Exception as e:
                return f"Search error: {e}. Try a different approach."
        
        async def perform_deep_crawl(urls: str, question: str) -> str:
            """
            Crawl specific URLs to extract detailed information.
            
            Args:
                urls: Comma-separated URLs to crawl
                question: Specific question to answer from the content
                
            Returns:
                Extracted insights from the URLs
            """
            try:
                url_list = [u.strip() for u in urls.split(",")]
                
                insights = await deep_crawl_research(
                    seed_urls=url_list,
                    extraction_prompt=question,
                    max_depth=1
                )
                
                self.current_session.urls_crawled.extend(url_list)
                
                if insights:
                    result = f"Extracted {len(insights)} insights:\n\n"
                    for insight in insights[:5]:  # Limit to 5 for context window
                        self.current_session.insights.append({
                            "url": insight.url,
                            "summary": insight.summary,
                            "key_points": insight.key_points,
                        })
                        result += f"**From {insight.url}:**\n"
                        result += f"Summary: {insight.summary[:500]}...\n"
                        if insight.key_points:
                            result += f"Key points: {', '.join(insight.key_points[:3])}\n"
                        result += "\n"
                    return result
                else:
                    return "No insights extracted. The URLs may be inaccessible or empty."
                    
            except Exception as e:
                return f"Crawl error: {e}. Try different URLs."
        
        async def finalize_research(summary: str) -> str:
            """
            Complete the research with a final summary.
            
            Args:
                summary: Your synthesis of all findings
                
            Returns:
                Confirmation that research is complete
            """
            self.current_session.final_report = summary
            return "Research finalized. Summary saved."
        
        # Set function metadata for ThinkingAgent
        perform_search.__name__ = "perform_search"
        perform_search.name = "perform_search"
        perform_search.description = "Search the web for articles or PDFs related to the research topic"
        
        perform_deep_crawl.__name__ = "perform_deep_crawl"
        perform_deep_crawl.name = "perform_deep_crawl"
        perform_deep_crawl.description = "Crawl specific URLs to extract detailed information"
        
        finalize_research.__name__ = "finalize_research"
        finalize_research.name = "finalize_research"
        finalize_research.description = "Complete the research with a final summary"
        
        return [perform_search, perform_deep_crawl, finalize_research]
    
    def _synthesize_final_report(self) -> str:
        """Generate final report from collected insights."""
        if not self.current_session.insights:
            return "No insights were collected during research."
        
        report_lines = [
            f"# Research Report: {self.current_session.query}",
            f"\n*Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}*\n",
            f"## Summary\n",
            f"Analyzed {len(self.current_session.urls_crawled)} sources.\n",
            f"## Key Findings\n",
        ]
        
        for i, insight in enumerate(self.current_session.insights, 1):
            report_lines.append(f"### Finding {i}")
            report_lines.append(f"**Source:** {insight['url']}\n")
            report_lines.append(insight['summary'][:1000])
            if insight.get('key_points'):
                report_lines.append("\n**Key Points:**")
                for point in insight['key_points'][:5]:
                    report_lines.append(f"- {point}")
            report_lines.append("\n")
        
        report_lines.append("## Reasoning Trace")
        report_lines.append("```")
        report_lines.append(self.current_session.reasoning_trace[:5000])
        report_lines.append("```")
        
        return "\n".join(report_lines)


# =============================================================================
# Convenience Function
# =============================================================================

async def run_reasoning_research(query: str, llm=None) -> ResearchSession:
    """
    Run reasoning research with default configuration.
    
    Args:
        query: Research topic
        llm: Optional LLM (will use default if not provided)
        
    Returns:
        ResearchSession with results
    """
    if llm is None:
        # Try to get default LLM
        try:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        except ImportError:
            raise ValueError("No LLM provided and langchain_openai not available")
    
    researcher = ReasoningResearcher(llm=llm)
    return await researcher.research(query)
