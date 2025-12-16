"""
Medical Terminology Normalization.

Converts abbreviations and medical jargon to plain language.
Essential for patient-friendly summaries and document understanding.
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import re


@dataclass
class TermMapping:
    """Mapping of medical term to plain language."""
    abbreviation: str
    full_term: str
    plain_explanation: str
    category: str  # "vital", "lab", "medication", "procedure", "diagnosis"


class MedicalTerminologyNormalizer:
    """
    Normalizes medical terminology for patient understanding.
    
    Maintains a dictionary of common medical abbreviations
    and their plain-language equivalents.
    
    Example:
        normalizer = MedicalTerminologyNormalizer()
        text = "BP: 120/80, HR: 72 bpm, HbA1c: 6.5%"
        normalized, mappings = normalizer.normalize_text(text)
        # normalized: "Blood Pressure: 120/80, Heart Rate: 72 beats per minute, ..."
    """
    
    # Common medical abbreviations organized by category
    ABBREVIATIONS: Dict[str, TermMapping] = {
        # Vitals
        "BP": TermMapping("BP", "Blood Pressure", "Force of blood against your artery walls", "vital"),
        "HR": TermMapping("HR", "Heart Rate", "Number of heartbeats per minute", "vital"),
        "RR": TermMapping("RR", "Respiratory Rate", "Number of breaths per minute", "vital"),
        "SpO2": TermMapping("SpO2", "Oxygen Saturation", "Amount of oxygen in your blood", "vital"),
        "T": TermMapping("T", "Temperature", "Body temperature", "vital"),
        "Temp": TermMapping("Temp", "Temperature", "Body temperature", "vital"),
        "BMI": TermMapping("BMI", "Body Mass Index", "Measure of body fat based on height and weight", "vital"),
        
        # Lab - Blood Count
        "CBC": TermMapping("CBC", "Complete Blood Count", "Test that measures blood cells", "lab"),
        "RBC": TermMapping("RBC", "Red Blood Cells", "Cells that carry oxygen", "lab"),
        "WBC": TermMapping("WBC", "White Blood Cells", "Cells that fight infection", "lab"),
        "Hb": TermMapping("Hb", "Hemoglobin", "Protein in red blood cells that carries oxygen", "lab"),
        "Hgb": TermMapping("Hgb", "Hemoglobin", "Protein in red blood cells that carries oxygen", "lab"),
        "HCT": TermMapping("HCT", "Hematocrit", "Percentage of red blood cells in blood", "lab"),
        "PLT": TermMapping("PLT", "Platelets", "Cells that help blood clot", "lab"),
        "MCV": TermMapping("MCV", "Mean Corpuscular Volume", "Average size of red blood cells", "lab"),
        "MCH": TermMapping("MCH", "Mean Corpuscular Hemoglobin", "Average hemoglobin per red blood cell", "lab"),
        "MCHC": TermMapping("MCHC", "Mean Corpuscular Hemoglobin Concentration", "Hemoglobin concentration in red blood cells", "lab"),
        
        # Lab - Chemistry
        "BMP": TermMapping("BMP", "Basic Metabolic Panel", "Test for kidney function and electrolytes", "lab"),
        "CMP": TermMapping("CMP", "Comprehensive Metabolic Panel", "Extended chemistry test", "lab"),
        "BUN": TermMapping("BUN", "Blood Urea Nitrogen", "Waste product filtered by kidneys", "lab"),
        "Cr": TermMapping("Cr", "Creatinine", "Waste product from muscle activity", "lab"),
        "GFR": TermMapping("GFR", "Glomerular Filtration Rate", "How well kidneys filter blood", "lab"),
        "eGFR": TermMapping("eGFR", "Estimated Glomerular Filtration Rate", "Estimated kidney function", "lab"),
        "Na": TermMapping("Na", "Sodium", "Electrolyte for fluid balance", "lab"),
        "K": TermMapping("K", "Potassium", "Electrolyte for heart and muscle function", "lab"),
        "Cl": TermMapping("Cl", "Chloride", "Electrolyte for fluid balance", "lab"),
        "CO2": TermMapping("CO2", "Carbon Dioxide/Bicarbonate", "Measure of blood acidity", "lab"),
        "Ca": TermMapping("Ca", "Calcium", "Mineral for bones and muscles", "lab"),
        "Mg": TermMapping("Mg", "Magnesium", "Mineral for nerve and muscle function", "lab"),
        
        # Lab - Liver
        "LFT": TermMapping("LFT", "Liver Function Tests", "Tests for liver health", "lab"),
        "AST": TermMapping("AST", "Aspartate Aminotransferase", "Liver enzyme", "lab"),
        "ALT": TermMapping("ALT", "Alanine Aminotransferase", "Liver enzyme", "lab"),
        "SGOT": TermMapping("SGOT", "Serum Glutamic-Oxaloacetic Transaminase", "Liver enzyme (same as AST)", "lab"),
        "SGPT": TermMapping("SGPT", "Serum Glutamic-Pyruvic Transaminase", "Liver enzyme (same as ALT)", "lab"),
        "ALP": TermMapping("ALP", "Alkaline Phosphatase", "Enzyme from liver and bones", "lab"),
        "GGT": TermMapping("GGT", "Gamma-Glutamyl Transferase", "Liver enzyme", "lab"),
        "T.Bil": TermMapping("T.Bil", "Total Bilirubin", "Yellow pigment from red blood cell breakdown", "lab"),
        "D.Bil": TermMapping("D.Bil", "Direct Bilirubin", "Bilirubin processed by liver", "lab"),
        "Alb": TermMapping("Alb", "Albumin", "Protein made by liver", "lab"),
        
        # Lab - Lipids
        "TC": TermMapping("TC", "Total Cholesterol", "Total amount of cholesterol in blood", "lab"),
        "TG": TermMapping("TG", "Triglycerides", "Type of fat in blood", "lab"),
        "HDL": TermMapping("HDL", "High-Density Lipoprotein", "Good cholesterol", "lab"),
        "LDL": TermMapping("LDL", "Low-Density Lipoprotein", "Bad cholesterol", "lab"),
        "VLDL": TermMapping("VLDL", "Very Low-Density Lipoprotein", "Carries triglycerides", "lab"),
        
        # Lab - Thyroid
        "TSH": TermMapping("TSH", "Thyroid Stimulating Hormone", "Controls thyroid function", "lab"),
        "T3": TermMapping("T3", "Triiodothyronine", "Thyroid hormone", "lab"),
        "T4": TermMapping("T4", "Thyroxine", "Thyroid hormone", "lab"),
        "FT3": TermMapping("FT3", "Free T3", "Active thyroid hormone", "lab"),
        "FT4": TermMapping("FT4", "Free T4", "Active thyroid hormone", "lab"),
        
        # Lab - Diabetes
        "FBS": TermMapping("FBS", "Fasting Blood Sugar", "Blood sugar after overnight fast", "lab"),
        "RBS": TermMapping("RBS", "Random Blood Sugar", "Blood sugar at any time", "lab"),
        "PPBS": TermMapping("PPBS", "Post-Prandial Blood Sugar", "Blood sugar after eating", "lab"),
        "HbA1c": TermMapping("HbA1c", "Glycated Hemoglobin", "Average blood sugar over 3 months", "lab"),
        "A1c": TermMapping("A1c", "Hemoglobin A1c", "Average blood sugar over 3 months", "lab"),
        "GTT": TermMapping("GTT", "Glucose Tolerance Test", "Test for diabetes", "lab"),
        "OGTT": TermMapping("OGTT", "Oral Glucose Tolerance Test", "Diabetes screening test", "lab"),
        
        # Lab - Cardiac
        "CK": TermMapping("CK", "Creatine Kinase", "Enzyme from muscles and heart", "lab"),
        "CK-MB": TermMapping("CK-MB", "Creatine Kinase-MB", "Heart-specific enzyme", "lab"),
        "LDH": TermMapping("LDH", "Lactate Dehydrogenase", "Enzyme indicating tissue damage", "lab"),
        "BNP": TermMapping("BNP", "B-type Natriuretic Peptide", "Heart failure marker", "lab"),
        "CRP": TermMapping("CRP", "C-Reactive Protein", "Inflammation marker", "lab"),
        "ESR": TermMapping("ESR", "Erythrocyte Sedimentation Rate", "Inflammation marker", "lab"),
        
        # Lab - Urine
        "UA": TermMapping("UA", "Urinalysis", "Urine test", "lab"),
        "UTI": TermMapping("UTI", "Urinary Tract Infection", "Infection in urinary system", "lab"),
        
        # Medication Frequency
        "OD": TermMapping("OD", "Once Daily", "Take once a day", "medication"),
        "BD": TermMapping("BD", "Twice Daily", "Take twice a day", "medication"),
        "BID": TermMapping("BID", "Twice Daily", "Take twice a day", "medication"),
        "TID": TermMapping("TID", "Three Times Daily", "Take three times a day", "medication"),
        "QID": TermMapping("QID", "Four Times Daily", "Take four times a day", "medication"),
        "HS": TermMapping("HS", "At Bedtime", "Take at night before sleeping", "medication"),
        "PRN": TermMapping("PRN", "As Needed", "Take when needed", "medication"),
        "SOS": TermMapping("SOS", "If Needed", "Take if required", "medication"),
        "AC": TermMapping("AC", "Before Meals", "Take before eating", "medication"),
        "PC": TermMapping("PC", "After Meals", "Take after eating", "medication"),
        "STAT": TermMapping("STAT", "Immediately", "Take right away", "medication"),
        
        # Medication Forms
        "Tab": TermMapping("Tab", "Tablet", "Solid pill form", "medication"),
        "Cap": TermMapping("Cap", "Capsule", "Medicine in a shell", "medication"),
        "Inj": TermMapping("Inj", "Injection", "Medicine given by needle", "medication"),
        "Syr": TermMapping("Syr", "Syrup", "Liquid medicine", "medication"),
        "PO": TermMapping("PO", "By Mouth", "Taken orally", "medication"),
        "IV": TermMapping("IV", "Intravenous", "Given into vein", "medication"),
        "IM": TermMapping("IM", "Intramuscular", "Given into muscle", "medication"),
        "SC": TermMapping("SC", "Subcutaneous", "Given under skin", "medication"),
        
        # Units
        "mg": TermMapping("mg", "milligrams", "Unit of weight (1/1000 gram)", "unit"),
        "mcg": TermMapping("mcg", "micrograms", "Unit of weight (1/1000 milligram)", "unit"),
        "mL": TermMapping("mL", "milliliters", "Unit of volume (1/1000 liter)", "unit"),
        "IU": TermMapping("IU", "International Units", "Standardized unit for vitamins/medicines", "unit"),
        "bpm": TermMapping("bpm", "beats per minute", "Heart rate measurement", "unit"),
        "mmHg": TermMapping("mmHg", "millimeters of mercury", "Blood pressure unit", "unit"),
        "g/dL": TermMapping("g/dL", "grams per deciliter", "Concentration unit", "unit"),
        "mg/dL": TermMapping("mg/dL", "milligrams per deciliter", "Concentration unit", "unit"),
        "mmol/L": TermMapping("mmol/L", "millimoles per liter", "Concentration unit", "unit"),
        
        # Common Diagnoses
        "HTN": TermMapping("HTN", "Hypertension", "High blood pressure", "diagnosis"),
        "DM": TermMapping("DM", "Diabetes Mellitus", "Diabetes - high blood sugar condition", "diagnosis"),
        "T2DM": TermMapping("T2DM", "Type 2 Diabetes Mellitus", "Most common form of diabetes", "diagnosis"),
        "CAD": TermMapping("CAD", "Coronary Artery Disease", "Heart artery blockage", "diagnosis"),
        "CHF": TermMapping("CHF", "Congestive Heart Failure", "Heart not pumping well", "diagnosis"),
        "COPD": TermMapping("COPD", "Chronic Obstructive Pulmonary Disease", "Lung disease causing breathing difficulty", "diagnosis"),
        "CKD": TermMapping("CKD", "Chronic Kidney Disease", "Long-term kidney damage", "diagnosis"),
        "MI": TermMapping("MI", "Myocardial Infarction", "Heart attack", "diagnosis"),
        "CVA": TermMapping("CVA", "Cerebrovascular Accident", "Stroke", "diagnosis"),
        "AF": TermMapping("AF", "Atrial Fibrillation", "Irregular heartbeat", "diagnosis"),
        "GERD": TermMapping("GERD", "Gastroesophageal Reflux Disease", "Acid reflux", "diagnosis"),
        
        # Procedures
        "ECG": TermMapping("ECG", "Electrocardiogram", "Heart electrical activity test", "procedure"),
        "EKG": TermMapping("EKG", "Electrocardiogram", "Heart electrical activity test", "procedure"),
        "ECHO": TermMapping("ECHO", "Echocardiogram", "Heart ultrasound", "procedure"),
        "CT": TermMapping("CT", "Computed Tomography", "Detailed X-ray scan", "procedure"),
        "MRI": TermMapping("MRI", "Magnetic Resonance Imaging", "Detailed body scan using magnets", "procedure"),
        "USG": TermMapping("USG", "Ultrasonography", "Ultrasound imaging", "procedure"),
    }
    
    def __init__(self):
        """Initialize normalizer with compiled patterns."""
        # Compile patterns for efficient matching
        self._patterns = {}
        for abbr, mapping in self.ABBREVIATIONS.items():
            # Match whole word or followed by punctuation/colon
            pattern = re.compile(
                rf'\b{re.escape(abbr)}\b(?:\s*:)?',
                re.IGNORECASE
            )
            self._patterns[abbr] = pattern
    
    def normalize_text(
        self,
        text: str,
        add_explanations: bool = True,
        explanation_format: str = "parentheses"
    ) -> Tuple[str, List[TermMapping]]:
        """
        Normalize medical terminology in text.
        
        Args:
            text: Text containing medical terminology
            add_explanations: Whether to add explanations
            explanation_format: "parentheses", "footnote", or "inline"
        
        Returns:
            Tuple of (normalized_text, list_of_term_mappings_used)
        """
        normalized = text
        used_mappings: List[TermMapping] = []
        
        for abbr, pattern in self._patterns.items():
            if pattern.search(normalized):
                mapping = self.ABBREVIATIONS[abbr]
                
                if add_explanations:
                    if explanation_format == "parentheses":
                        replacement = f"{mapping.full_term} ({mapping.plain_explanation})"
                    elif explanation_format == "inline":
                        replacement = f"{mapping.full_term}"
                    else:
                        replacement = mapping.full_term
                else:
                    replacement = mapping.full_term
                
                # Preserve the colon if it was there
                def replace_with_colon(match):
                    if ':' in match.group(0):
                        return replacement + ':'
                    return replacement
                
                normalized = pattern.sub(replace_with_colon, normalized)
                used_mappings.append(mapping)
        
        return normalized, used_mappings
    
    def get_term_explanation(self, term: str) -> Optional[TermMapping]:
        """Get explanation for a specific term."""
        return self.ABBREVIATIONS.get(term.upper())
    
    def add_custom_term(self, mapping: TermMapping) -> None:
        """Add custom term mapping."""
        self.ABBREVIATIONS[mapping.abbreviation.upper()] = mapping
        pattern = re.compile(
            rf'\b{re.escape(mapping.abbreviation)}\b(?:\s*:)?',
            re.IGNORECASE
        )
        self._patterns[mapping.abbreviation.upper()] = pattern
    
    def get_terms_by_category(self, category: str) -> List[TermMapping]:
        """Get all terms in a category."""
        return [
            mapping for mapping in self.ABBREVIATIONS.values()
            if mapping.category == category
        ]
    
    def extract_medical_terms(self, text: str) -> List[TermMapping]:
        """
        Extract all recognized medical terms from text.
        
        Args:
            text: Text to analyze
            
        Returns:
            List of recognized medical term mappings
        """
        found_terms = []
        for abbr, pattern in self._patterns.items():
            if pattern.search(text):
                found_terms.append(self.ABBREVIATIONS[abbr])
        return found_terms


# Convenience function
def normalize_medical_text(text: str) -> str:
    """
    Quick normalization of medical text.
    
    Args:
        text: Text with medical abbreviations
        
    Returns:
        Text with expanded abbreviations
    """
    normalizer = MedicalTerminologyNormalizer()
    normalized, _ = normalizer.normalize_text(text, add_explanations=False)
    return normalized
