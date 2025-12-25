#!/usr/bin/env python3
"""
Script to create INT8 quantized ONNX models as specified in BACKEND_PERFORMANCE_PLAN.md
This addresses the remaining task from the performance plan.
"""

import os
import sys
from pathlib import Path

# Add the nlp-service directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from nlp.rag.model_converter import ONNXModelConverter

def create_quantized_model():
    """Create INT8 quantized ONNX model."""
    print("Creating INT8 quantized ONNX embedding model...")
    
    # Create output directory
    output_dir = Path("models/onnx_quantized")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize converter
    converter = ONNXModelConverter()
    
    # Convert with INT8 quantization
    model_path, metadata = converter.convert(
        model_name="all-MiniLM-L6-v2",
        output_dir=str(output_dir),
        quantize=True,
        optimize_level="O2"
    )
    
    print(f"✅ Model created: {model_path}")
    print(f"   Quantized: {metadata['quantized']}")
    print(f"   Model: {metadata['model_name']}")
    print(f"   Dimensions: {metadata['dimension']}")
    
    # Validate the conversion
    is_valid = converter.validate_conversion(
        original_model="sentence-transformers/all-MiniLM-L6-v2",
        onnx_path=model_path
    )
    
    if is_valid:
        print("✅ Model validation passed")
    else:
        print("❌ Model validation failed")
        
    return model_path, metadata

if __name__ == "__main__":
    try:
        model_path, metadata = create_quantized_model()
        print(f"\n✅ INT8 quantized model successfully created at: {model_path}")
        print("Model is ready for use with 4x faster inference as specified in the performance plan.")
    except Exception as e:
        print(f"❌ Error creating quantized model: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)