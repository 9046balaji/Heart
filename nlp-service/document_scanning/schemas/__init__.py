"""
Document Scanning Schemas Package.

Pydantic models for structured medical document extraction.
"""

from .lab_report import LabReportSchema, TestResult
from .prescription import PrescriptionSchema, Medication
from .medical_bill import MedicalBillSchema, BillLineItem
from .discharge_summary import DischargeSummarySchema

__all__ = [
    'LabReportSchema',
    'TestResult',
    'PrescriptionSchema',
    'Medication',
    'MedicalBillSchema',
    'BillLineItem',
    'DischargeSummarySchema',
]
