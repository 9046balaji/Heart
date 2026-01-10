"""
PII Scrubber - Backward compatibility wrapper

Re-exports from pii_scrubber_v2 for backward compatibility.
"""

from .pii_scrubber_v2 import (
    EnhancedPIIScrubber,
    PRESIDIO_AVAILABLE,
    SPACY_AVAILABLE,
)

# Alias for backward compatibility
PIIScrubber = EnhancedPIIScrubber

# Singleton instance
_pii_scrubber_instance = None


def get_pii_scrubber() -> PIIScrubber:
    """Get singleton PII scrubber instance."""
    global _pii_scrubber_instance
    if _pii_scrubber_instance is None:
        _pii_scrubber_instance = PIIScrubber(use_presidio=True, use_scispacy=True)
    return _pii_scrubber_instance


__all__ = [
    "PIIScrubber",
    "EnhancedPIIScrubber", 
    "get_pii_scrubber",
    "PRESIDIO_AVAILABLE",
    "SPACY_AVAILABLE",
]
