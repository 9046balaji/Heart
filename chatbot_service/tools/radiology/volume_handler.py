"""
3D Volume Processor

Provides support for 3D medical volumes (CT, MRI).
Supported formats: NIfTI (.nii, .nii.gz), DICOM Series

Note: Requires 'nibabel' and 'numpy'.
"""


import logging
import os
from dataclasses import dataclass
from typing import Tuple, Optional, List, Any, Dict
import numpy as np

logger = logging.getLogger(__name__)

def _get_nibabel():
    try:
        import nibabel as nib
        return nib
    except ImportError:
        logger.warning("nibabel not installed. Run: pip install nibabel")
        return None

@dataclass
class VolumeMetadata:
    """Metadata for a 3D Volume."""
    shape: Tuple[int, ...]
    affine: np.ndarray
    voxel_sizes: Tuple[float, ...]
    orientation: str
    data_type: str

class VolumeHandler:
    """
    Handler for 3D Medical Volumes.
    
    Example:
        handler = VolumeHandler("scan.nii.gz")
        slice_data = handler.get_slice('axial', 50)
    """
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self._nib = _get_nibabel()
        self.img = None
        self.data = None
        
        if self._nib:
            try:
                self.img = self._nib.load(file_path)
                self.data = self.img.get_fdata()
            except Exception as e:
                logger.error(f"Failed to load volume {file_path}: {e}")

    def get_metadata(self) -> Optional[VolumeMetadata]:
        """Extract metadata from the volume."""
        if self.img is None:
            return None
            
        try:
            return VolumeMetadata(
                shape=self.img.shape,
                affine=self.img.affine,
                voxel_sizes=self.img.header.get_zooms(),
                orientation="".join(self._nib.aff2axcodes(self.img.affine)),
                data_type=str(self.img.get_data_dtype())
            )
        except Exception as e:
            logger.error(f"Failed to extract metadata: {e}")
            return None

    def get_slice(self, plane: str = 'axial', index: Optional[int] = None) -> Optional[np.ndarray]:
        """
        Extract a 2D slice from the volume.
        
        Args:
            plane: 'axial', 'coronal', or 'sagittal'
            index: Slice index (default: middle of volume)
        """
        if self.data is None:
            return None
            
        try:
            if plane == 'axial':
                # Axial is usually the 3rd dimension (z)
                idx = index if index is not None else self.data.shape[2] // 2
                return self.data[:, :, idx]
            elif plane == 'coronal':
                # Coronal is usually the 2nd dimension (y)
                idx = index if index is not None else self.data.shape[1] // 2
                return self.data[:, idx, :]
            elif plane == 'sagittal':
                # Sagittal is usually the 1st dimension (x)
                idx = index if index is not None else self.data.shape[0] // 2
                return self.data[idx, :, :]
            else:
                logger.error(f"Unknown plane: {plane}")
                return None
        except Exception as e:
            logger.error(f"Failed to extract slice: {e}")
            return None

    def get_statistics(self) -> Dict[str, float]:
        """Calculate basic statistics of the volume."""
        if self.data is None:
            return {}
        return {
            "min": float(np.min(self.data)),
            "max": float(np.max(self.data)),
            "mean": float(np.mean(self.data)),
            "std": float(np.std(self.data))
        }

# Convenience function
def analyze_3d_volume(file_path: str) -> str:
    """
    Analyze a 3D volume (placeholder for actual AI analysis).
    
    Args:
        file_path: Path to .nii or .nii.gz file
        
    Returns:
        Analysis summary
    """
    handler = VolumeHandler(file_path)
    metadata = handler.get_metadata()
    
    if not metadata:
        return f"Failed to load volume: {file_path}. Ensure nibabel is installed."
        
    stats = handler.get_statistics()
    
    return f"""## 3D Volume Analysis
    
**File**: {os.path.basename(file_path)}
**Shape**: {metadata.shape}
**Voxel Sizes**: {metadata.voxel_sizes}
**Orientation**: {metadata.orientation}

**Statistics**:
- Min Intensity: {stats.get('min', 'N/A')}
- Max Intensity: {stats.get('max', 'N/A')}
- Mean Intensity: {stats.get('mean', 'N/A'):.2f}

*Note: 3D segmentation and volumetric analysis pending model integration.*
"""
