"""
Web Search Tool for Medical AI Assistant.

SAFETY: Only searches verified medical domains.
USAGE: Fallback when internal RAG has low confidence.

⚠️ WARNING: Results are SUPPLEMENTARY, not authoritative.
All responses must include citations and disclaimers.
"""

import os
import logging
import hashlib
import time
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache

logger = logging.getLogger(__name__)

# Attempt Tavily import
try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False
    logger.warning("Tavily not installed. Run: pip install tavily-python")


@dataclass
class WebSearchResult:
    """Single web search result."""
    title: str
    url: str
    content: str
    domain: str
    score: float


@dataclass 
class WebSearchResponse:
    """Complete search response with metadata."""
    results: List[WebSearchResult]
    query: str
    search_timestamp: str
    domains_searched: List[str]
    disclaimer: str


class VerifiedWebSearchTool:
    """
    Web search restricted to verified medical domains.
    
    Usage:
        tool = VerifiedWebSearchTool()
        response = tool.search("latest FDA approval heart medication 2024")
        
        for result in response.results:
            print(f"[{result.domain}] {result.title}")
            print(f"  {result.content[:200]}...")
    """
    
    # Whitelisted medical domains
    VERIFIED_DOMAINS: List[str] = [
        "cdc.gov",
        "nih.gov",
        "fda.gov",
        "who.int",
        "heart.org",
        "pubmed.ncbi.nlm.nih.gov",
        "mayoclinic.org",
        "clevelandclinic.org",
        "hopkinsmedicine.org",
        "medlineplus.gov",
    ]
    
    DISCLAIMER = (
        "⚠️ DISCLAIMER: This information is from external web sources and "
        "is provided for educational purposes only. Always consult a "
        "healthcare professional before making medical decisions."
    )
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize web search tool.
        
        Args:
            api_key: Tavily API key (or use TAVILY_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        
        if not TAVILY_AVAILABLE:
            raise ImportError("Tavily not installed")
        
        if not self.api_key:
            raise ValueError("TAVILY_API_KEY not set")
        
        self.client = TavilyClient(api_key=self.api_key)
        logger.info("VerifiedWebSearchTool initialized")
    
    def search(
        self,
        query: str,
        max_results: int = 5,
        include_domains: Optional[List[str]] = None
    ) -> WebSearchResponse:
        """
        Search verified medical sources.
        
        Args:
            query: Search query (will be scrubbed of PII)
            max_results: Maximum results to return
            include_domains: Override default verified domains
            
        Returns:
            WebSearchResponse with results and metadata
        """
        # Scrub PII from query before external call
        scrubbed_query = self._scrub_pii(query)
        
        # Use whitelist domains
        domains = include_domains or self.VERIFIED_DOMAINS
        
        logger.info(f"Web search: '{scrubbed_query[:50]}...' on {len(domains)} domains")
        
        try:
            # Tavily search with domain restriction
            response = self.client.search(
                query=scrubbed_query,
                search_depth="advanced",
                include_domains=domains,
                max_results=max_results
            )
            
            results = []
            for item in response.get("results", []):
                result = WebSearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    content=item.get("content", ""),
                    domain=self._extract_domain(item.get("url", "")),
                    score=item.get("score", 0.0)
                )
                results.append(result)
            
            return WebSearchResponse(
                results=results,
                query=scrubbed_query,
                search_timestamp=datetime.utcnow().isoformat(),
                domains_searched=domains,
                disclaimer=self.DISCLAIMER
            )
            
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return WebSearchResponse(
                results=[],
                query=scrubbed_query,
                search_timestamp=datetime.utcnow().isoformat(),
                domains_searched=domains,
                disclaimer=self.DISCLAIMER
            )
    
    def _scrub_pii(self, text: str) -> str:
        """
        Remove PII before sending to external API.
        
        Uses multi-layer approach:
        1. Primary: NER-based detection (Presidio/Spacy) for names, dates, etc.
        2. Fallback: Regex patterns for structured PII (emails, phones, SSN)
        """
        # Layer 1: Try NER-based scrubber (catches names reliably)
        try:
            from core.compliance.pii_scrubber import get_pii_scrubber
            scrubber = get_pii_scrubber()
            return scrubber.scrub(text)
        except ImportError:
            pass
        
        # Layer 2: Try Presidio (Microsoft's PII detection)
        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_anonymizer import AnonymizerEngine
            
            analyzer = AnalyzerEngine()
            anonymizer = AnonymizerEngine()
            
            # Analyze for all PII types
            results = analyzer.analyze(
                text=text,
                entities=["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", 
                          "DATE_TIME", "LOCATION", "MEDICAL_LICENSE"],
                language="en"
            )
            
            # Anonymize detected entities
            anonymized = anonymizer.anonymize(text=text, analyzer_results=results)
            return anonymized.text
            
        except ImportError:
            logger.warning("Presidio not available, falling back to regex")
        
        # Layer 3: Regex fallback (structured patterns only)
        import re
        # Remove emails
        text = re.sub(r'\S+@\S+', '[EMAIL]', text)
        # Remove phone numbers
        text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE]', text)
        # Remove SSN-like patterns
        text = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]', text)
        # Remove dates (MM/DD/YYYY, YYYY-MM-DD)
        text = re.sub(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b', '[DATE]', text)
        text = re.sub(r'\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b', '[DATE]', text)
        # Remove MRN-like patterns
        text = re.sub(r'\b(?:MRN|mrn)[:#]?\s*\d+\b', '[MRN]', text)
        return text
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc.replace("www.", "")
        except Exception:
            return "unknown"


def search_verified_sources(query: str, max_results: int = 5) -> str:
    """
    Convenience function for agent tool calling.
    
    Returns formatted markdown string with citations.
    
    Args:
        query: User's search query
        max_results: Max results to return
        
    Returns:
        Markdown-formatted results with citations
    """
    # Check cache first for common queries
    cache_key = _get_search_cache_key(query)
    cached_result = _search_cache.get(cache_key)
    if cached_result and _is_cache_valid(cache_key):
        logger.info(f"Web search cache hit: {cache_key}")
        return cached_result
    
    try:
        tool = VerifiedWebSearchTool()
        response = tool.search(query, max_results)
        
        # Handle zero results gracefully
        if not response.results:
            return _build_zero_results_response(query, response.domains_searched)
        
        # Format as markdown
        lines = [
            f"**Web Search Results** (from verified medical sources)\n",
            f"Query: *{response.query}*\n"
        ]
        
        for i, result in enumerate(response.results, 1):
            lines.append(f"\n### {i}. {result.title}")
            lines.append(f"**Source:** [{result.domain}]({result.url})")
            lines.append(f"\n{result.content[:500]}...")
        
        lines.append(f"\n---\n{response.disclaimer}")
        
        result = "\n".join(lines)
        
        # Cache successful results (TTL: 1 hour for medical info freshness)
        _search_cache[cache_key] = result
        _cache_timestamps[cache_key] = time.time()
        
        return result
        
    except Exception as e:
        logger.error(f"search_verified_sources failed: {e}")
        return f"Web search unavailable: {str(e)}"


# Tool definition for LLM function calling
WEB_SEARCH_TOOL_DEFINITION = {
    "name": "search_verified_sources",
    "description": (
        "Search verified medical websites (CDC, NIH, Mayo Clinic, etc.) "
        "for recent health information. Use for queries about recent FDA approvals, "
        "latest guidelines, or when internal knowledge is insufficient. "
        "DO NOT use for clinical diagnosis or drug interaction checks."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query (will be sanitized of personal info)"
            }
        },
        "required": ["query"]
    }
}


# =============================================================================
# CACHING LAYER FOR LATENCY MANAGEMENT
# =============================================================================

# Simple in-memory cache with TTL (production should use Redis)
_search_cache: Dict[str, str] = {}
_cache_timestamps: Dict[str, float] = {}
CACHE_TTL_SECONDS = 3600  # 1 hour

def _get_search_cache_key(query: str) -> str:
    """Generate cache key from normalized query."""
    normalized = query.lower().strip()
    return f"websearch_{hashlib.sha256(normalized.encode()).hexdigest()[:16]}"

def _is_cache_valid(key: str) -> bool:
    """Check if cached entry is still valid."""
    import time
    timestamp = _cache_timestamps.get(key, 0)
    return (time.time() - timestamp) < CACHE_TTL_SECONDS

def clear_search_cache():
    """Clear the search cache (for testing/admin)."""
    _search_cache.clear()
    _cache_timestamps.clear()


# =============================================================================
# GRACEFUL ZERO-RESULTS HANDLING
# =============================================================================

def _build_zero_results_response(query: str, domains_searched: List[str]) -> str:
    """
    Build helpful response when no results found.
    
    Instead of generic 'error', explains WHY and suggests alternatives.
    """
    domains_list = ", ".join(domains_searched[:5])
    
    return f"""
**No Results Found on Verified Sources**

I searched the following trusted medical websites but couldn't find specific information about: *"{query}"*

**Sources Checked:** {domains_list}

**Why This Might Happen:**
- The topic may be very new and not yet covered by official sources
- The drug or treatment might be in clinical trials (not yet FDA-approved)
- The query might be too specific for general medical databases

**What You Can Do:**
1. Try rephrasing your question with broader terms
2. Check [ClinicalTrials.gov](https://clinicaltrials.gov) for ongoing research
3. Ask your healthcare provider about the latest developments

⚠️ *This search only queried official government and clinical sources for your safety.*
"""