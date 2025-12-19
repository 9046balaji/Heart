"""
PII Scrubbing for Memory System.

Scrub Personally Identifiable Information (PII) from text before storing in memory system.
"""

import re
import logging
from typing import List, Tuple, Dict, Any

logger = logging.getLogger(__name__)


class PIIScrubber:
    """Scrub PII from text before storing in memory system."""
    
    # Patterns for common PII types with replacement templates
    PATTERNS: List[Tuple[str, str]] = [
        # Social Security Numbers (XXX-XX-XXXX or XXXXXXXXX)
        (r'\b\d{3}-\d{2}-\d{4}\b', '[SSN_REDACTED]'),
        (r'\b\d{9}\b', '[SSN_REDACTED]'),
        
        # Phone numbers (various formats)
        (r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE_REDACTED]'),
        (r'\b\(\d{3}\)\s*\d{3}[-.]?\d{4}\b', '[PHONE_REDACTED]'),
        (r'\b\d{10}\b', '[PHONE_REDACTED]'),
        
        # Email addresses
        (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL_REDACTED]'),
        
        # Credit card numbers (basic patterns)
        (r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', '[CC_REDACTED]'),
        (r'\b\d{16}\b', '[CC_REDACTED]'),
        
        # Names (simple pattern - two capitalized words)
        # Note: This is a simple heuristic and may have false positives
        (r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', '[NAME_REDACTED]'),
        
        # Addresses (street addresses)
        (r'\b\d+ [A-Z][a-z]+ (?:St|Ave|Blvd|Dr|Rd|Ct|Ln|Pl|Sq|Ter|Way)\b', '[ADDRESS_REDACTED]'),
        
        # Medical record numbers (common formats)
        (r'\b[A-Z]{2,3}\d{6,8}\b', '[MRN_REDACTED]'),
        (r'\b\d{8,10}\b', '[MRN_REDACTED]'),
        
        # Insurance IDs
        (r'\b[A-Z]{1,2}\d{8,12}\b', '[INSURANCE_ID_REDACTED]'),
    ]
    
    def __init__(self):
        """Initialize PII scrubber."""
        logger.info("PII scrubber initialized")
    
    def scrub(self, text: str) -> str:
        """
        Remove PII from text.
        
        Args:
            text: Text to scrub
            
        Returns:
            Text with PII redacted
        """
        if not text:
            return text
        
        scrubbed_text = text
        
        # Apply all patterns
        for pattern, replacement in self.PATTERNS:
            try:
                scrubbed_text = re.sub(pattern, replacement, scrubbed_text)
            except re.error as e:
                logger.warning(f"Invalid regex pattern '{pattern}': {e}")
                continue
        
        # Log if any PII was found and scrubbed
        if scrubbed_text != text:
            logger.debug("PII detected and scrubbed from text")
        
        return scrubbed_text
    
    def scrub_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively scrub PII from dictionary values.
        
        Args:
            data: Dictionary to scrub
            
        Returns:
            Dictionary with PII redacted
        """
        scrubbed_data = {}
        
        for key, value in data.items():
            if isinstance(value, str):
                scrubbed_data[key] = self.scrub(value)
            elif isinstance(value, dict):
                scrubbed_data[key] = self.scrub_dict(value)
            elif isinstance(value, list):
                scrubbed_data[key] = self.scrub_list(value)
            else:
                scrubbed_data[key] = value
        
        return scrubbed_data
    
    def scrub_list(self, items: List[Any]) -> List[Any]:
        """
        Recursively scrub PII from list items.
        
        Args:
            items: List to scrub
            
        Returns:
            List with PII redacted
        """
        scrubbed_items = []
        
        for item in items:
            if isinstance(item, str):
                scrubbed_items.append(self.scrub(item))
            elif isinstance(item, dict):
                scrubbed_items.append(self.scrub_dict(item))
            elif isinstance(item, list):
                scrubbed_items.append(self.scrub_list(item))
            else:
                scrubbed_items.append(item)
        
        return scrubbed_items
    
    def add_custom_pattern(self, pattern: str, replacement: str) -> None:
        """
        Add a custom PII pattern to scrub.
        
        Args:
            pattern: Regex pattern to match
            replacement: Replacement text
        """
        try:
            # Validate the pattern
            re.compile(pattern)
            self.PATTERNS.append((pattern, replacement))
            logger.debug(f"Added custom PII pattern: {pattern}")
        except re.error as e:
            logger.error(f"Invalid custom regex pattern '{pattern}': {e}")
            raise ValueError(f"Invalid regex pattern: {e}")


# Global PII scrubber instance
_pii_scrubber: Optional[PIIScrubber] = None


def get_pii_scrubber() -> PIIScrubber:
    """
    Get or create the global PII scrubber instance.
    
    Returns:
        PII scrubber instance
    """
    global _pii_scrubber
    if _pii_scrubber is None:
        _pii_scrubber = PIIScrubber()
    return _pii_scrubber


def scrub_pii(text: str) -> str:
    """
    Convenience function to scrub PII from text.
    
    Args:
        text: Text to scrub
        
    Returns:
        Text with PII redacted
    """
    scrubber = get_pii_scrubber()
    return scrubber.scrub(text)