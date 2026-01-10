import logging
from typing import List

# Import from shared tools directory
# Note: deep_research.py ensures project root is in sys.path
try:
    from tools.web_search import VerifiedWebSearchTool
except ImportError:
    # Fallback: try relative import if running as package
    try:
        from ...tools.web_search import VerifiedWebSearchTool
    except ImportError as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to import VerifiedWebSearchTool: {e}")
        raise

logger = logging.getLogger(__name__)

async def get_search_results(query: str, max_results: int = 5, search_pdfs: bool = False) -> List[str]:
    """
    Adapter function to make VerifiedWebSearchTool compatible with Deep Research Agent.
    Handles 'filetype:pdf' injection for paper search.
    """
    # 1. Modify query for PDFs if requested
    final_query = query
    if search_pdfs:
        # Google/DDG operator for PDFs
        final_query += " filetype:pdf"
    
    # 2. Initialize the tool (using cache if available)
    tool = VerifiedWebSearchTool(use_cache=True)
    
    # 3. Execute Search
    try:
        response = await tool.search(final_query, num_results=max_results)
        
        # 4. Extract URLs
        urls = [result.url for result in response.results]
        
        # 5. Filter for PDFs strictly if requested (double-check)
        if search_pdfs:
            urls = [u for u in urls if u.lower().endswith('.pdf')]
            
        logger.info(f"🔍 Found {len(urls)} URLs for query: '{final_query}'")
        return urls
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return []
