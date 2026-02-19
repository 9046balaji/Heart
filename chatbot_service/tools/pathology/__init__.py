"""
Digital Pathology Tools

Provides Whole Slide Image (WSI) handling for digital pathology workflows.
Requires openslide-python and system OpenSlide binaries.
"""

from .wsi_handler import WSIHandler, SlideMetadata

__all__ = [
    "WSIHandler",
    "SlideMetadata",
]
