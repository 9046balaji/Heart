"""
3D Radiology Volume Tools

Provides NIfTI and DICOM series volume handling for 3D medical imaging.
Requires nibabel and numpy.
"""

from .volume_handler import VolumeHandler, VolumeMetadata

__all__ = [
    "VolumeHandler",
    "VolumeMetadata",
]
