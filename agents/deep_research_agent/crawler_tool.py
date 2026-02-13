import asyncio
import os
import json
import base64
import logging
from typing import List, Dict, Optional, Union
from datetime import datetime


# External Dependencies
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, CrawlResult
from crawl4ai.extraction_strategy import LLMExtractionStrategy

# Try importing advanced modules
try:
    from crawl4ai.deep_crawling import BFSDeepCrawlStrategy, DeepCrawlConfig
    DEEP_CRAWL_AVAILABLE = True
except ImportError:
    DEEP_CRAWL_AVAILABLE = False

try:
    from crawl4ai.content_filter_strategy import PruningContentFilter
except ImportError:
    PruningContentFilter = None

from .models import ResearchInsight

logger = logging.getLogger(__name__)

# Configuration
BROWSER_PROFILE_DIR = os.path.join(os.getcwd(), "browser_profile")
SCREENSHOTS_DIR = os.path.join("research_outputs", "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
os.makedirs(BROWSER_PROFILE_DIR, exist_ok=True)

# LLM Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai/gpt-4o")
LLM_API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")

# **CONCURRENCY CONTROL**: Limit concurrent browser instances to prevent OOM
# Each browser instance uses ~300MB+ RAM. Default: 3 concurrent crawlers.
MAX_CONCURRENT_CRAWLERS = int(os.getenv("MAX_CONCURRENT_CRAWLERS", "3"))
_crawler_semaphore = asyncio.Semaphore(MAX_CONCURRENT_CRAWLERS)

# JavaScript injection for expanding hidden content
EXPAND_CONTENT_SCRIPT = """
async () => {
    // 1. Scroll to bottom to trigger lazy loading
    window.scrollTo(0, document.body.scrollHeight);
    await new Promise(r => setTimeout(r, 1000));
    
    // 2. Click common "Read More" buttons
    const buttons = document.querySelectorAll('button, a');
    for (const btn of buttons) {
        if (btn.innerText && (
            btn.innerText.toLowerCase().includes('read more') || 
            btn.innerText.toLowerCase().includes('show more') ||
            btn.innerText.toLowerCase().includes('load more'))) {
            try { btn.click(); } catch(e) {}
        }
    }
    await new Promise(r => setTimeout(r, 500));
}
"""

def _save_screenshot(url: str, screenshot_base64: str) -> Optional[str]:
    """Save base64 screenshot to file."""
    try:
        # Generate filename from URL
        safe_name = url[:20].replace('https://', '').replace('http://', '').replace('/', '_')
        filename = f"screenshot_{safe_name}_{int(datetime.now().timestamp())}.png"
        filepath = os.path.join(SCREENSHOTS_DIR, filename)
        
        # Decode and save
        with open(filepath, "wb") as f:
            f.write(base64.b64decode(screenshot_base64))
        
        return filepath
    except Exception as e:
        logger.error(f"Failed to save screenshot: {e}")
        return None


async def _crawl_with_limit(
    crawler: AsyncWebCrawler, 
    url: str, 
    config: CrawlerRunConfig,
    deep_crawl_strategy=None
) -> CrawlResult:
    """
    Wrap crawler.arun with semaphore to limit concurrent browser instances.
    
    **Concurrency Control**: Prevents OOM by limiting parallel crawlers.
    Each browser instance consumes ~300MB RAM. With default limit of 3,
    max memory usage = ~900MB for crawling alone.
    
    Args:
        crawler: AsyncWebCrawler instance
        url: URL to crawl
        config: CrawlerRunConfig with extraction strategy
        deep_crawl_strategy: Optional deep crawl strategy (for recursive crawling)
    """
    async with _crawler_semaphore:
        logger.debug(f"Acquired crawler slot ({_crawler_semaphore._value}/{MAX_CONCURRENT_CRAWLERS} available)")
        if deep_crawl_strategy:
            return await crawler.arun(url=url, config=config, deep_crawl_strategy=deep_crawl_strategy)
        else:
            return await crawler.arun(url=url, config=config)

def _parse_and_add_insight(result: CrawlResult, insights: List[ResearchInsight]):
    """Helper to parse result and add to insights list."""
    if not result.success or not result.extracted_content:
        return

    try:
        # Save screenshot
        screenshot_path = None
        if result.screenshot:
            screenshot_path = _save_screenshot(result.url, result.screenshot)
        
        data = json.loads(result.extracted_content)
        
        # Handle list or single object
        items = data if isinstance(data, list) else [data]
        
        for item in items:
            item['source_url'] = result.url
            item['screenshot_path'] = screenshot_path
            
            # Extract links if available
            if hasattr(result, 'links'):
                item['source_links'] = [l.get('href', '') for l in result.links[:5]]
                
            insights.append(ResearchInsight(**item))
            
        logger.info(f"✅ Extracted insight from {result.url}")
            
    except Exception as e:
        logger.warning(f"Failed to parse JSON from {result.url}: {e}")

async def crawl_and_extract(urls: List[str], extraction_prompt: str) -> List[ResearchInsight]:
    """
    Crawls URLs and extracts structured insights.
    Optimized for PDFs (magic=False) and HTML (magic=True).
    """
    logger.info(f"🚀 Starting crawl for {len(urls)} URLs...")
    
    # 1. Configure Browser
    browser_config = BrowserConfig(
        headless=True,
        verbose=False,
        user_agent_mode="random",
        text_mode=False, # Must be False for screenshots!
        user_data_dir=BROWSER_PROFILE_DIR,
    )

    # 2. LLM Extraction Strategy
    llm_strategy = LLMExtractionStrategy(
        provider=LLM_PROVIDER,
        api_token=LLM_API_KEY,
        schema=ResearchInsight.model_json_schema(),
        extraction_type="schema",
        instruction=extraction_prompt,
        chunk_token_threshold=2000,
        overlap_rate=0.1,
        apply_chunking=True,
        input_format="markdown",
        verbose=False
    )

    insights = []
    
    # 3. Crawl with smart routing and concurrency limiting
    async with AsyncWebCrawler(config=browser_config) as crawler:
        for url in urls:
            # Smart config: Disable magic for PDFs to save 2-3 seconds
            is_pdf = url.lower().endswith(".pdf")
            
            run_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                magic=not is_pdf,  # ✨ Disable for PDFs
                word_count_threshold=500,
                remove_overlay_elements=True,
                process_iframes=False,
                exclude_external_links=True,
                js_code=EXPAND_CONTENT_SCRIPT if not is_pdf else None,
                wait_for="article, main, .content" if not is_pdf else None,
                screenshot=not is_pdf, # Capture screenshots only for web
                extraction_strategy=llm_strategy,
            )

            # Add Content Filter
            if PruningContentFilter and not is_pdf:
                run_config.content_filter = PruningContentFilter(
                    threshold=0.45,
                    min_word_threshold=50
                )

            try:
                logger.info(f"{'📄' if is_pdf else '🌐'} Crawling: {url}")
                # Use semaphore wrapper to limit concurrent browser instances
                result = await _crawl_with_limit(crawler, url, run_config)
                _parse_and_add_insight(result, insights)
                    
            except Exception as e:
                logger.error(f"Error processing {url}: {e}")
                continue

    return insights

async def deep_crawl_research(
    seed_urls: List[str],
    extraction_prompt: str,
    max_depth: int = 1,
    max_pages_per_seed: int = 10,
    score_threshold: float = 0.7
) -> List[ResearchInsight]:
    """
    Perform deep research using native crawl4ai deep crawling (BFS) for Web,
    and optimized fast crawl for PDFs.
    """
    logger.info(f"🔍 Deep crawling {len(seed_urls)} seed URLs...")
    
    # Separate PDFs from regular sites
    pdf_urls = [u for u in seed_urls if u.lower().endswith('.pdf')]
    web_urls = [u for u in seed_urls if not u.lower().endswith('.pdf')]
    
    insights = []
    
    # Browser Config (Screenshots enabled)
    browser_config = BrowserConfig(
        headless=True,
        user_agent_mode="random",
        text_mode=False, # Must be False for screenshots!
        user_data_dir=BROWSER_PROFILE_DIR,
    )
    
    # LLM Strategy
    llm_strategy = LLMExtractionStrategy(
        provider=LLM_PROVIDER,
        api_token=LLM_API_KEY,
        schema=ResearchInsight.model_json_schema(),
        extraction_type="schema",
        instruction=extraction_prompt,
        chunk_token_threshold=2000,
    )
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        
        # 1. Process PDFs (Fast Mode, No Magic, No Deep Crawl)
        if pdf_urls:
            logger.info(f"📄 Processing {len(pdf_urls)} PDF seeds (Fast Mode)...")
            pdf_run_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                magic=False,      # CRITICAL: Disable magic for PDFs
                word_count_threshold=500,
                remove_overlay_elements=True,
                extraction_strategy=llm_strategy,
                screenshot=False, # Usually no screenshots for PDFs
            )
            
            # Run flat crawl for PDFs
            results = await crawler.arun_many(pdf_urls, config=pdf_run_config)
            
            for res in results:
                _parse_and_add_insight(res, insights)

        # 2. Process Web Pages (Magic Mode, Deep Crawl)
        if web_urls:
            logger.info(f"🌐 Deep crawling {len(web_urls)} Web seeds (BFS Strategy)...")
            
            # Web Config
            web_run_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                magic=True,
                word_count_threshold=500,
                remove_overlay_elements=True,
                extraction_strategy=llm_strategy,
                screenshot=True,
            )
            
            if PruningContentFilter:
                web_run_config.content_filter = PruningContentFilter(
                    threshold=0.45,
                    min_word_threshold=50
                )
            
            if DEEP_CRAWL_AVAILABLE:
                deep_config = DeepCrawlConfig(
                    max_depth=max_depth,
                    score_threshold=score_threshold,
                    same_domain_only=True,
                    max_pages=max_pages_per_seed,
                )
                crawl_strategy = BFSDeepCrawlStrategy(config=deep_config)
                
                for seed_url in web_urls:
                    try:
                        # Use semaphore wrapper to limit concurrent browser instances
                        results = await _crawl_with_limit(
                            crawler,
                            seed_url,
                            web_run_config,
                            deep_crawl_strategy=crawl_strategy
                        )
                        
                        # Handle results (could be list or single)
                        results_list = results if isinstance(results, list) else [results]
                        for res in results_list:
                            _parse_and_add_insight(res, insights)

                    except Exception as e:
                        logger.error(f"Deep crawl failed for {seed_url}: {e}")
            else:
                # Fallback to flat crawl
                logger.warning("⚠️ Deep crawl unavailable, using simple crawl for Web URLs")
                results = await crawler.arun_many(web_urls, config=web_run_config)
                for res in results:
                    _parse_and_add_insight(res, insights)

    logger.info(f"✅ Research complete: {len(insights)} insights")
    return insights
