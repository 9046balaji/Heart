"""
Medical Document Type Classifier.

Classifies documents into:
- Lab Reports
- Prescriptions
- Medical Bills
- Discharge Summaries
- Imaging Reports

Uses pattern matching with option for ML model enhancement.
"""

import re
from typing import Dict, List
from enum import Enum
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


class DocumentCategory(Enum):
    """Medical document categories."""

    LAB_REPORT = "lab_report"
    PRESCRIPTION = "prescription"
    MEDICAL_BILL = "medical_bill"
    DISCHARGE_SUMMARY = "discharge_summary"
    IMAGING_REPORT = "imaging_report"
    CONSULTATION_NOTE = "consultation_note"
    UNKNOWN = "unknown"


@dataclass
class ClassificationResult:
    """Result of document classification."""

    category: DocumentCategory
    confidence: float
    matched_patterns: List[str]
    sections_detected: List[str] = field(default_factory=list)


class MedicalDocumentClassifier:
    """
    Classifies medical documents based on content patterns.

    Uses keyword matching and pattern recognition.
    Can be enhanced with ML models for better accuracy.

    Example:
        classifier = MedicalDocumentClassifier()
        result = classifier.classify(ocr_text)
        print(f"Document type: {result.category.value}")
        print(f"Confidence: {result.confidence:.2%}")
    """

    # Pattern dictionaries for each document type
    LAB_REPORT_PATTERNS = [
        r"\b(lab|laboratory)\s*(report|result|test)",
        r"\b(blood|urine|serum|plasma)\s*(test|analysis)",
        r"\b(cbc|complete\s*blood\s*count)",
        r"\b(lipid\s*profile|lipid\s*panel)",
        r"\b(hemoglobin|haemoglobin|hb|hgb)\b",
        r"\b(reference\s*range|normal\s*range)",
        r"\bspecimen\s*(type|collected)",
        r"\b(creatinine|bun|gfr)\b",
        r"\b(hba1c|glycated\s*hemoglobin)",
        r"\b(wbc|rbc|platelet)\s*count",
        r"\b(tsh|thyroid)",
        r"\b(ast|alt|sgpt|sgot)\b",
    ]

    PRESCRIPTION_PATTERNS = [
        r"\b(prescription|rx)\b",
        r"\b(tablet|tab|capsule|cap|syrup|injection|inj)\b",
        r"\b(mg|mcg|ml|iu)\b",
        r"\b(once|twice|thrice)\s*(daily|a\s*day)",
        r"\b(od|bd|tid|qid|sos|prn)\b",
        r"\b(before|after)\s*(meal|food|breakfast|lunch|dinner)",
        r"\b(morning|evening|night|bedtime)\b",
        r"\bduration\s*:\s*\d+\s*(day|week|month)",
        r"\brefill",
        r"\bdispense",
    ]

    BILL_PATTERNS = [
        r"\b(bill|invoice|statement|receipt)",
        r"\b(charges?|fees?|amount|total)\s*:?\s*\$?\d",
        r"\b(payment|paid|balance\s*due)",
        r"\b(insurance|claim|coverage)",
        r"\b(consultation\s*fee|room\s*charge)",
        r"\b(pharmacy|medication\s*charge)",
        r"\b(balance|due|paid)",
        r"\b(gst|tax|vat|discount)",
        r"\b(patient\s*id|mrn|account)",
        r"\bhospital\s*registration",
    ]

    DISCHARGE_PATTERNS = [
        r"\b(discharge)\s*(summary|note|instructions)",
        r"\badmission\s*(date|diagnosis)",
        r"\bdischarged?\s*(on|date)",
        r"\b(principal|primary|final)\s*diagnosis",
        r"\b(treatment\s*given|procedures?\s*performed)",
        r"\b(home\s*care|instructions)",
        r"\bfollow[\s-]?up",
        r"\b(condition\s*at\s*discharge|outcome)",
        r"\b(advice\s*on\s*discharge)",
        r"\binpatient\s*(care|stay)",
    ]

    IMAGING_PATTERNS = [
        r"\b(x-ray|xray|x\s*ray)",
        r"\b(ct\s*scan|computed\s*tomography)",
        r"\b(mri|magnetic\s*resonance)",
        r"\b(ultrasound|sonography|usg)",
        r"\b(ecg|ekg|electrocardiogram)",
        r"\b(echo|echocardiogram)",
        r"\b(mammogram|mammography)",
        r"\b(pet\s*scan|nuclear)",
        r"\b(normal\s*study|no\s*abnormality)",
        r"\b(impression|findings|conclusion)",
        r"\b(radiologist|reporting\s*doctor)",
    ]

    CONSULTATION_PATTERNS = [
        r"\bconsultation\s*(note|report)",
        r"\b(chief\s*complaint|presenting\s*complaint)",
        r"\b(history\s*of\s*present\s*illness|hpi)",
        r"\b(physical\s*examination|examination\s*findings)",
        r"\b(assessment|impression|diagnosis)",
        r"\b(plan|recommendation|advised)",
        r"\b(vitals?|vital\s*signs)",
    ]

    def __init__(self):
        """Initialize classifier with pattern dictionaries."""
        self.category_patterns: Dict[DocumentCategory, List[re.Pattern]] = {
            DocumentCategory.LAB_REPORT: [
                re.compile(p, re.IGNORECASE) for p in self.LAB_REPORT_PATTERNS
            ],
            DocumentCategory.PRESCRIPTION: [
                re.compile(p, re.IGNORECASE) for p in self.PRESCRIPTION_PATTERNS
            ],
            DocumentCategory.MEDICAL_BILL: [
                re.compile(p, re.IGNORECASE) for p in self.BILL_PATTERNS
            ],
            DocumentCategory.DISCHARGE_SUMMARY: [
                re.compile(p, re.IGNORECASE) for p in self.DISCHARGE_PATTERNS
            ],
            DocumentCategory.IMAGING_REPORT: [
                re.compile(p, re.IGNORECASE) for p in self.IMAGING_PATTERNS
            ],
            DocumentCategory.CONSULTATION_NOTE: [
                re.compile(p, re.IGNORECASE) for p in self.CONSULTATION_PATTERNS
            ],
        }

        # Section patterns for structure detection
        self.section_patterns = {
            "patient_info": re.compile(
                r"\b(patient\s*(name|info|details)|name\s*:|age\s*:|gender\s*:)", re.I
            ),
            "test_results": re.compile(
                r"\b(test\s*results?|lab\s*values?|parameters?)", re.I
            ),
            "medications": re.compile(r"\b(medications?|medicines?|drugs?|rx)", re.I),
            "diagnosis": re.compile(r"\b(diagnosis|impression|assessment)", re.I),
            "recommendations": re.compile(
                r"\b(recommendations?|advice|plan|follow[\s-]?up)", re.I
            ),
            "doctor_info": re.compile(
                r"\b(doctor|physician|dr\.|consultant|referred)", re.I
            ),
            "billing": re.compile(r"\b(charges?|fees?|total|amount|payment)", re.I),
            "instructions": re.compile(
                r"\b(instructions?|advice|precautions?|warnings?)", re.I
            ),
        }

    def classify(self, text: str) -> ClassificationResult:
        """
        Classify a medical document based on text content.

        Args:
            text: Extracted text from document

        Returns:
            ClassificationResult with category, confidence, and matched patterns
        """
        if not text or not text.strip():
            return ClassificationResult(
                category=DocumentCategory.UNKNOWN,
                confidence=0.0,
                matched_patterns=[],
                sections_detected=[],
            )

        # Score each category
        category_scores: Dict[DocumentCategory, List[str]] = {}

        for category, patterns in self.category_patterns.items():
            matches = []
            for pattern in patterns:
                found = pattern.findall(text)
                if found:
                    matches.append(pattern.pattern)
            category_scores[category] = matches

        # Find best category
        best_category = DocumentCategory.UNKNOWN
        best_score = 0
        best_matches: List[str] = []

        for category, matches in category_scores.items():
            score = len(matches)
            if score > best_score:
                best_score = score
                best_category = category
                best_matches = matches

        # Calculate confidence (normalized by expected matches)
        expected_matches = 5  # A good document should match ~5 patterns
        confidence = min(1.0, best_score / expected_matches) if best_score > 0 else 0

        # If confidence is low, mark as unknown
        if confidence < 0.2:
            best_category = DocumentCategory.UNKNOWN

        # Detect sections
        sections = self._detect_sections(text, best_category)

        logger.info(
            f"Classified document as {best_category.value} with confidence {confidence:.2%}"
        )

        return ClassificationResult(
            category=best_category,
            confidence=confidence,
            matched_patterns=best_matches,
            sections_detected=sections,
        )

    def _detect_sections(self, text: str, category: DocumentCategory) -> List[str]:
        """Detect document sections based on category."""
        sections = []

        for section_name, pattern in self.section_patterns.items():
            if pattern.search(text):
                sections.append(section_name)

        return sections

    def get_category_confidence(self, text: str, category: DocumentCategory) -> float:
        """
        Get confidence score for a specific category.

        Useful when you suspect a document type and want to verify.

        Args:
            text: Document text
            category: Category to check

        Returns:
            Confidence score (0.0 - 1.0)
        """
        if category not in self.category_patterns:
            return 0.0

        patterns = self.category_patterns[category]
        matches = sum(1 for p in patterns if p.search(text))

        return min(1.0, matches / len(patterns))

    def extract_sections(self, text: str) -> Dict[str, str]:
        """
        Extract content for each detected section.

        Args:
            text: Document text

        Returns:
            Dictionary mapping section names to content
        """
        # Split text into lines
        lines = text.split("\n")

        # Find section boundaries
        section_starts = {}
        for i, line in enumerate(lines):
            for section_name, pattern in self.section_patterns.items():
                if pattern.search(line):
                    section_starts[i] = section_name

        # Extract section content
        sections = {}
        sorted_starts = sorted(section_starts.items())

        for idx, (start_line, section_name) in enumerate(sorted_starts):
            # Find end of section
            if idx + 1 < len(sorted_starts):
                end_line = sorted_starts[idx + 1][0]
            else:
                end_line = len(lines)

            content = "\n".join(lines[start_line:end_line]).strip()
            sections[section_name] = content

        return sections


# Convenience function for quick classification
def classify_document(text: str) -> ClassificationResult:
    """
    Quick classification of medical document text.

    Args:
        text: Document text

    Returns:
        ClassificationResult
    """
    classifier = MedicalDocumentClassifier()
    return classifier.classify(text)
