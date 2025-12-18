"""
JSON Schema for Medical Bill extraction.

Defines structured data format for medical bills and invoices.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date
from decimal import Decimal
from enum import Enum


class ChargeCategory(str, Enum):
    """Categories of medical charges."""
    CONSULTATION = "consultation"
    ROOM = "room"
    NURSING = "nursing"
    MEDICATION = "medication"
    PHARMACY = "pharmacy"
    LAB = "laboratory"
    IMAGING = "imaging"
    PROCEDURE = "procedure"
    SURGERY = "surgery"
    ANESTHESIA = "anesthesia"
    EQUIPMENT = "equipment"
    SUPPLIES = "supplies"
    MISCELLANEOUS = "miscellaneous"
    OTHER = "other"


class PaymentStatus(str, Enum):
    """Bill payment status."""
    PAID = "paid"
    PARTIAL = "partial"
    PENDING = "pending"
    OVERDUE = "overdue"
    INSURANCE_PENDING = "insurance_pending"


class BillLineItem(BaseModel):
    """Individual charge line item."""
    description: str = Field(..., description="Description of the charge")
    quantity: int = Field(default=1, ge=1, description="Quantity")
    unit_price: float = Field(..., description="Price per unit")
    total_price: float = Field(..., description="Total price for this item")
    category: Optional[ChargeCategory] = Field(None, description="Category of charge")
    date_of_service: Optional[date] = Field(None, description="Date service was provided")
    code: Optional[str] = Field(None, description="Billing/procedure code (CPT, HCPCS)")
    notes: Optional[str] = Field(None, description="Additional notes")
    confidence: float = Field(default=1.0, ge=0, le=1, description="Extraction confidence")
    
    class Config:
        json_schema_extra = {
            "example": {
                "description": "Consultation - General Medicine",
                "quantity": 1,
                "unit_price": 500.00,
                "total_price": 500.00,
                "category": "consultation",
                "date_of_service": "2025-12-10",
                "confidence": 0.95
            }
        }


class InsuranceInfo(BaseModel):
    """Insurance claim information."""
    provider_name: Optional[str] = Field(None, description="Insurance provider name")
    policy_number: Optional[str] = Field(None, description="Policy/Member number")
    group_number: Optional[str] = Field(None, description="Group number")
    claim_number: Optional[str] = Field(None, description="Claim number")
    covered_amount: Optional[float] = Field(None, ge=0, description="Amount covered by insurance")
    copay_amount: Optional[float] = Field(None, ge=0, description="Copay amount")
    deductible: Optional[float] = Field(None, ge=0, description="Deductible amount")
    status: Optional[str] = Field(None, description="Claim status")


class MedicalBillSchema(BaseModel):
    """
    Structured schema for medical bill extraction.
    
    Handles:
    - Hospital/provider information
    - Patient information
    - Itemized charges
    - Insurance details
    - Payment information
    - Tax and discounts
    """
    
    # Hospital/Provider Information
    hospital_name: Optional[str] = Field(None, description="Hospital/Provider name")
    hospital_address: Optional[str] = Field(None, description="Hospital address")
    hospital_phone: Optional[str] = Field(None, description="Hospital phone")
    hospital_gstin: Optional[str] = Field(None, description="GST Identification Number")
    hospital_registration: Optional[str] = Field(None, description="Hospital registration number")
    
    # Bill Details
    bill_number: Optional[str] = Field(None, description="Bill/Invoice number")
    bill_date: Optional[date] = Field(None, description="Bill date")
    due_date: Optional[date] = Field(None, description="Payment due date")
    bill_type: Optional[str] = Field(None, description="Type (interim, final, etc.)")
    
    # Patient Information
    patient_name: Optional[str] = Field(None, description="Patient name")
    patient_id: Optional[str] = Field(None, description="Patient ID/MRN")
    patient_address: Optional[str] = Field(None, description="Patient address")
    patient_phone: Optional[str] = Field(None, description="Patient phone")
    
    # Admission Details
    admission_date: Optional[date] = Field(None, description="Admission date")
    discharge_date: Optional[date] = Field(None, description="Discharge date")
    admission_type: Optional[str] = Field(None, description="IP/OP/Daycare")
    ward_type: Optional[str] = Field(None, description="Ward/Room type")
    room_number: Optional[str] = Field(None, description="Room number")
    
    # Doctor Information
    attending_doctor: Optional[str] = Field(None, description="Attending doctor name")
    department: Optional[str] = Field(None, description="Department")
    
    # Diagnosis
    diagnosis: Optional[str] = Field(None, description="Primary diagnosis")
    procedures_performed: Optional[List[str]] = Field(None, description="Procedures performed")
    
    # Charges
    line_items: List[BillLineItem] = Field(default_factory=list, description="Itemized charges")
    
    # Totals
    subtotal: Optional[float] = Field(None, ge=0, description="Subtotal before tax/discount")
    discount: Optional[float] = Field(None, ge=0, description="Discount amount")
    discount_percent: Optional[float] = Field(None, ge=0, le=100, description="Discount percentage")
    tax_amount: Optional[float] = Field(None, ge=0, description="Tax amount")
    tax_percent: Optional[float] = Field(None, ge=0, description="Tax percentage")
    grand_total: Optional[float] = Field(None, ge=0, description="Grand total")
    
    # Insurance
    insurance: Optional[InsuranceInfo] = Field(None, description="Insurance information")
    
    # Payment
    advance_paid: Optional[float] = Field(None, ge=0, description="Advance payment")
    amount_paid: Optional[float] = Field(None, ge=0, description="Amount already paid")
    balance_due: Optional[float] = Field(None, description="Balance due")
    payment_status: Optional[PaymentStatus] = Field(None, description="Payment status")
    payment_mode: Optional[str] = Field(None, description="Payment mode (cash, card, etc.)")
    payment_reference: Optional[str] = Field(None, description="Payment reference number")
    
    # Currency
    currency: str = Field(default="INR", description="Currency code")
    
    # Metadata
    extraction_confidence: float = Field(default=1.0, ge=0, le=1, description="Overall extraction confidence")
    needs_verification: bool = Field(default=True, description="Whether human verification is needed")
    uncertain_fields: List[str] = Field(default_factory=list, description="Fields needing review")
    
    class Config:
        json_schema_extra = {
            "example": {
                "hospital_name": "City General Hospital",
                "bill_number": "INV-2025-12345",
                "bill_date": "2025-12-15",
                "patient_name": "John Doe",
                "patient_id": "MRN123456",
                "admission_date": "2025-12-10",
                "discharge_date": "2025-12-15",
                "line_items": [
                    {
                        "description": "Room Charges (5 days)",
                        "quantity": 5,
                        "unit_price": 2000.00,
                        "total_price": 10000.00,
                        "category": "room"
                    }
                ],
                "subtotal": 25000.00,
                "discount": 2500.00,
                "tax_amount": 2250.00,
                "grand_total": 24750.00,
                "advance_paid": 10000.00,
                "balance_due": 14750.00,
                "payment_status": "pending",
                "currency": "INR"
            }
        }


def calculate_category_totals(line_items: List[BillLineItem]) -> dict:
    """
    Calculate totals by charge category.
    
    Args:
        line_items: List of bill line items
        
    Returns:
        Dictionary mapping category to total amount
    """
    totals = {}
    for item in line_items:
        category = item.category.value if item.category else "uncategorized"
        totals[category] = totals.get(category, 0) + item.total_price
    return totals
