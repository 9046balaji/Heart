"""
Reasoning Researcher - Chain-of-Thought Research Agent

Transforms linear research into a thinking, adaptive process.
Uses ThinkingAgent to reason about search strategies and retry on failure.
"""

import asyncio
import os
import logging
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

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
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "started_at": self.started_at.isoformat(),
            "urls_searched": self.urls_searched,
            "urls_crawled": self.urls_crawled,
            "insights_count": len(self.insights),
            "has_report": self.final_report is not None,
        }


class ReasoningResearcher:
    """
    Chain-of-Thought Research Agent.
    
    Instead of blindly searching and crawling, this agent:
    1. Thinks about what to search for
    2. Evaluates search results
    3. Reasons about which URLs to crawl
    4. Reflects on findings and adjusts strategy
    
    Example:
        researcher = ReasoningResearcher(llm)
        result = await researcher.research("Latest breakthroughs in quantum computing")
        
        print(result.reasoning_trace)  # See the agent's thinking
        print(result.final_report)     # The synthesized report
    """
    
    def __init__(
        self,
        llm,
        max_thinking_rounds: int = 10,
        verbose: bool = True,
    ):
        """
        Initialize the reasoning researcher.
        
        Args:
            llm: Language model (must support ainvoke)
            max_thinking_rounds: Maximum think-act cycles
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
        
        # Research prompt
        research_prompt = f"""You are an expert research assistant. Your task is to conduct thorough research on:

"{query}"

Available tools:
1. perform_search(query, search_pdfs) - Search the web for articles or PDFs
2. perform_deep_crawl(urls, question) - Crawl specific URLs to extract information
3. finalize_research(summary) - Complete the research with final summary

Research Strategy:
1. Start with a broad search to understand the landscape
2. If results are poor, refine your search query
3. Select the most relevant URLs to crawl
4. Extract key findings
5. If you find references to important papers, search for them
6. When you have enough information, finalize with a summary

Think carefully before each action. Explain your reasoning.
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
                query: Search query
                search_pdfs: If True, search specifically for PDF papers
                
            Returns:
                Summary of search results with URLs
            """
            try:
                urls = await get_search_results(
                    query, 
                    max_results=5, 
                    search_pdfs=search_pdfs
                )
                
                self.current_session.urls_searched.extend(urls)
                
                if urls:
                    result = f"Found {len(urls)} URLs:\n"
                    for i, url in enumerate(urls, 1):
                        type_label = "[PDF]" if url.lower().endswith(".pdf") else "[WEB]"
                        result += f"  {i}. {type_label} {url}\n"
                    return result
                else:
                    return "No results found. Try a different search query."
                    
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
