"""
Medical-Specific Prompt Templates for Multimodal Processing

These prompts are optimized for:
- Lab result table extraction
- Vital signs parsing
- ECG/EKG image analysis
- Prescription/medication parsing
- Medical chart interpretation

IMPORTANT: All outputs include medical disclaimers.
"""

from typing import Dict, Any

MEDICAL_PROMPTS: Dict[str, Any] = {}

# =============================================================================
# TABLE ANALYSIS PROMPTS
# =============================================================================

MEDICAL_PROMPTS["TABLE_ANALYSIS_SYSTEM"] = (
    "You are an expert medical data analyst. Extract structured information from "
    "medical tables with precision. Always include units and reference ranges when available."
)

MEDICAL_PROMPTS["LAB_RESULTS_TABLE"] = """
Analyze this lab results table and extract structured data.

Return a JSON response with this exact structure:
{{
    "data_type": "lab_results",
    "patient_id": "<if visible, otherwise null>",
    "collection_date": "<date if visible>",
    "results": [
        {{
            "test_name": "<name of the test>",
            "value": "<numeric or text value>",
            "unit": "<unit of measurement>",
            "reference_range": "<normal range if shown>",
            "is_abnormal": <true/false>,
            "flag": "<H/L/C if flagged>"
        }}
    ],
    "panel_name": "<if this is part of a panel, e.g., 'Complete Blood Count'>",
    "clinical_notes": "<any notes or comments visible>"
}}

Table Information:
{table_content}

IMPORTANT: 
- Extract ALL test results visible in the table
- Mark values as abnormal if they fall outside reference ranges
- Include units exactly as shown
- If reference range is not shown, set it to null
"""

MEDICAL_PROMPTS["VITAL_SIGNS_TABLE"] = """
Analyze this vital signs table and extract structured data.

Return a JSON response with this exact structure:
{{
    "data_type": "vital_signs",
    "readings": [
        {{
            "timestamp": "<date/time of reading>",
            "blood_pressure_systolic": <number or null>,
            "blood_pressure_diastolic": <number or null>,
            "heart_rate": <number or null>,
            "respiratory_rate": <number or null>,
            "temperature": <number or null>,
            "temperature_unit": "<F or C>",
            "oxygen_saturation": <number or null>,
            "weight": <number or null>,
            "weight_unit": "<kg or lbs>",
            "height": <number or null>,
            "height_unit": "<cm or in>",
            "bmi": <number or null>,
            "notes": "<any notes>"
        }}
    ],
    "trends": {{
        "bp_trend": "<stable/increasing/decreasing>",
        "hr_trend": "<stable/increasing/decreasing>",
        "concerning_readings": ["<list any abnormal values>"]
    }}
}}

Table Information:
{table_content}

Reference Ranges for Flagging:
- Blood Pressure: Normal <120/80, Elevated 120-129/<80, High ≥130/80
- Heart Rate: Normal 60-100 bpm
- Respiratory Rate: Normal 12-20/min
- SpO2: Normal ≥95%
- Temperature: Normal 97.8-99.1°F (36.5-37.3°C)
"""

MEDICAL_PROMPTS["MEDICATION_TABLE"] = """
Analyze this medication table and extract structured data.

Return a JSON response with this exact structure:
{{
    "data_type": "medications",
    "medications": [
        {{
            "drug_name": "<generic or brand name>",
            "generic_name": "<generic name if different>",
            "dosage": "<amount>",
            "dosage_unit": "<mg, mcg, mL, etc.>",
            "route": "<oral, IV, topical, etc.>",
            "frequency": "<once daily, BID, TID, PRN, etc.>",
            "start_date": "<if shown>",
            "end_date": "<if shown>",
            "prescriber": "<if shown>",
            "indication": "<reason for medication if shown>",
            "special_instructions": "<any special notes>"
        }}
    ],
    "potential_interactions": "<note any obvious interaction concerns>",
    "total_medications": <count>
}}

Table Information:
{table_content}

IMPORTANT: Extract exact dosages and frequencies as written.
"""

# =============================================================================
# IMAGE ANALYSIS PROMPTS
# =============================================================================

MEDICAL_PROMPTS["IMAGE_ANALYSIS_SYSTEM"] = (
    "You are an expert medical image analyst. Provide detailed, accurate descriptions "
    "of medical images. Always include appropriate medical disclaimers."
)

MEDICAL_PROMPTS["ECG_ANALYSIS"] = """
Analyze this ECG/EKG image and provide a structured assessment.

IMPORTANT DISCLAIMER: This analysis is for educational and informational purposes only.
It is NOT a substitute for professional medical interpretation. Always consult a
qualified healthcare provider for ECG interpretation.

Provide a JSON response with this structure:
{{
    "image_type": "ECG",
    "leads_visible": ["<list visible leads, e.g., I, II, III, aVR, aVL, aVF, V1-V6>"],
    "rhythm_analysis": {{
        "rhythm": "<sinus rhythm, atrial fibrillation, etc.>",
        "rate": "<heart rate if calculable, otherwise estimate>",
        "regularity": "<regular/irregular>"
    }},
    "intervals": {{
        "pr_interval": "<normal/prolonged/shortened/not measurable>",
        "qrs_duration": "<normal/wide/not measurable>",
        "qt_interval": "<normal/prolonged/shortened/not measurable>"
    }},
    "findings": [
        "<list any notable findings>"
    ],
    "abnormalities": [
        "<list any potential abnormalities noted>"
    ],
    "clinical_correlation": "<suggested clinical correlation>",
    "confidence_level": "<high/medium/low>",
    "disclaimer": "This is an AI-assisted interpretation for educational purposes only. Professional medical review is required."
}}

Image Information:
- Image Path: {image_path}
- Caption: {caption}

Context from surrounding document:
{context}
"""

MEDICAL_PROMPTS["MEDICAL_CHART_ANALYSIS"] = """
Analyze this medical chart/graph and extract key information.

Provide a JSON response with this structure:
{{
    "chart_type": "<line graph, bar chart, scatter plot, etc.>",
    "title": "<chart title if visible>",
    "x_axis": {{
        "label": "<x-axis label>",
        "unit": "<unit if applicable>",
        "range": "<min to max>"
    }},
    "y_axis": {{
        "label": "<y-axis label>",
        "unit": "<unit if applicable>",
        "range": "<min to max>"
    }},
    "data_series": [
        {{
            "name": "<series name>",
            "key_points": ["<notable data points>"],
            "trend": "<increasing/decreasing/stable/variable>"
        }}
    ],
    "clinical_significance": "<what this chart shows clinically>",
    "key_takeaways": ["<main points from the chart>"]
}}

Image Information:
- Image Path: {image_path}
- Caption: {caption}

Context:
{context}
"""

MEDICAL_PROMPTS["PRESCRIPTION_IMAGE"] = """
Analyze this prescription/medication image and extract information.

IMPORTANT: This is for documentation purposes only. Always verify with the original
prescription and consult a pharmacist.

Provide a JSON response with this structure:
{{
    "document_type": "prescription",
    "prescriber_info": {{
        "name": "<if visible>",
        "credentials": "<MD, DO, NP, etc.>",
        "practice": "<if visible>"
    }},
    "patient_info": {{
        "name": "<if visible - NOTE: Consider PHI implications>",
        "dob": "<if visible>"
    }},
    "date_written": "<prescription date>",
    "medications": [
        {{
            "drug_name": "<medication name>",
            "strength": "<dosage strength>",
            "quantity": "<quantity prescribed>",
            "sig": "<directions>",
            "refills": "<number of refills>"
        }}
    ],
    "legibility_score": "<good/fair/poor>",
    "warnings": ["<any warnings or alerts on the prescription>"]
}}

Image Information:
- Image Path: {image_path}
- Caption: {caption}

NOTE: Extracted patient information should be handled according to HIPAA guidelines.
"""

# =============================================================================
# GENERIC CONTENT PROMPTS
# =============================================================================

MEDICAL_PROMPTS["GENERIC_TABLE"] = """
Analyze this table from a medical document and extract its content.

Provide a JSON response with this structure:
{{
    "table_title": "<title if visible>",
    "table_type": "<data/comparison/reference/unknown>",
    "columns": ["<column headers>"],
    "row_count": <number>,
    "content_summary": "<brief description of table contents>",
    "key_data_points": [
        {{
            "description": "<what this data point represents>",
            "value": "<the value>",
            "significance": "<why it matters>"
        }}
    ],
    "medical_relevance": "<how this table relates to medical care>"
}}

Table Information:
{table_content}
"""

MEDICAL_PROMPTS["GENERIC_IMAGE"] = """
Analyze this image from a medical document.

Provide a JSON response with this structure:
{{
    "image_type": "<photo/diagram/chart/scan/other>",
    "content_description": "<detailed description of what's shown>",
    "medical_context": "<how this relates to medical information>",
    "key_elements": [
        "<list important elements visible>"
    ],
    "text_visible": ["<any text visible in the image>"],
    "quality_assessment": "<clear/acceptable/poor>"
}}

Image Information:
- Image Path: {image_path}
- Caption: {caption}

Context:
{context}
"""

# =============================================================================
# ENTITY EXTRACTION PROMPTS
# =============================================================================

MEDICAL_PROMPTS["EXTRACT_ENTITIES"] = """
From the following medical content, extract key entities and their relationships.

Content:
{content}

Extract and return a JSON with:
{{
    "entities": [
        {{
            "name": "<entity name>",
            "type": "<medication/condition/procedure/lab_test/vital_sign/symptom/provider>",
            "attributes": {{<relevant attributes>}}
        }}
    ],
    "relationships": [
        {{
            "from": "<entity1>",
            "to": "<entity2>",
            "type": "<treats/causes/indicates/monitors/prescribes/etc.>"
        }}
    ]
}}
"""

# =============================================================================
# QUERY ENHANCEMENT PROMPTS
# =============================================================================

MEDICAL_PROMPTS["MULTIMODAL_QUERY"] = """
You are answering a medical question using both text and visual information.

Text Context:
{text_context}

Visual Information:
{visual_context}

User Question: {query}

Provide a comprehensive answer that:
1. Integrates information from both text and visual sources
2. Cites specific data points when available
3. Notes any discrepancies between sources
4. Includes appropriate medical disclaimers
5. Recommends professional consultation when appropriate

Answer:
"""
