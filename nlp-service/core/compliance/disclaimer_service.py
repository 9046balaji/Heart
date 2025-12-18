"""
Medical Disclaimer Service.

Automatically adds required disclaimers to AI-generated content.
All patient-facing AI content MUST include appropriate disclaimers.

From medical.md:
- "For informational purposes only"
- "Not a substitute for professional medical advice"
- "Consult your healthcare provider"
"""

import logging
from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class DisclaimerType(Enum):
    """Types of medical disclaimers."""
    GENERAL = "general"
    PATIENT_SUMMARY = "patient_summary"
    LAB_RESULTS = "lab_results"
    MEDICATION = "medication"
    EXTRACTION = "extraction"
    HEALTH_ADVICE = "health_advice"
    RISK_ASSESSMENT = "risk_assessment"
    WEEKLY_SUMMARY = "weekly_summary"


class DisclaimerSeverity(Enum):
    """Severity levels for disclaimers."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Disclaimer:
    """A medical disclaimer."""
    type: DisclaimerType
    title: str
    text: str
    severity: DisclaimerSeverity
    short_text: Optional[str] = None  # For WhatsApp/SMS


class DisclaimerService:
    """
    Service for adding required medical disclaimers.
    
    All patient-facing AI content MUST include appropriate disclaimers
    as required by medical.md compliance requirements.
    """
    
    DISCLAIMERS: Dict[DisclaimerType, Disclaimer] = {
        DisclaimerType.GENERAL: Disclaimer(
            type=DisclaimerType.GENERAL,
            title="Medical Information Disclaimer",
            text=(
                "This information is provided for educational and informational purposes only. "
                "It is not intended to be a substitute for professional medical advice, diagnosis, "
                "or treatment. Always seek the advice of your physician or other qualified health "
                "provider with any questions you may have regarding a medical condition."
            ),
            severity=DisclaimerSeverity.WARNING,
            short_text="⚠️ For info only. Not medical advice. Consult your doctor."
        ),
        
        DisclaimerType.PATIENT_SUMMARY: Disclaimer(
            type=DisclaimerType.PATIENT_SUMMARY,
            title="Patient Summary Disclaimer",
            text=(
                "This summary is automatically generated from your health data and uploaded documents. "
                "While we strive for accuracy, AI-generated summaries may contain errors. "
                "All information should be verified by a healthcare professional before making "
                "any medical decisions. This summary does not replace professional medical advice."
            ),
            severity=DisclaimerSeverity.WARNING,
            short_text="⚠️ AI-generated summary. Verify with your doctor before acting."
        ),
        
        DisclaimerType.LAB_RESULTS: Disclaimer(
            type=DisclaimerType.LAB_RESULTS,
            title="Lab Results Disclaimer",
            text=(
                "Lab result interpretations are provided for informational purposes only. "
                "Reference ranges may vary between laboratories. Only your healthcare provider "
                "can properly interpret your results in the context of your overall health, "
                "medical history, and other factors. Abnormal results do not necessarily "
                "indicate a medical problem and should be discussed with your doctor."
            ),
            severity=DisclaimerSeverity.WARNING,
            short_text="⚠️ Lab interpretations are informational only. Consult your doctor."
        ),
        
        DisclaimerType.MEDICATION: Disclaimer(
            type=DisclaimerType.MEDICATION,
            title="Medication Information Disclaimer",
            text=(
                "Medication information extracted from documents is for reference only. "
                "Always follow your prescriber's instructions and the official medication guide. "
                "Do not change, start, or stop any medication without consulting your healthcare "
                "provider. Report any side effects to your doctor immediately."
            ),
            severity=DisclaimerSeverity.CRITICAL,
            short_text="🚨 Always follow your doctor's medication instructions."
        ),
        
        DisclaimerType.EXTRACTION: Disclaimer(
            type=DisclaimerType.EXTRACTION,
            title="Data Extraction Disclaimer",
            text=(
                "The data shown has been automatically extracted from your uploaded documents "
                "using AI and optical character recognition (OCR). While we use advanced technology, "
                "extraction errors may occur. Please verify all extracted information against your "
                "original documents. Human verification is recommended for critical data."
            ),
            severity=DisclaimerSeverity.INFO,
            short_text="ℹ️ AI-extracted data. Please verify against original documents."
        ),
        
        DisclaimerType.HEALTH_ADVICE: Disclaimer(
            type=DisclaimerType.HEALTH_ADVICE,
            title="Health Advice Disclaimer",
            text=(
                "Health recommendations and tips provided are general in nature and may not be "
                "appropriate for your specific situation. They are not a substitute for personalized "
                "medical advice from a qualified healthcare professional. Before making changes to "
                "your diet, exercise routine, or lifestyle, consult with your healthcare provider."
            ),
            severity=DisclaimerSeverity.WARNING,
            short_text="⚠️ General health tips only. Consult your doctor before changes."
        ),
        
        DisclaimerType.RISK_ASSESSMENT: Disclaimer(
            type=DisclaimerType.RISK_ASSESSMENT,
            title="Risk Assessment Disclaimer",
            text=(
                "Risk scores and assessments are generated by machine learning models based on "
                "available data. These predictions are statistical estimates and should not be "
                "interpreted as definitive diagnoses. Many factors influence health outcomes "
                "that may not be captured by our models. Discuss any concerns with your doctor."
            ),
            severity=DisclaimerSeverity.CRITICAL,
            short_text="🚨 Risk scores are estimates only. Discuss with your healthcare provider."
        ),
        
        DisclaimerType.WEEKLY_SUMMARY: Disclaimer(
            type=DisclaimerType.WEEKLY_SUMMARY,
            title="Weekly Summary Disclaimer",
            text=(
                "This weekly health summary is compiled from your tracked data, uploaded documents, "
                "and connected devices. It provides an overview of your health metrics but should "
                "not replace regular check-ups with your healthcare provider. If you notice "
                "concerning trends or symptoms, contact your doctor promptly."
            ),
            severity=DisclaimerSeverity.WARNING,
            short_text="⚠️ Weekly overview only. Regular check-ups still important."
        )
    }
    
    def __init__(self):
        """Initialize disclaimer service."""
        logger.info("DisclaimerService initialized")
    
    def get_disclaimer(self, disclaimer_type: DisclaimerType) -> Disclaimer:
        """
        Get a specific disclaimer.
        
        Args:
            disclaimer_type: Type of disclaimer to retrieve
            
        Returns:
            Disclaimer object
        """
        return self.DISCLAIMERS.get(disclaimer_type, self.DISCLAIMERS[DisclaimerType.GENERAL])
    
    def get_disclaimers_for_content(
        self,
        content_type: str
    ) -> List[Disclaimer]:
        """
        Get all applicable disclaimers for a content type.
        
        Args:
            content_type: Type of content (summary, lab_report, medication, etc.)
            
        Returns:
            List of applicable disclaimers
        """
        content_type_lower = content_type.lower()
        
        # Map content types to disclaimers
        disclaimer_mapping = {
            "summary": [DisclaimerType.PATIENT_SUMMARY, DisclaimerType.GENERAL],
            "patient_summary": [DisclaimerType.PATIENT_SUMMARY, DisclaimerType.GENERAL],
            "weekly_summary": [DisclaimerType.WEEKLY_SUMMARY, DisclaimerType.GENERAL],
            "lab_report": [DisclaimerType.LAB_RESULTS, DisclaimerType.EXTRACTION],
            "lab_results": [DisclaimerType.LAB_RESULTS, DisclaimerType.EXTRACTION],
            "medication": [DisclaimerType.MEDICATION, DisclaimerType.EXTRACTION],
            "prescription": [DisclaimerType.MEDICATION, DisclaimerType.EXTRACTION],
            "extraction": [DisclaimerType.EXTRACTION],
            "health_advice": [DisclaimerType.HEALTH_ADVICE, DisclaimerType.GENERAL],
            "recommendation": [DisclaimerType.HEALTH_ADVICE],
            "risk_assessment": [DisclaimerType.RISK_ASSESSMENT, DisclaimerType.GENERAL],
            "prediction": [DisclaimerType.RISK_ASSESSMENT],
            "discharge_summary": [DisclaimerType.PATIENT_SUMMARY, DisclaimerType.EXTRACTION],
            "medical_bill": [DisclaimerType.EXTRACTION],
        }
        
        disclaimer_types = disclaimer_mapping.get(
            content_type_lower, 
            [DisclaimerType.GENERAL]
        )
        
        return [self.DISCLAIMERS[t] for t in disclaimer_types]
    
    def wrap_with_disclaimer(
        self,
        content: str,
        content_type: str,
        format: str = "text"
    ) -> str:
        """
        Wrap content with appropriate disclaimers.
        
        Args:
            content: The content to wrap
            content_type: Type of content for disclaimer selection
            format: Output format (text, markdown, html, whatsapp)
            
        Returns:
            Content wrapped with disclaimers
        """
        disclaimers = self.get_disclaimers_for_content(content_type)
        
        format_lower = format.lower()
        
        if format_lower == "markdown":
            return self._format_markdown(content, disclaimers)
        elif format_lower == "html":
            return self._format_html(content, disclaimers)
        elif format_lower == "whatsapp":
            return self._format_whatsapp(content, disclaimers)
        else:
            return self._format_text(content, disclaimers)
    
    def _format_text(self, content: str, disclaimers: List[Disclaimer]) -> str:
        """Format as plain text."""
        header = "=" * 50
        
        disclaimer_parts = []
        for d in disclaimers:
            disclaimer_parts.append(f"⚠️ {d.title.upper()}")
            disclaimer_parts.append(d.text)
            disclaimer_parts.append("")
        
        disclaimer_text = "\n".join(disclaimer_parts)
        
        return f"{header}\n{disclaimer_text}{header}\n\n{content}\n\n{header}\nEND OF SUMMARY\n{header}"
    
    def _format_markdown(self, content: str, disclaimers: List[Disclaimer]) -> str:
        """Format as markdown."""
        disclaimer_parts = []
        
        for d in disclaimers:
            icon = self._get_severity_icon(d.severity)
            disclaimer_parts.append(f"> {icon} **{d.title}**")
            disclaimer_parts.append(f"> ")
            disclaimer_parts.append(f"> {d.text}")
            disclaimer_parts.append("")
        
        disclaimer_md = "\n".join(disclaimer_parts)
        
        return f"{disclaimer_md}\n---\n\n{content}"
    
    def _format_html(self, content: str, disclaimers: List[Disclaimer]) -> str:
        """Format as HTML."""
        disclaimer_parts = []
        
        for d in disclaimers:
            bg_color = self._get_severity_color(d.severity)
            disclaimer_parts.append(f'''
<div style="background-color: {bg_color}; padding: 16px; border-radius: 8px; margin-bottom: 16px; border-left: 4px solid #333;">
    <strong style="display: block; margin-bottom: 8px;">{d.title}</strong>
    <p style="margin: 0; font-size: 14px;">{d.text}</p>
</div>
''')
        
        disclaimer_html = "\n".join(disclaimer_parts)
        
        return f'{disclaimer_html}<div class="content">{content}</div>'
    
    def _format_whatsapp(self, content: str, disclaimers: List[Disclaimer]) -> str:
        """Format for WhatsApp (short disclaimers)."""
        # Use only the first/most important disclaimer in short form
        if disclaimers:
            primary_disclaimer = disclaimers[0]
            short_text = primary_disclaimer.short_text or f"⚠️ {primary_disclaimer.title}"
            return f"{short_text}\n\n{content}"
        
        return content
    
    def get_short_disclaimer(self, content_type: str) -> str:
        """
        Get a short disclaimer for space-constrained contexts.
        
        Args:
            content_type: Type of content
            
        Returns:
            Short disclaimer text
        """
        disclaimers = self.get_disclaimers_for_content(content_type)
        if disclaimers:
            return disclaimers[0].short_text or f"⚠️ {disclaimers[0].title}"
        return "⚠️ For informational purposes only."
    
    def _get_severity_icon(self, severity: DisclaimerSeverity) -> str:
        """Get icon for severity level."""
        icons = {
            DisclaimerSeverity.INFO: "ℹ️",
            DisclaimerSeverity.WARNING: "⚠️",
            DisclaimerSeverity.CRITICAL: "🚨"
        }
        return icons.get(severity, "⚠️")
    
    def _get_severity_color(self, severity: DisclaimerSeverity) -> str:
        """Get background color for severity level."""
        colors = {
            DisclaimerSeverity.INFO: "#e3f2fd",      # Light blue
            DisclaimerSeverity.WARNING: "#fff3e0",   # Light orange
            DisclaimerSeverity.CRITICAL: "#ffebee"   # Light red
        }
        return colors.get(severity, "#fff3e0")


# Global instance
disclaimer_service = DisclaimerService()


def get_disclaimer_service() -> DisclaimerService:
    """Get the global disclaimer service instance."""
    return disclaimer_service
