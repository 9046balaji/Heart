"""
OCR Engine for extracting text from medical documents.

Supports multiple backends:
- Tesseract (open source, local)
- Google Cloud Vision (cloud, high accuracy)
- AWS Textract (cloud, form extraction)

The factory pattern allows automatic fallback between engines.
"""

import os
import logging
import time
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class OCRProvider(Enum):
    """Available OCR providers."""

    TESSERACT = "tesseract"
    GOOGLE_VISION = "google_vision"
    AWS_TEXTRACT = "aws_textract"


@dataclass
class OCRResult:
    """Result from OCR processing."""

    text: str
    confidence: float
    provider: OCRProvider
    page_count: int
    blocks: List[Dict[str, Any]]  # Structured blocks with positions
    processing_time_ms: float
    metadata: Dict[str, Any]


class BaseOCREngine(ABC):
    """Abstract base class for OCR engines."""

    @abstractmethod
    def extract_text(self, file_path: str) -> OCRResult:
        """Extract text from document."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if engine is available."""


class TesseractOCREngine(BaseOCREngine):
    """
    Tesseract OCR engine (local, open-source).

    Requirements:
        pip install pytesseract Pillow pdf2image
        Also requires Tesseract binary installed on system

    Installation:
        Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
        Linux: sudo apt-get install tesseract-ocr
        macOS: brew install tesseract
    """

    def __init__(self, tesseract_cmd: Optional[str] = None):
        """
        Initialize Tesseract engine.

        Args:
            tesseract_cmd: Path to Tesseract executable
        """
        self.tesseract_cmd = tesseract_cmd or os.getenv(
            "TESSERACT_CMD",
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",  # Windows default
        )
        self._available = None

    def is_available(self) -> bool:
        """Check if Tesseract is available."""
        if self._available is not None:
            return self._available

        try:
            import pytesseract

            pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
            pytesseract.get_tesseract_version()
            self._available = True
            logger.info(f"Tesseract available: {self.tesseract_cmd}")
        except Exception as e:
            logger.warning(f"Tesseract not available: {e}")
            self._available = False

        return self._available

    def extract_text(self, file_path: str) -> OCRResult:
        """
        Extract text using Tesseract.

        Args:
            file_path: Path to PDF or image file

        Returns:
            OCRResult with extracted text
        """
        start_time = time.time()

        try:
            import pytesseract
            from PIL import Image

            pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd

            # Handle PDF vs image
            if file_path.lower().endswith(".pdf"):
                try:
                    from pdf2image import convert_from_path

                    images = convert_from_path(file_path)
                except ImportError:
                    raise RuntimeError(
                        "pdf2image not installed. Install with: pip install pdf2image\n"
                        "Also requires poppler: https://poppler.freedesktop.org/"
                    )
            else:
                images = [Image.open(file_path)]

            all_text = []
            all_blocks = []
            total_confidence = 0
            block_count = 0

            for page_num, image in enumerate(images):
                # Get detailed data with confidence scores
                data = pytesseract.image_to_data(
                    image,
                    output_type=pytesseract.Output.DICT,
                    config="--psm 6",  # Assume uniform block of text
                )

                # Extract text
                page_text = pytesseract.image_to_string(image)
                all_text.append(page_text)

                # Build blocks with positions
                for i, word in enumerate(data["text"]):
                    if word.strip():
                        conf = data["conf"][i]
                        if conf > 0:  # Valid confidence
                            all_blocks.append(
                                {
                                    "page": page_num + 1,
                                    "text": word,
                                    "confidence": conf / 100,
                                    "bbox": {
                                        "left": data["left"][i],
                                        "top": data["top"][i],
                                        "width": data["width"][i],
                                        "height": data["height"][i],
                                    },
                                }
                            )
                            total_confidence += conf
                            block_count += 1

            # Calculate average confidence
            avg_confidence = (
                (total_confidence / block_count / 100) if block_count else 0
            )

            processing_time = (time.time() - start_time) * 1000

            return OCRResult(
                text="\n\n".join(all_text),
                confidence=avg_confidence,
                provider=OCRProvider.TESSERACT,
                page_count=len(images),
                blocks=all_blocks,
                processing_time_ms=processing_time,
                metadata={
                    "engine_version": str(pytesseract.get_tesseract_version()),
                    "config": "--psm 6",
                },
            )

        except ImportError as e:
            raise RuntimeError(
                f"Required packages not installed: {e}. "
                "Install with: pip install pytesseract Pillow pdf2image"
            )
        except Exception as e:
            logger.error(f"Tesseract OCR failed: {e}")
            raise


class GoogleVisionOCREngine(BaseOCREngine):
    """
    Google Cloud Vision OCR engine.

    Requirements:
        pip install google-cloud-vision
        Set GOOGLE_APPLICATION_CREDENTIALS environment variable

    Best for:
        - High accuracy requirements
        - Multi-language support
        - Handwriting recognition
    """

    def __init__(self):
        """Initialize Google Vision engine."""
        self._available = None
        self._client = None

    def is_available(self) -> bool:
        """Check if Google Vision is available."""
        if self._available is not None:
            return self._available

        try:
            from google.cloud import vision

            credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if not credentials_path:
                logger.warning("GOOGLE_APPLICATION_CREDENTIALS not set")
                self._available = False
                return False

            self._client = vision.ImageAnnotatorClient()
            self._available = True
            logger.info("Google Vision OCR available")
        except Exception as e:
            logger.warning(f"Google Vision not available: {e}")
            self._available = False

        return self._available

    def extract_text(self, file_path: str) -> OCRResult:
        """
        Extract text using Google Vision.

        Args:
            file_path: Path to PDF or image file

        Returns:
            OCRResult with extracted text
        """
        start_time = time.time()

        try:
            from google.cloud import vision

            with open(file_path, "rb") as f:
                content = f.read()

            image = vision.Image(content=content)
            response = self._client.document_text_detection(image=image)

            if response.error.message:
                raise RuntimeError(f"Google Vision error: {response.error.message}")

            # Extract full text
            full_text = (
                response.full_text_annotation.text
                if response.full_text_annotation
                else ""
            )

            # Extract blocks with confidence
            blocks = []
            pages = (
                response.full_text_annotation.pages
                if response.full_text_annotation
                else []
            )

            for page_num, page in enumerate(pages):
                for block in page.blocks:
                    block_text = ""
                    for paragraph in block.paragraphs:
                        for word in paragraph.words:
                            word_text = "".join([s.text for s in word.symbols])
                            block_text += word_text + " "

                    if block_text.strip():
                        blocks.append(
                            {
                                "page": page_num + 1,
                                "text": block_text.strip(),
                                "confidence": block.confidence,
                                "bbox": {
                                    "vertices": [
                                        {"x": v.x, "y": v.y}
                                        for v in block.bounding_box.vertices
                                    ]
                                },
                            }
                        )

            # Average confidence
            avg_confidence = (
                sum(b["confidence"] for b in blocks) / len(blocks) if blocks else 0
            )

            processing_time = (time.time() - start_time) * 1000

            return OCRResult(
                text=full_text,
                confidence=avg_confidence,
                provider=OCRProvider.GOOGLE_VISION,
                page_count=len(pages),
                blocks=blocks,
                processing_time_ms=processing_time,
                metadata={"api_version": "v1"},
            )

        except ImportError:
            raise RuntimeError(
                "google-cloud-vision not installed. "
                "Install with: pip install google-cloud-vision"
            )


class AWSTextractEngine(BaseOCREngine):
    """
    AWS Textract OCR engine (optimized for forms/tables).

    Requirements:
        pip install boto3
        AWS credentials configured (via environment or ~/.aws/credentials)

    Best for:
        - Form extraction
        - Table extraction
        - Medical bills and invoices
    """

    def __init__(self, region: str = "us-east-1"):
        """Initialize AWS Textract engine."""
        self.region = region
        self._available = None
        self._client = None

    def is_available(self) -> bool:
        """Check if AWS Textract is available."""
        if self._available is not None:
            return self._available

        try:
            import boto3

            # Check for credentials
            session = boto3.Session()
            credentials = session.get_credentials()

            if not credentials:
                logger.warning("AWS credentials not configured")
                self._available = False
                return False

            self._client = boto3.client("textract", region_name=self.region)
            self._available = True
            logger.info("AWS Textract available")
        except Exception as e:
            logger.warning(f"AWS Textract not available: {e}")
            self._available = False

        return self._available

    def extract_text(self, file_path: str) -> OCRResult:
        """
        Extract text using AWS Textract.

        Args:
            file_path: Path to PDF or image file

        Returns:
            OCRResult with extracted text
        """
        start_time = time.time()

        try:
            with open(file_path, "rb") as f:
                content = f.read()

            # Use analyze_document for forms, detect_document_text for plain text
            response = self._client.detect_document_text(Document={"Bytes": content})

            # Extract text and blocks
            all_text = []
            blocks = []

            for block in response.get("Blocks", []):
                if block["BlockType"] == "LINE":
                    all_text.append(block["Text"])
                    blocks.append(
                        {
                            "page": block.get("Page", 1),
                            "text": block["Text"],
                            "confidence": block["Confidence"] / 100,
                            "bbox": block["Geometry"]["BoundingBox"],
                        }
                    )

            avg_confidence = (
                sum(b["confidence"] for b in blocks) / len(blocks) if blocks else 0
            )
            processing_time = (time.time() - start_time) * 1000

            return OCRResult(
                text="\n".join(all_text),
                confidence=avg_confidence,
                provider=OCRProvider.AWS_TEXTRACT,
                page_count=1,  # Single page for detect_document_text
                blocks=blocks,
                processing_time_ms=processing_time,
                metadata={"document_metadata": response.get("DocumentMetadata", {})},
            )

        except ImportError:
            raise RuntimeError("boto3 not installed. Install with: pip install boto3")

    def extract_form_fields(self, file_path: str) -> Dict[str, Any]:
        """
        Extract form key-value pairs from document.

        Specialized for medical bills and forms with labeled fields.

        Args:
            file_path: Path to document

        Returns:
            Dictionary of extracted form fields
        """
        try:
            with open(file_path, "rb") as f:
                content = f.read()

            response = self._client.analyze_document(
                Document={"Bytes": content}, FeatureTypes=["FORMS"]
            )

            # Extract key-value pairs
            key_map = {}
            value_map = {}
            block_map = {}

            for block in response.get("Blocks", []):
                block_id = block["Id"]
                block_map[block_id] = block

                if block["BlockType"] == "KEY_VALUE_SET":
                    if "KEY" in block.get("EntityTypes", []):
                        key_map[block_id] = block
                    elif "VALUE" in block.get("EntityTypes", []):
                        value_map[block_id] = block

            # Match keys to values
            form_fields = {}
            for key_id, key_block in key_map.items():
                key_text = self._get_text_from_block(key_block, block_map)
                value_block_id = None

                for relationship in key_block.get("Relationships", []):
                    if relationship["Type"] == "VALUE":
                        value_block_id = relationship["Ids"][0]
                        break

                if value_block_id and value_block_id in value_map:
                    value_text = self._get_text_from_block(
                        value_map[value_block_id], block_map
                    )
                    form_fields[key_text.strip()] = value_text.strip()

            return form_fields

        except Exception as e:
            logger.error(f"Form extraction failed: {e}")
            return {}

    def _get_text_from_block(self, block: Dict, block_map: Dict) -> str:
        """Extract text from a block, following child relationships."""
        text = ""
        for relationship in block.get("Relationships", []):
            if relationship["Type"] == "CHILD":
                for child_id in relationship["Ids"]:
                    child_block = block_map.get(child_id, {})
                    if child_block.get("BlockType") == "WORD":
                        text += child_block.get("Text", "") + " "
        return text


class OCREngineFactory:
    """
    Factory for creating OCR engines with fallback support.

    Tries providers in order of preference based on availability.
    Default preference: Tesseract > Google Vision > AWS Textract
    """

    def __init__(self):
        """Initialize OCR engine factory."""
        self.engines = {
            OCRProvider.TESSERACT: TesseractOCREngine(),
            OCRProvider.GOOGLE_VISION: GoogleVisionOCREngine(),
            OCRProvider.AWS_TEXTRACT: AWSTextractEngine(),
        }
        self._default_provider = None

    def get_engine(self, provider: Optional[OCRProvider] = None) -> BaseOCREngine:
        """
        Get an OCR engine.

        Args:
            provider: Specific provider to use, or None for auto-select

        Returns:
            Available OCR engine

        Raises:
            RuntimeError: If no OCR engine is available
        """
        if provider:
            engine = self.engines.get(provider)
            if engine and engine.is_available():
                return engine
            raise RuntimeError(f"OCR provider {provider.value} is not available")

        # Auto-select available engine (preference order)
        preference_order = [
            OCRProvider.TESSERACT,
            OCRProvider.GOOGLE_VISION,
            OCRProvider.AWS_TEXTRACT,
        ]

        for prov in preference_order:
            engine = self.engines.get(prov)
            if engine and engine.is_available():
                return engine

        raise RuntimeError(
            "No OCR engine available. Install one of:\n"
            "- Tesseract: pip install pytesseract\n"
            "- Google Vision: pip install google-cloud-vision\n"
            "- AWS Textract: pip install boto3"
        )

    def get_available_providers(self) -> List[OCRProvider]:
        """Get list of available OCR providers."""
        return [
            provider
            for provider, engine in self.engines.items()
            if engine.is_available()
        ]


# Global factory instance
ocr_factory = OCREngineFactory()
