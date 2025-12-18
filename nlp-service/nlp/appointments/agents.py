"""
Appointment booking and validation agents.

Phase 3: Appointment Agents
Updated: Robust date parsing with dateparser library
"""

import re
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

# Optional dateparser for robust NLU date parsing
try:
    import dateparser
    DATEPARSER_AVAILABLE = True
except ImportError:
    DATEPARSER_AVAILABLE = False
    dateparser = None

from agents.base import BaseAgent
from appointments.models import (
    AppointmentType, Appointment, AppointmentCreateRequest, Provider, TimeSlot
)
from appointments.service import get_appointment_service

logger = logging.getLogger(__name__)

if not DATEPARSER_AVAILABLE:
    logger.warning(
        "dateparser library not available. Install with: pip install dateparser"
    )


# ============================================================================
# APPOINTMENT PARSER AGENT
# ============================================================================


class AppointmentParserAgent(BaseAgent):
    """
    Parses user input to extract appointment details.
    Converts natural language to structured appointment request.
    """
    
    def __init__(self):
        """Initialize appointment parser agent."""
        super().__init__(
            name="AppointmentParser",
            description="Parses user input to extract appointment details"
        )
        
        # Define appointment type keywords
        self.appointment_type_keywords = {
            'consultation': ['consultation', 'consult', 'visit', 'appointment'],
            'follow_up': ['follow', 'follow-up', 'follow up'],
            'procedure': ['procedure', 'surgery', 'surgical'],
            'laboratory': ['lab', 'blood', 'lab work', 'testing'],
            'imaging': ['imaging', 'xray', 'x-ray', 'ultrasound', 'mri', 'ct scan'],
            'vaccination': ['vaccine', 'vaccination', 'immunization', 'shot'],
            'routine': ['routine', 'checkup', 'physical', 'annual'],
            'urgent': ['urgent', 'emergency', 'asap', 'right away']
        }
        
        # Time patterns
        self.date_patterns = [
            r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})',  # MM/DD/YYYY or DD/MM/YYYY
            r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s+(\d{4}))?',
            r'(next|this)\s+(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)',
            r'(today|tomorrow|next week|next month)'
        ]
        
        self.time_patterns = [
            r'(\d{1,2}):(\d{2})\s*(am|pm|AM|PM)',
            r'(\d{1,2})\s*(am|pm|AM|PM)',
            r'(morning|afternoon|evening|night)'
        ]
    
    def execute(self, user_input: str, patient_id: str) -> Dict:
        """
        Parse user input to extract appointment details.
        
        Args:
            user_input: User's natural language input
            patient_id: Patient ID
            
        Returns:
            Dictionary with extracted appointment details
        """
        try:
            self.log_action("parse_appointment_input", f"patient={patient_id}")
            
            result = {
                "patient_id": patient_id,
                "appointment_type": self._extract_appointment_type(user_input),
                "requested_datetime": self._extract_datetime(user_input),
                "reason_for_visit": self._extract_reason(user_input),
                "specialty": self._extract_specialty(user_input),
                "is_telehealth": self._extract_telehealth_preference(user_input),
                "urgency_level": self._extract_urgency(user_input),
                "extraction_confidence": 0.0,
                "timestamp": datetime.now().isoformat()
            }
            
            result["extraction_confidence"] = self._calculate_confidence(result)
            
            self.log_action(
                "parsing_complete",
                f"type={result.get('appointment_type')}, confidence={result['extraction_confidence']:.2f}"
            )
            
            return result
        
        except Exception as e:
            logger.error(f"Error in AppointmentParserAgent: {e}")
            self.log_action("parsing_error", str(e))
            raise
    
    def _extract_appointment_type(self, text: str) -> Optional[str]:
        """Extract appointment type from text."""
        text_lower = text.lower()
        
        for app_type, keywords in self.appointment_type_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return app_type
        
        return "consultation"  # Default
    
    def _extract_datetime(self, text: str) -> Optional[str]:
        """
        Extract requested appointment datetime using NLU parsing.
        
        Uses dateparser library for robust natural language date understanding:
        - "tomorrow at 3pm"
        - "next Tuesday morning"
        - "in 2 weeks at 10:30"
        - "March 15th at 2pm"
        - "3 days from now afternoon"
        
        Falls back to regex patterns if dateparser is not available.
        """
        # Try dateparser first (if available) for robust NLU parsing
        if DATEPARSER_AVAILABLE:
            return self._parse_datetime_with_dateparser(text)
        
        # Fallback to regex patterns
        return self._parse_datetime_with_regex(text)
    
    def _parse_datetime_with_dateparser(self, text: str) -> Optional[str]:
        """Parse datetime using dateparser library (NLU approach)."""
        try:
            # Configure dateparser settings
            settings = {
                'PREFER_DATES_FROM': 'future',  # Appointments are usually in future
                'RELATIVE_BASE': datetime.now(),
                'RETURN_AS_TIMEZONE_AWARE': False,
                'PREFER_DAY_OF_MONTH': 'first',
            }
            
            # Common patterns to look for datetime expressions
            datetime_phrases = [
                # Try to find explicit datetime mentions
                r'(?:on|for|at|by|this|next)\s+[\w\s,]+(?:\d{1,2}(?::\d{2})?\s*(?:am|pm)?)?',
                # Try direct date/time
                text,
            ]
            
            # Process time modifiers
            time_modifiers = {
                'morning': '09:00',
                'noon': '12:00',
                'afternoon': '14:00',
                'evening': '17:00',
                'night': '19:00',
            }
            
            # Check for time modifiers in text
            time_override = None
            text_lower = text.lower()
            for modifier, default_time in time_modifiers.items():
                if modifier in text_lower:
                    time_override = default_time
                    break
            
            # Try parsing the full text first
            parsed = dateparser.parse(text, settings=settings)
            
            if parsed:
                # If no time was parsed and we have a modifier, apply it
                if parsed.hour == 0 and parsed.minute == 0 and time_override:
                    hours, minutes = map(int, time_override.split(':'))
                    parsed = parsed.replace(hour=hours, minute=minutes)
                
                # Don't allow past dates for appointments
                if parsed < datetime.now():
                    # Try to interpret as future
                    parsed = dateparser.parse(text, settings={
                        **settings,
                        'PREFER_DATES_FROM': 'future',
                    })
                
                if parsed and parsed > datetime.now():
                    return parsed.isoformat()
            
            # Try extracting date phrases with regex then parsing
            for pattern in self.date_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    phrase = match.group(0)
                    parsed = dateparser.parse(phrase, settings=settings)
                    if parsed and parsed > datetime.now():
                        if time_override:
                            hours, minutes = map(int, time_override.split(':'))
                            parsed = parsed.replace(hour=hours, minute=minutes)
                        return parsed.isoformat()
            
            return None
            
        except Exception as e:
            logger.debug(f"dateparser failed: {e}, falling back to regex")
            return self._parse_datetime_with_regex(text)
    
    def _parse_datetime_with_regex(self, text: str) -> Optional[str]:
        """Parse datetime using regex patterns (fallback approach)."""
        # Simplified extraction - basic regex patterns
        patterns = [
            r'(?:on|for|at)\s+(\d{1,2})[/-](\d{1,2})[/-](\d{4})\s+(?:at|@)?\s*(\d{1,2}):(\d{2})',
            r'(?:next\s+)?(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+(?:at|@)?\s*(\d{1,2}):(\d{2})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)
        
        return None
    
    def _extract_reason(self, text: str) -> Optional[str]:
        """Extract reason for visit."""
        # Look for "reason", "complaint", "issue", etc.
        patterns = [
            r'(?:reason|chief complaint|complain(?:ing)?|issue|problem)\s*(?:is|:|—)\s*([^.,]+)',
            r'(?:for|about)\s+([a-z\s]+(?:pain|ache|concern|issue|problem))',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # Default fallback
        if any(word in text.lower() for word in ['checkup', 'physical', 'exam']):
            return "Routine checkup"
        
        return "General consultation"
    
    def _extract_specialty(self, text: str) -> Optional[str]:
        """Extract medical specialty if mentioned."""
        specialties = {
            'cardiology': ['heart', 'cardiac', 'cardiologist'],
            'orthopedics': ['bone', 'joint', 'orthopedic', 'back pain'],
            'neurology': ['neurology', 'neurologist', 'brain', 'nerve'],
            'pediatrics': ['pediatric', 'pediatrician', 'children', 'kids'],
            'dermatology': ['skin', 'dermatology', 'dermatologist'],
            'psychiatry': ['mental health', 'psychiatry', 'psychiatrist'],
        }
        
        text_lower = text.lower()
        for specialty, keywords in specialties.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return specialty
        
        return None
    
    def _extract_telehealth_preference(self, text: str) -> bool:
        """Extract telehealth preference."""
        telehealth_keywords = ['telehealth', 'virtual', 'video', 'call', 'online', 'from home']
        in_person_keywords = ['in person', 'office', 'visit', 'clinic']
        
        text_lower = text.lower()
        
        for keyword in telehealth_keywords:
            if keyword in text_lower:
                return True
        
        for keyword in in_person_keywords:
            if keyword in text_lower:
                return False
        
        return False  # Default to in-person
    
    def _extract_urgency(self, text: str) -> str:
        """Extract urgency level."""
        urgent_keywords = ['urgent', 'emergency', 'asap', 'right away', 'immediately']
        soon_keywords = ['soon', 'quickly', 'next few days']
        routine_keywords = ['whenever', 'no rush', 'whenever possible']
        
        text_lower = text.lower()
        
        for keyword in urgent_keywords:
            if keyword in text_lower:
                return "urgent"
        
        for keyword in soon_keywords:
            if keyword in text_lower:
                return "soon"
        
        for keyword in routine_keywords:
            if keyword in text_lower:
                return "routine"
        
        return "routine"
    
    def _calculate_confidence(self, result: Dict) -> float:
        """Calculate extraction confidence."""
        confidence = 0.7  # Base confidence
        
        if result.get("requested_datetime"):
            confidence += 0.15
        if result.get("reason_for_visit") and len(result["reason_for_visit"]) > 5:
            confidence += 0.1
        if result.get("specialty"):
            confidence += 0.05
        
        return min(0.99, confidence)


# ============================================================================
# APPOINTMENT VALIDATOR AGENT
# ============================================================================


class AppointmentValidatorAgent(BaseAgent):
    """
    Validates appointment requests against availability and business rules.
    Checks for conflicts, provider availability, and data completeness.
    """
    
    def __init__(self):
        """Initialize appointment validator agent."""
        super().__init__(
            name="AppointmentValidator",
            description="Validates appointment requests and checks availability"
        )
    
    def execute(self, appointment_data: Dict) -> Dict:
        """
        Validate appointment data and check availability.
        
        Args:
            appointment_data: Parsed appointment data
            
        Returns:
            Validation result with flags and recommendations
        """
        try:
            self.log_action("validate_appointment")
            
            validation_result = {
                "is_valid": True,
                "flags": [],
                "conflicts": [],
                "recommendations": [],
                "missing_fields": [],
                "timestamp": datetime.now().isoformat()
            }
            
            # Check for missing fields
            required_fields = ["patient_id", "appointment_type", "reason_for_visit"]
            for field in required_fields:
                if not appointment_data.get(field):
                    validation_result["missing_fields"].append(field)
            
            if validation_result["missing_fields"]:
                validation_result["is_valid"] = False
            
            # Validate datetime if present
            if appointment_data.get("requested_datetime"):
                datetime_validation = self._validate_datetime(
                    appointment_data["requested_datetime"]
                )
                validation_result["flags"].extend(datetime_validation.get("flags", []))
                validation_result["recommendations"].extend(
                    datetime_validation.get("recommendations", [])
                )
                
                if not datetime_validation.get("is_valid"):
                    validation_result["is_valid"] = False
            
            # Check for business rules
            if appointment_data.get("urgency_level") == "urgent":
                validation_result["recommendations"].append(
                    "Mark as urgent - prioritize for same-day or next-day scheduling"
                )
            
            # Check if appointment type is valid
            valid_types = [t.value for t in AppointmentType]
            if appointment_data.get("appointment_type") not in valid_types:
                validation_result["flags"].append(
                    f"Invalid appointment type: {appointment_data.get('appointment_type')}"
                )
                validation_result["is_valid"] = False
            
            self.log_action(
                "validation_complete",
                f"valid={validation_result['is_valid']}, "
                f"flags={len(validation_result['flags'])}"
            )
            
            return validation_result
        
        except Exception as e:
            logger.error(f"Error in AppointmentValidatorAgent: {e}")
            self.log_action("validation_error", str(e))
            raise
    
    def _validate_datetime(self, datetime_str: str) -> Dict:
        """Validate appointment datetime."""
        result = {
            "is_valid": True,
            "flags": [],
            "recommendations": []
        }
        
        try:
            # Try to parse datetime
            # In production, would be more sophisticated parsing
            if not datetime_str:
                result["flags"].append("No appointment time specified")
                result["recommendations"].append("Request patient to specify preferred date/time")
                result["is_valid"] = False
            else:
                # Check if it's in the future
                # (simplified - real implementation would parse the string properly)
                result["recommendations"].append(
                    "Verify appointment time is at least 24 hours in the future"
                )
        
        except Exception as e:
            result["flags"].append(f"Invalid datetime format: {str(e)}")
            result["is_valid"] = False
        
        return result


# ============================================================================
# APPOINTMENT BOOKING AGENT
# ============================================================================


class AppointmentBookingAgent(BaseAgent):
    """
    Books appointments after validation.
    Handles provider matching, slot allocation, and confirmation.
    """
    
    def __init__(self):
        """Initialize appointment booking agent."""
        super().__init__(
            name="AppointmentBooking",
            description="Books appointments and manages scheduling"
        )
        self.appointment_service = get_appointment_service()
    
    def execute(
        self,
        parsed_data: Dict,
        validated_data: Dict,
        provider_id: str,
        scheduled_datetime: datetime
    ) -> Dict:
        """
        Book appointment.
        
        Args:
            parsed_data: Parsed appointment data
            validated_data: Validation results
            provider_id: Selected provider ID
            scheduled_datetime: Final scheduled datetime
            
        Returns:
            Booking result with confirmation details
        """
        try:
            self.log_action("book_appointment", f"patient={parsed_data.get('patient_id')}")
            
            if not validated_data.get("is_valid"):
                self.log_action("booking_rejected", "Validation failed")
                return {
                    "booked": False,
                    "reason": "Appointment validation failed",
                    "validation_issues": validated_data.get("missing_fields", [])
                }
            
            # Create appointment request
            request = AppointmentCreateRequest(
                patient_id=parsed_data["patient_id"],
                provider_id=provider_id,
                appointment_type=parsed_data.get("appointment_type", "consultation"),
                scheduled_datetime=scheduled_datetime,
                reason_for_visit=parsed_data.get("reason_for_visit", "General consultation"),
                is_telehealth=parsed_data.get("is_telehealth", False),
                relevant_medications=parsed_data.get("relevant_medications", []),
                known_allergies=parsed_data.get("known_allergies", [])
            )
            
            # Attempt booking
            appointment_id = self.appointment_service.create_appointment(
                request,
                user_id=parsed_data["patient_id"]
            )
            
            if appointment_id:
                result = {
                    "booked": True,
                    "appointment_id": appointment_id,
                    "patient_id": parsed_data["patient_id"],
                    "provider_id": provider_id,
                    "scheduled_datetime": scheduled_datetime.isoformat(),
                    "appointment_type": parsed_data.get("appointment_type"),
                    "is_telehealth": parsed_data.get("is_telehealth", False),
                    "confirmation_code": f"APPT-{appointment_id[-8:].upper()}",
                    "timestamp": datetime.now().isoformat()
                }
                
                self.log_action(
                    "booking_confirmed",
                    f"id={appointment_id}, provider={provider_id}"
                )
                
                return result
            else:
                self.log_action("booking_failed", "Service returned None")
                return {
                    "booked": False,
                    "reason": "Unable to book appointment - time slot may be unavailable"
                }
        
        except Exception as e:
            logger.error(f"Error in AppointmentBookingAgent: {e}")
            self.log_action("booking_error", str(e))
            return {
                "booked": False,
                "reason": f"Booking error: {str(e)}"
            }
