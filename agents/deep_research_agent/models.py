from typing import List, Optional
from pydantic import BaseModel, Field

class ResearchInsight(BaseModel):
    """Structured insight extracted from a single web page."""
    source_url: str = Field(..., description="The URL of the source.")
    title: str = Field(..., description="The title of the article or page.")
    summary: str = Field(..., description="A concise summary of the content (approx 100-150 words).")
    key_findings: List[str] = Field(..., description="List of 3-5 key technical findings or breakthroughs.")
    relevant_quotes: List[str] = Field(..., description="Direct quotes that support the findings.")
    source_links: List[str] = Field(default_factory=list, description="External links found on the page (for depth-2 research).")
    screenshot_path: Optional[str] = Field(default=None, description="Path to saved screenshot if available.")

