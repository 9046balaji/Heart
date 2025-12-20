"""
Medical PII Scrubber for RAG Pipeline.

Scrub Personally Identifiable Information (PII) from medical text while preserving
medical information needed for healthcare AI responses.
"""

import re
import logging
from typing import List, Tuple, Dict, Any

logger = logging.getLogger(__name__)


class MedicalPIIScrubber:
    """Scrub PII from medical text while preserving medical relevance."""

    # Patterns for medical PII types with replacement templates
    # More conservative than general PII scrubber to preserve medical info
    PATTERNS: List[Tuple[str, str]] = [
        # Social Security Numbers (XXX-XX-XXXX or XXXXXXXXX)
        (r"\b\d{3}-\d{2}-\d{4}\b", "[SSN]"),
        (r"\b\d{9}\b", "[SSN]"),
        # Phone numbers (various formats)
        (r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "[PHONE]"),
        (r"\b\(\d{3}\)\s*\d{3}[-.]?\d{4}\b", "[PHONE]"),
        (r"\b\d{10}\b", "[PHONE]"),
        # Email addresses
        (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL]"),
        # Addresses (street addresses)
        (r"\b\d+ [A-Z][a-z]+ (?:St|Ave|Blvd|Dr|Rd|Ct|Ln|Pl|Sq|Ter|Way)\b", "[ADDRESS]"),
        # Medical record numbers (common formats)
        (r"\b[A-Z]{2,3}\d{6,8}\b", "[MRN]"),
        (r"\b\d{8,10}\b", "[MRN]"),
        # Insurance IDs
        (r"\b[A-Z]{1,2}\d{8,12}\b", "[INSURANCE_ID]"),
        # Credit card numbers (basic patterns) - less likely in medical context
        (r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", "[CC]"),
        (r"\b\d{16}\b", "[CC]"),
    ]

    # Medical values that should NOT be scrubbed
    MEDICAL_EXCEPTIONS = [
        r"\b\d+/\d+\b",  # Blood pressure (e.g., 120/80)
        r"\b\d+\.\d+\s*(?:mg|mcg|g|ml|units?|IU|mEq)\b",  # Dosages (e.g., 10.5 mg)
        r"\b\d+\s*(?:mg|mcg|g|ml|units?|IU|mEq)\b",  # Dosages (e.g., 10 mg)
        r"\b\d+\.\d+\s*(?:bpm|%|mmHg|kg|lbs?|cm|m)\b",  # Measurements (e.g., 72 bpm)
        r"\b\d+\s*(?:bpm|%|mmHg|kg|lbs?|cm|m)\b",  # Measurements (e.g., 72 bpm)
    ]

    def __init__(self):
        """Initialize medical PII scrubber."""
        logger.info("Medical PII scrubber initialized")

    def scrub(self, text: str, preserve_medical: bool = True) -> str:
        """
        Remove PII from medical text while optionally preserving medical values.

        Args:
            text: Text to scrub
            preserve_medical: Keep medical values (BP, dosages) - default True

        Returns:
            Text with PII redacted
        """
        if not text:
            return text

        scrubbed_text = text

        # If preserving medical values, temporarily mask them
        medical_masks = {}
        if preserve_medical:
            for i, pattern in enumerate(self.MEDICAL_EXCEPTIONS):
                try:

                    def mask_match(match):
                        mask = f"__MEDICAL_VALUE_{i}_{len(medical_masks)}__"
                        medical_masks[mask] = match.group(0)
                        return mask

                    scrubbed_text = re.sub(pattern, mask_match, scrubbed_text)
                except re.error as e:
                    logger.warning(
                        f"Invalid medical exception pattern '{pattern}': {e}"
                    )

        # Apply PII patterns
        for pattern, replacement in self.PATTERNS:
            try:
                scrubbed_text = re.sub(pattern, replacement, scrubbed_text)
            except re.error as e:
                logger.warning(f"Invalid regex pattern '{pattern}': {e}")
                continue

        # Restore medical values if we preserved them
        if preserve_medical:
            for mask, original in medical_masks.items():
                scrubbed_text = scrubbed_text.replace(mask, original)

        # Log if any PII was found and scrubbed
        if scrubbed_text != text:
            logger.debug("PII detected and scrubbed from medical text")

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


# Global medical PII scrubber instance
_medical_pii_scrubber: "MedicalPIIScrubber" = None


def get_medical_pii_scrubber() -> MedicalPIIScrubber:
    """
    Get or create the global medical PII scrubber instance.

    Returns:
        Medical PII scrubber instance
    """
    global _medical_pii_scrubber
    if _medical_pii_scrubber is None:
        _medical_pii_scrubber = MedicalPIIScrubber()
    return _medical_pii_scrubber


def scrub_medical_pii(text: str) -> str:
    """
    Convenience function to scrub PII from medical text.

    Args:
        text: Text to scrub

    Returns:
        Text with PII redacted
    """
    scrubber = get_medical_pii_scrubber()
    return scrubber.scrub(text)
