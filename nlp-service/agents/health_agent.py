"""
Health data collection and validation agents.
Extracts structured health data from user input and validates against medical standards.

Phase 2: Health Agents
"""

import re
import logging
from typing import Optional, Dict, List, Tuple
from datetime import datetime

from agents.base import BaseAgent
from models.health import (
    HealthRecord,
    VitalSigns,
    MedicationRecord,
    Allergy,
    VitalSignsType,
    MedicationFrequency,
    AllergyReactionSeverity,
)
from services.health_service import get_health_service

logger = logging.getLogger(__name__)


# ============================================================================
# HEALTH DATA COLLECTOR AGENT
# ============================================================================


class HealthDataCollectorAgent(BaseAgent):
    """
    Collects and structures health data from user input.
    Uses pattern matching and NLP to extract vitals, medications, and symptoms.
    """
    
    def __init__(self):
        """Initialize health data collector agent."""
        super().__init__(
            agent_type="HealthDataCollector",
            description="Collects structured health data from user input"
        )
        
        # Define vital sign patterns
        self.vital_patterns = {
            'heart_rate': r'(?:heart\s+rate|hr|bpm|pulse)[\s:]*(\d+)',
            'blood_pressure_systolic': r'(?:blood\s+pressure|bp)[\s:]*(\d+)[\s/]*',
            'blood_pressure_diastolic': r'(?:blood\s+pressure|bp)[\s:]*\d+\s*[/-]\s*(\d+)',
            'temperature': r'(?:temp|temperature)[\s:]*(\d+\.?\d*)',
            'respiratory_rate': r'(?:respiratory\s+rate|rr|breaths?)[\s:]*(\d+)',
            'oxygen_saturation': r'(?:o2\s+sat|oxygen|spo2)[\s:]*(\d+)',
        }
        
        # Define medication patterns
        self.medication_patterns = r'(?:on|taking|medication|drug)[\s:]*([^,.\n]+)'
        
        # Define symptom patterns
        self.symptom_keywords = [
            'headache', 'fever', 'cough', 'fatigue', 'nausea', 'dizziness',
            'chest pain', 'shortness of breath', 'sore throat', 'body aches',
            'chills', 'sweating', 'congestion', 'rash'
        ]
    
    async def execute(self, user_input: str, patient_id: str) -> Dict:
        """
        Extract structured health data from user input.
        
        Args:
            user_input: Raw user input text
            patient_id: Patient ID for the record
            
        Returns:
            Dictionary with extracted health data
        """
        try:
            self.log_action("extract_health_data", f"patient={patient_id}")
            
            # Extract vital signs
            vitals = self._extract_vitals(user_input)
            
            # Extract medications
            medications = self._extract_medications(user_input)
            
            # Extract symptoms
            symptoms = self._extract_symptoms(user_input)
            
            # Extract allergies
            allergies = self._extract_allergies(user_input)
            
            # Build response
            result = {
                "patient_id": patient_id,
                "vitals": vitals,
                "medications": medications,
                "symptoms": symptoms,
                "allergies": allergies,
                "timestamp": datetime.now().isoformat(),
                "extraction_confidence": self._calculate_confidence(
                    vitals, medications, symptoms, allergies
                )
            }
            
            self.log_action("extraction_complete", f"vitals={bool(vitals)}, meds={len(medications)}")
            
            return result
        
        except Exception as e:
            logger.error(f"Error in HealthDataCollectorAgent: {e}")
            self.log_action("extraction_error", str(e))
            raise
    
    def _extract_vitals(self, text: str) -> Optional[Dict]:
        """Extract vital signs from text."""
        vitals = {}
        text_lower = text.lower()
        
        # Heart rate
        if match := re.search(self.vital_patterns['heart_rate'], text_lower):
            vitals['heart_rate'] = int(match.group(1))
        
        # Blood pressure
        bp_sys_match = re.search(self.vital_patterns['bp_systolic'], text_lower)
        bp_dia_match = re.search(self.vital_patterns['bp_diastolic'], text_lower)
        if bp_sys_match and bp_dia_match:
            vitals['bp_systolic'] = int(bp_sys_match.group(1))
            vitals['bp_diastolic'] = int(bp_dia_match.group(1))
        
        # Temperature
        if match := re.search(self.vital_patterns['temperature'], text_lower):
            vitals['temperature'] = float(match.group(1))
        
        # Respiratory rate
        if match := re.search(self.vital_patterns['respiratory_rate'], text_lower):
            vitals['respiratory_rate'] = int(match.group(1))
        
        # O2 saturation
        if match := re.search(self.vital_patterns['o2_saturation'], text_lower):
            vitals['o2_saturation'] = int(match.group(1))
        
        return vitals if vitals else None
    
    def _extract_medications(self, text: str) -> List[Dict]:
        """Extract medication information."""
        medications = []
        
        # Simple pattern-based extraction
        matches = re.finditer(self.medication_patterns, text, re.IGNORECASE)
        for match in matches:
            med_text = match.group(1).strip()
            
            # Parse medication details if present
            med_dict = {
                "medication_id": f"MED_{hash(med_text) % 10000}",
                "name": med_text,
                "dosage": self._extract_dosage(med_text),
                "frequency": self._extract_frequency(med_text),
                "is_active": True
            }
            
            medications.append(med_dict)
        
        return medications
    
    def _extract_dosage(self, med_text: str) -> Optional[str]:
        """Extract dosage from medication text."""
        patterns = [
            r'(\d+\s*(?:mg|ml|units|tabs?))',
            r'(\d+\s*-\s*\d+\s*(?:mg|ml))',
        ]
        
        for pattern in patterns:
            if match := re.search(pattern, med_text, re.IGNORECASE):
                return match.group(1)
        
        return None
    
    def _extract_frequency(self, med_text: str) -> Optional[str]:
        """Extract medication frequency."""
        freq_keywords = {
            r'(?:once|1x)\s+(?:daily|per day)': MedicationFrequency.ONCE_DAILY,
            r'(?:twice|2x)\s+(?:daily|per day)': MedicationFrequency.TWICE_DAILY,
            r'(?:three|thrice|3x)\s+(?:daily|per day)': MedicationFrequency.THREE_TIMES_DAILY,
            r'(?:every\s+)?4\s+hours': MedicationFrequency.EVERY_4_HOURS,
            r'(?:every\s+)?6\s+hours': MedicationFrequency.EVERY_6_HOURS,
            r'(?:every\s+)?8\s+hours': MedicationFrequency.EVERY_8_HOURS,
            r'(?:as\s+needed|prn)': MedicationFrequency.AS_NEEDED,
        }
        
        med_lower = med_text.lower()
        for pattern, freq in freq_keywords.items():
            if re.search(pattern, med_lower):
                return freq
        
        return None
    
    def _extract_symptoms(self, text: str) -> List[str]:
        """Extract symptoms from text."""
        symptoms = []
        text_lower = text.lower()
        
        for symptom in self.symptom_keywords:
            if symptom in text_lower:
                symptoms.append(symptom)
        
        return symptoms
    
    def _extract_allergies(self, text: str) -> List[Dict]:
        """Extract allergy information."""
        allergies = []
        
        # Look for allergy mentions
        allergy_pattern = r'(?:allerg(?:y|ies)|allergic\s+to)\s+([^,.\n]+)'
        
        for match in re.finditer(allergy_pattern, text, re.IGNORECASE):
            allergen = match.group(1).strip()
            
            # Determine severity if mentioned
            severity = AllergyReactionSeverity.MODERATE
            if any(word in text.lower() for word in ['severe', 'anaphylaxis']):
                severity = AllergyReactionSeverity.SEVERE
            elif any(word in text.lower() for word in ['mild', 'minor']):
                severity = AllergyReactionSeverity.MILD
            
            allergy_dict = {
                "allergen": allergen,
                "reaction_type": "Not specified",
                "severity": severity,
                "onset_date": datetime.now().isoformat()
            }
            
            allergies.append(allergy_dict)
        
        return allergies
    
    def _calculate_confidence(
        self,
        vitals: Optional[Dict],
        medications: List[Dict],
        symptoms: List[str],
        allergies: List[Dict]
    ) -> float:
        """Calculate extraction confidence score."""
        extracted_count = sum([
            1 if vitals else 0,
            len(medications),
            len(symptoms),
            len(allergies)
        ])
        
        # Confidence based on amount of extracted data
        return min(0.95, max(0.5, extracted_count * 0.2))


# ============================================================================
# HEALTH DATA VALIDATOR AGENT
# ============================================================================


class HealthValidatorAgent(BaseAgent):
    """
    Validates health data against medical standards and flags concerns.
    Checks vital sign ranges and identifies potentially dangerous values.
    """
    
    def __init__(self):
        """Initialize health validator agent."""
        super().__init__(
            agent_type="HealthValidator",
            description="Validates health data and flags concerning values"
        )
        
        # Define normal ranges (from VitalSigns model validation)
        self.vital_ranges = {
            'heart_rate': (40, 200),           # BPM
            'blood_pressure_systolic': (60, 220),          # mmHg
            'blood_pressure_diastolic': (40, 130),         # mmHg
            'temperature': (95.0, 106.0),      # Fahrenheit
            'respiratory_rate': (8, 60),       # breaths per minute
            'oxygen_saturation': (70, 100),        # percentage
        }
        
        # Red flags
        self.critical_thresholds = {
            'heart_rate': (40, 180),           # Critical if outside
            'blood_pressure_systolic': (50, 230),          # Critical if outside
            'temperature': (94.0, 107.0),      # Critical if outside
            'oxygen_saturation': (75, 100),        # Critical if below 75%
        }
    
    async def execute(self, health_data: Dict) -> Dict:
        """
        Validate health data and flag concerns.
        
        Args:
            health_data: Extracted health data dictionary
            
        Returns:
            Validation result with flags and recommendations
        """
        try:
            self.log_action("validate_health_data")
            
            validation_result = {
                "is_valid": True,
                "flags": [],
                "concerns": [],
                "recommendations": [],
                "critical_alerts": [],
                "timestamp": datetime.now().isoformat()
            }
            
            # Validate vitals
            if health_data.get('vitals'):
                vital_validation = self._validate_vitals(health_data['vitals'])
                validation_result.update(vital_validation)
            
            # Validate medications
            if health_data.get('medications'):
                med_validation = self._validate_medications(health_data['medications'])
                validation_result['flags'].extend(med_validation.get('flags', []))
            
            # Validate symptoms
            if health_data.get('symptoms'):
                symptom_validation = self._validate_symptoms(health_data['symptoms'])
                validation_result['concerns'].extend(
                    symptom_validation.get('concerns', [])
                )
            
            # Overall determination
            validation_result['is_valid'] = len(validation_result['critical_alerts']) == 0
            
            self.log_action(
                "validation_complete",
                f"valid={validation_result['is_valid']}, "
                f"alerts={len(validation_result['critical_alerts'])}"
            )
            
            return validation_result
        
        except Exception as e:
            logger.error(f"Error in HealthValidatorAgent: {e}")
            self.log_action("validation_error", str(e))
            raise
    
    def _validate_vitals(self, vitals: Dict) -> Dict:
        """Validate vital signs against normal ranges."""
        result = {
            "flags": [],
            "concerns": [],
            "critical_alerts": [],
            "recommendations": []
        }
        
        for vital_name, vital_value in vitals.items():
            if vital_name not in self.vital_ranges:
                continue
            
            normal_min, normal_max = self.vital_ranges[vital_name]
            critical_min, critical_max = self.critical_thresholds.get(
                vital_name, (normal_min, normal_max)
            )
            
            # Check critical range first
            if vital_value < critical_min or vital_value > critical_max:
                alert = f"{vital_name}: {vital_value} is CRITICAL (normal: {normal_min}-{normal_max})"
                result['critical_alerts'].append(alert)
                result['recommendations'].append(
                    f"URGENT: Seek immediate medical attention for {vital_name}"
                )
            
            # Check normal range
            elif vital_value < normal_min or vital_value > normal_max:
                flag = f"{vital_name}: {vital_value} is outside normal range ({normal_min}-{normal_max})"
                result['flags'].append(flag)
                result['recommendations'].append(
                    f"Monitor {vital_name} closely"
                )
        
        return result
    
    def _validate_medications(self, medications: List[Dict]) -> Dict:
        """Validate medication data."""
        result = {"flags": []}
        
        for med in medications:
            # Check for missing critical fields
            if not med.get('frequency'):
                result['flags'].append(f"Medication '{med.get('name')}' missing frequency")
            
            if not med.get('dosage'):
                result['flags'].append(f"Medication '{med.get('name')}' missing dosage")
        
        return result
    
    def _validate_symptoms(self, symptoms: List[str]) -> Dict:
        """Validate symptoms and identify concerning combinations."""
        result = {"concerns": []}
        
        # Define concerning symptom combinations
        concerning_combos = [
            (['chest pain', 'shortness of breath'], "Possible cardiac event"),
            (['high fever', 'severe headache'], "Possible meningitis"),
            (['fever', 'fatigue', 'cough'], "Possible respiratory infection"),
        ]
        
        symptoms_lower = [s.lower() for s in symptoms]
        
        for combo, concern in concerning_combos:
            if all(any(keyword in symptom for keyword in combo) for symptom in symptoms_lower):
                result['concerns'].append(concern)
        
        return result


# ============================================================================
# HEALTH ORCHESTRATION AGENT
# ============================================================================


class HealthOrchestrationAgent(BaseAgent):
    """
    Orchestrates the complete health data workflow.
    Chains collector → validator → storage.
    """
    
    def __init__(self):
        """Initialize health orchestration agent."""
        super().__init__(
            agent_type="HealthOrchestrator",
            description="Orchestrates health data collection, validation, and storage"
        )
        self.collector = HealthDataCollectorAgent()
        self.validator = HealthValidatorAgent()
        self.health_service = get_health_service()
    
    async def execute(
        self,
        user_input: str,
        patient_id: str,
        user_id: str
    ) -> Dict:
        """
        Complete health data workflow.
        
        Args:
            user_input: Raw user input
            patient_id: Patient ID
            user_id: User ID performing action
            
        Returns:
            Complete workflow result
        """
        try:
            self.log_action("orchestration_start", f"patient={patient_id}")
            
            # Step 1: Collect data
            collected = await self.collector.execute(user_input, patient_id)
            
            # Step 2: Validate data
            validated = await self.validator.execute(collected)
            
            # Step 3: Store if valid (and no critical alerts)
            storage_result = None
            if validated.get('is_valid') or not validated.get('critical_alerts'):
                try:
                    health_record = self._build_health_record(
                        patient_id, collected, validated
                    )
                    success = self.health_service.create_health_record(health_record, user_id)
                    storage_result = {
                        "stored": success,
                        "patient_id": patient_id
                    }
                except Exception as e:
                    logger.error(f"Storage error: {e}")
                    storage_result = {"stored": False, "error": str(e)}
            
            result = {
                "workflow_complete": True,
                "collected": collected,
                "validated": validated,
                "stored": storage_result,
                "timestamp": datetime.now().isoformat()
            }
            
            self.log_action("orchestration_complete", f"stored={bool(storage_result)}")
            
            return result
        
        except Exception as e:
            logger.error(f"Error in HealthOrchestrationAgent: {e}")
            self.log_action("orchestration_error", str(e))
            raise
    
    def _build_health_record(
        self,
        patient_id: str,
        collected: Dict,
        validated: Dict
    ) -> HealthRecord:
        """Build HealthRecord from collected and validated data."""
        
        # Build vitals if present
        vitals = None
        if collected.get('vitals'):
            vitals = VitalSigns(**collected['vitals'])
        
        # Build medications
        medications = []
        for med_data in collected.get('medications', []):
            med = MedicationRecord(**med_data)
            medications.append(med)
        
        # Build allergies
        allergies = []
        for allergy_data in collected.get('allergies', []):
            allergy = Allergy(**allergy_data)
            allergies.append(allergy)
        
        # Create HealthRecord
        return HealthRecord(
            patient_id=patient_id,
            vitals=vitals,
            active_medications=medications,
            allergies=allergies,
            chronic_conditions=[],
            data_classification="CONFIDENTIAL_MEDICAL",
            hipaa_consent=True
        )
