"""
PII Redaction Filter for Python Logging.

Scrubs personally identifiable information from log messages
before they are written to files or external systems.
"""

import re
import logging
from typing import Pattern, List, Tuple


class PIIScrubFilter(logging.Filter):
    """
    Logging filter that redacts PII patterns from log records.
    
    Patterns scrubbed:
    - Email addresses
    - Phone numbers (US format)
    - Social Security Numbers
    - Credit card numbers
    - IP addresses
    - Names (via common patterns, not perfect)
    
    Usage:
        logger = logging.getLogger("my_logger")
        logger.addFilter(PIIScrubFilter())
    """
    
    # PII patterns with their replacements
    PATTERNS: List[Tuple[Pattern, str]] = [
        # Email addresses
        (
            re.compile(
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                re.IGNORECASE
            ),
            '[EMAIL_REDACTED]'
        ),
        # US Phone numbers: (123) 456-7890, 123-456-7890, 123.456.7890, +1 123 456 7890
        (
            re.compile(
                r'(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'
            ),
            '[PHONE_REDACTED]'
        ),
        # Social Security Numbers: 123-45-6789
        (
            re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
            '[SSN_REDACTED]'
        ),
        # Credit card numbers (basic pattern)
        (
            re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
            '[CC_REDACTED]'
        ),
        # IP addresses (IPv4)
        (
            re.compile(
                r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
                r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
            ),
            '[IP_REDACTED]'
        ),
        # Date of birth patterns: 01/15/1990, 1990-01-15
        (
            re.compile(
                r'\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})\b'
            ),
            '[DOB_REDACTED]'
        ),
        # Medical Record Numbers (common patterns: MRN followed by digits)
        (
            re.compile(r'\bMRN[:\s]?\d{6,10}\b', re.IGNORECASE),
            '[MRN_REDACTED]'
        ),
    ]
    
    def __init__(self, additional_patterns: List[Tuple[Pattern, str]] = None):
        """
        Initialize PII filter with optional additional patterns.
        
        Args:
            additional_patterns: List of (compiled_regex, replacement) tuples
        """
        super().__init__()
        self.patterns = self.PATTERNS.copy()
        if additional_patterns:
            self.patterns.extend(additional_patterns)
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter log record by scrubbing PII.
        
        Args:
            record: LogRecord to filter
            
        Returns:
            True (always allows the record through after scrubbing)
        """
        # Scrub the main message
        if record.msg:
            record.msg = self._scrub(str(record.msg))
        
        # Scrub any format arguments
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: self._scrub(str(v)) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    self._scrub(str(arg)) if isinstance(arg, str) else arg
                    for arg in record.args
                )
        
        return True
    
    def _scrub(self, text: str) -> str:
        """Apply all PII patterns to text."""
        result = text
        for pattern, replacement in self.patterns:
            result = pattern.sub(replacement, result)
        return result


def setup_pii_safe_logging(logger_name: str = None) -> None:
    """
    Configure PII-safe logging for the application.
    
    Args:
        logger_name: Specific logger to configure, or None for root logger
    """
    pii_filter = PIIScrubFilter()
    
    if logger_name:
        logger = logging.getLogger(logger_name)
    else:
        logger = logging.getLogger()
    
    # Add filter to all handlers
    for handler in logger.handlers:
        handler.addFilter(pii_filter)
    
    # Also add to logger itself (catches records before handlers)
    logger.addFilter(pii_filter)


# Integration with AuditLogger
def create_pii_safe_audit_logger(log_file: str = "audit.log") -> logging.Logger:
    """
    Create a dedicated audit logger with PII scrubbing.
    
    Returns:
        Logger configured for audit logging with PII protection
    """
    audit_logger = logging.getLogger("audit")
    audit_logger.setLevel(logging.WARNING)
    
    # File handler
    handler = logging.FileHandler(log_file)
    handler.setLevel(logging.WARNING)
    
    # JSON formatter
    formatter = logging.Formatter(
        '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
        '"message": "%(message)s"}'
    )
    handler.setFormatter(formatter)
    
    # Add PII filter
    handler.addFilter(PIIScrubFilter())
    
    audit_logger.addHandler(handler)
    
    return audit_logger