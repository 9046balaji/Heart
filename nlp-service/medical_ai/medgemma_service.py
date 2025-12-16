"""
MedGemma Integration Service.

Provides medical document understanding using Google's MedGemma model.

MedGemma is optimized for:
- Medical text understanding
- Clinical entity extraction
- Patient-friendly explanations
- Multimodal medical analysis (optional)

Note: For production, consider using Google's hosted API
or running locally with sufficient GPU resources.

The key principle: "Think of MedGemma as a medical NLP brain, not the doctor."
- DO extract and understand medical information
- DO generate patient-friendly summaries
- DO NOT make diagnoses or treatment recommendations
"""

import os
import logging
import time
import json
import aiohttp
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class MedGemmaModel(Enum):
    """Available MedGemma model variants."""
    MEDGEMMA_4B = "medgemma-4b"           # Smaller, faster
    MEDGEMMA_27B = "medgemma-27b"         # Larger, more accurate
    MEDGEMMA_MULTIMODAL = "medgemma-mm"   # Image + text
    GEMINI_PRO = "gemini-pro"             # Fallback to Gemini
    GEMINI_PRO_VISION = "gemini-pro-vision"  # Fallback for multimodal


@dataclass
class ExtractionResult:
    """Result from medical entity extraction."""
    entities: List[Dict[str, Any]]
    raw_text: str
    confidence: float
    model_used: str
    processing_time_ms: float
    document_type: str = "unknown"


@dataclass
class SummaryResult:
    """Result from patient-friendly summarization."""
    summary: str
    key_findings: List[str]
    concerns: List[str]
    recommendations: List[str]
    reading_level: str
    original_length: int
    summary_length: int


class MedGemmaService:
    """
    Medical document understanding using MedGemma.
    
    Implements the "medical NLP brain" concept from medical.md.
    Focuses on understanding and extraction, NOT diagnosis.
    
    Usage Options:
    1. Google AI Studio API (cloud, recommended)
    2. Vertex AI (enterprise)
    3. Local Ollama with medgemma model
    
    Example:
        service = MedGemmaService()
        result = await service.extract_medical_entities(
            text="Hemoglobin: 14.5 g/dL (Normal: 12-16)",
            document_type="lab_report"
        )
    """
    
    def __init__(
        self,
        model: MedGemmaModel = MedGemmaModel.GEMINI_PRO,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        mock_mode: Optional[bool] = None
    ):
        """
        Initialize MedGemma service.
        
        Args:
            model: MedGemma model variant to use
            api_key: API key for Google AI or custom endpoint
            base_url: Custom base URL (for Ollama or local deployment)
            mock_mode: Skip actual API calls (for testing)
        """
        self.model = model
        self.api_key = api_key or os.getenv('GOOGLE_AI_API_KEY')
        self.base_url = base_url or os.getenv(
            'MEDGEMMA_BASE_URL', 
            'https://generativelanguage.googleapis.com/v1beta'
        )
        
        # Mock mode
        if mock_mode is None:
            mock_mode = os.getenv('MEDGEMMA_MOCK_MODE', 'false').lower() == 'true'
        self.mock_mode = mock_mode or not self.api_key
        
        if self.mock_mode:
            logger.info("MedGemma service initialized in MOCK mode")
        else:
            logger.info(f"MedGemma service initialized: {model.value}")
    
    async def extract_medical_entities(
        self,
        text: str,
        document_type: str = "unknown",
        schema: Optional[Dict[str, Any]] = None
    ) -> ExtractionResult:
        """
        Extract medical entities from document text.
        
        Implements schema-driven extraction as per medical.md Section 3.
        
        Args:
            text: Document text (from OCR or direct)
            document_type: Type hint (lab_report, prescription, etc.)
            schema: Target JSON schema for extraction
        
        Returns:
            ExtractionResult with structured entities
        """
        start_time = time.time()
        
        if self.mock_mode:
            return self._mock_extraction(text, document_type, start_time)
        
        # Build prompt for schema-driven extraction
        prompt = self._build_extraction_prompt(text, document_type, schema)
        
        try:
            response = await self._call_model(prompt)
            entities = self._parse_extraction_response(response, schema)
            
            return ExtractionResult(
                entities=entities,
                raw_text=text[:500],  # First 500 chars for reference
                confidence=0.85,  # TODO: Calculate from response
                model_used=self.model.value,
                processing_time_ms=(time.time() - start_time) * 1000,
                document_type=document_type
            )
            
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            raise
    
    async def generate_patient_summary(
        self,
        text: str,
        patient_name: Optional[str] = None,
        reading_level: str = "simple"
    ) -> SummaryResult:
        """
        Generate patient-friendly summary of medical document.
        
        Converts medical jargon to plain language.
        
        Args:
            text: Medical document text
            patient_name: Patient name for personalization
            reading_level: Target reading level (simple, moderate, detailed)
        
        Returns:
            SummaryResult with plain language summary
        """
        if self.mock_mode:
            return self._mock_summary(text, reading_level)
        
        prompt = self._build_summary_prompt(text, patient_name, reading_level)
        
        try:
            response = await self._call_model(prompt)
            return self._parse_summary_response(response, text, reading_level)
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            raise
    
    async def normalize_terminology(
        self,
        text: str
    ) -> Dict[str, Any]:
        """
        Normalize medical abbreviations and terminology.
        
        Examples:
        - "BP" → "Blood Pressure"
        - "HbA1c" → "Hemoglobin A1c (3-month blood sugar average)"
        - "QID" → "Four times daily"
        
        Args:
            text: Text containing medical terminology
        
        Returns:
            Dict with normalized text and term mappings
        """
        if self.mock_mode:
            return self._mock_normalization(text)
        
        prompt = f"""Normalize the following medical text by:
1. Expanding all medical abbreviations
2. Adding brief explanations for medical terms in parentheses
3. Converting medical measurements to patient-friendly formats

Medical text:
{text}

Return JSON with:
- "normalized_text": The text with expansions
- "term_mappings": List of {{"abbreviation": "...", "expansion": "...", "explanation": "..."}}
"""
        
        try:
            response = await self._call_model(prompt)
            return json.loads(response)
        except Exception as e:
            logger.error(f"Terminology normalization failed: {e}")
            return {"normalized_text": text, "term_mappings": []}
    
    async def classify_document_sections(
        self,
        text: str,
        document_type: str
    ) -> List[Dict[str, Any]]:
        """
        Identify and classify sections within a medical document.
        
        Args:
            text: Full document text
            document_type: Type of document
        
        Returns:
            List of sections with type and content
        """
        prompt = f"""Analyze this {document_type} and identify its sections.

Document:
{text}

Return JSON array of sections:
[
  {{"section_type": "patient_info", "content": "...", "start_line": 1}},
  {{"section_type": "test_results", "content": "...", "start_line": 5}}
]

Possible section types: patient_info, test_results, medications, 
diagnosis, recommendations, doctor_info, billing, instructions
"""
        
        if self.mock_mode:
            return [{"section_type": "unknown", "content": text[:200]}]
        
        try:
            response = await self._call_model(prompt)
            return json.loads(response)
        except Exception as e:
            logger.error(f"Section classification failed: {e}")
            return []
    
    def _build_extraction_prompt(
        self,
        text: str,
        document_type: str,
        schema: Optional[Dict[str, Any]]
    ) -> str:
        """Build prompt for entity extraction."""
        schema_instruction = ""
        if schema:
            schema_instruction = f"""
Extract data into this exact JSON schema:
```json
{json.dumps(schema, indent=2)}
```
"""
        
        return f"""You are a medical document parser. Extract structured information from the following {document_type}.

IMPORTANT RULES:
1. Only extract information explicitly stated in the document
2. Use null for missing fields
3. Do not infer or assume values
4. Maintain exact values for lab results
5. Normalize dates to ISO format (YYYY-MM-DD)
6. Add confidence scores for uncertain extractions

{schema_instruction}

Document text:
{text}

Return valid JSON only. No additional text or explanations.
"""
    
    def _build_summary_prompt(
        self,
        text: str,
        patient_name: Optional[str],
        reading_level: str
    ) -> str:
        """Build prompt for patient summary."""
        name_part = f"for {patient_name}" if patient_name else ""
        
        level_instructions = {
            "simple": "Use 6th grade reading level. Short sentences. No medical jargon.",
            "moderate": "Use 10th grade reading level. Explain medical terms in parentheses.",
            "detailed": "Include more technical details but still explain complex terms."
        }
        
        return f"""Create a patient-friendly summary {name_part} of this medical document.

{level_instructions.get(reading_level, level_instructions['simple'])}

IMPORTANT:
- DO NOT provide medical advice
- DO NOT make diagnoses
- Highlight values that are outside normal range
- Include clear "Next Steps" if mentioned in document
- Add disclaimer that this is for informational purposes

Document:
{text}

Return JSON:
{{
  "summary": "2-3 paragraph plain language summary",
  "key_findings": ["finding 1", "finding 2"],
  "concerns": ["any values outside normal range"],
  "recommendations": ["next steps from document, NOT new advice"]
}}
"""
    
    async def _call_model(self, prompt: str) -> str:
        """Call MedGemma/Gemini model API."""
        if not self.api_key:
            raise ValueError("API key not configured")
        
        # Use Google Generative AI API
        url = f"{self.base_url}/models/{self.model.value}:generateContent"
        
        headers = {
            "Content-Type": "application/json",
        }
        
        params = {
            "key": self.api_key
        }
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,  # Low temperature for factual extraction
                "topP": 0.8,
                "maxOutputTokens": 4096
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, params=params, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"API call failed: {response.status} - {error_text}")
                
                result = await response.json()
                
                # Extract text from response
                candidates = result.get("candidates", [])
                if candidates:
                    content = candidates[0].get("content", {})
                    parts = content.get("parts", [])
                    if parts:
                        return parts[0].get("text", "")
                
                raise RuntimeError("No content in API response")
    
    def _mock_extraction(
        self, 
        text: str, 
        doc_type: str,
        start_time: float
    ) -> ExtractionResult:
        """Mock extraction for testing."""
        return ExtractionResult(
            entities=[
                {"type": "patient_name", "value": "Mock Patient", "confidence": 0.9},
                {"type": "document_type", "value": doc_type, "confidence": 0.85}
            ],
            raw_text=text[:200],
            confidence=0.8,
            model_used="mock",
            processing_time_ms=(time.time() - start_time) * 1000,
            document_type=doc_type
        )
    
    def _mock_summary(self, text: str, level: str) -> SummaryResult:
        """Mock summary for testing."""
        return SummaryResult(
            summary="This is a mock summary of the medical document. "
                    "In a production system, this would contain a patient-friendly "
                    "explanation of the document contents.",
            key_findings=["Mock finding 1", "Mock finding 2"],
            concerns=["No concerns identified (mock)"],
            recommendations=["Follow up with your healthcare provider"],
            reading_level=level,
            original_length=len(text),
            summary_length=200
        )
    
    def _mock_normalization(self, text: str) -> Dict[str, Any]:
        """Mock normalization for testing."""
        return {
            "normalized_text": text,
            "term_mappings": [
                {"abbreviation": "BP", "expansion": "Blood Pressure", "explanation": "Force of blood against artery walls"}
            ]
        }
    
    def _parse_extraction_response(
        self, 
        response: str, 
        schema: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Parse model response into entities."""
        try:
            # Try to parse as JSON
            # Handle markdown code blocks
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                response = response[start:end].strip()
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                response = response[start:end].strip()
            
            data = json.loads(response)
            
            # Convert to list of entities if it's a dict
            if isinstance(data, dict):
                entities = []
                for key, value in data.items():
                    if value is not None:
                        entities.append({
                            "type": key,
                            "value": value,
                            "confidence": 0.85
                        })
                return entities
            
            return data if isinstance(data, list) else [data]
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse extraction response: {e}")
            return [{"raw_response": response, "parse_error": str(e)}]
    
    def _parse_summary_response(
        self, 
        response: str, 
        original_text: str,
        reading_level: str
    ) -> SummaryResult:
        """Parse model response into summary result."""
        try:
            # Handle markdown code blocks
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                response = response[start:end].strip()
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                response = response[start:end].strip()
            
            data = json.loads(response)
            
            return SummaryResult(
                summary=data.get("summary", ""),
                key_findings=data.get("key_findings", []),
                concerns=data.get("concerns", []),
                recommendations=data.get("recommendations", []),
                reading_level=reading_level,
                original_length=len(original_text),
                summary_length=len(data.get("summary", ""))
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse summary response: {e}")
            return SummaryResult(
                summary=response,
                key_findings=[],
                concerns=[],
                recommendations=[],
                reading_level=reading_level,
                original_length=len(original_text),
                summary_length=len(response)
            )
