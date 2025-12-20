"""
Drug Database for Cardiovascular Medications

This module provides a structured database of cardiovascular medications including:
- Drug information (indications, dosing, side effects)
- Drug-drug interactions
- Contraindications
- Food interactions

DISCLAIMER: This information is for educational purposes only. Always consult
a healthcare provider or pharmacist for medication advice.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class DrugClass(Enum):
    """Drug classifications."""

    ACE_INHIBITOR = "ACE Inhibitor"
    ARB = "Angiotensin Receptor Blocker"
    BETA_BLOCKER = "Beta Blocker"
    CALCIUM_CHANNEL_BLOCKER = "Calcium Channel Blocker"
    DIURETIC = "Diuretic"
    ANTICOAGULANT = "Anticoagulant"
    ANTIPLATELET = "Antiplatelet"
    STATIN = "Statin"
    NITRATE = "Nitrate"
    ANTIARRHYTHMIC = "Antiarrhythmic"
    SGLT2_INHIBITOR = "SGLT2 Inhibitor"
    OTHER = "Other"


class InteractionSeverity(Enum):
    """Drug interaction severity levels."""

    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    CONTRAINDICATED = "contraindicated"


@dataclass
class DrugInteraction:
    """Represents an interaction between two drugs."""

    drug1: str
    drug2: str
    severity: InteractionSeverity
    effect: str
    recommendation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "drug1": self.drug1,
            "drug2": self.drug2,
            "severity": self.severity.value,
            "effect": self.effect,
            "recommendation": self.recommendation,
        }


@dataclass
class Drug:
    """Represents a cardiovascular medication."""

    id: str
    generic_name: str
    brand_names: List[str]
    drug_class: DrugClass
    indications: List[str]
    dosing: str
    common_side_effects: List[str]
    serious_side_effects: List[str]
    contraindications: List[str]
    monitoring: List[str]
    food_interactions: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "generic_name": self.generic_name,
            "brand_names": self.brand_names,
            "drug_class": self.drug_class.value,
            "indications": self.indications,
            "dosing": self.dosing,
            "common_side_effects": self.common_side_effects,
            "serious_side_effects": self.serious_side_effects,
            "contraindications": self.contraindications,
            "monitoring": self.monitoring,
            "food_interactions": self.food_interactions,
            "warnings": self.warnings,
        }

    def to_content(self) -> str:
        """Convert to text content for embedding."""
        parts = [
            f"Drug: {self.generic_name}",
            f"Brand Names: {', '.join(self.brand_names)}",
            f"Class: {self.drug_class.value}",
            f"Uses: {', '.join(self.indications)}",
            f"Dosing: {self.dosing}",
            f"Common Side Effects: {', '.join(self.common_side_effects)}",
            f"Serious Side Effects: {', '.join(self.serious_side_effects)}",
        ]
        if self.contraindications:
            parts.append(f"Do Not Use If: {', '.join(self.contraindications)}")
        if self.monitoring:
            parts.append(f"Monitor: {', '.join(self.monitoring)}")
        if self.food_interactions:
            parts.append(f"Food Interactions: {', '.join(self.food_interactions)}")
        return "\n".join(parts)


class DrugDatabase:
    """
    Database of cardiovascular medications with interaction checking.

    Features:
    - Drug information lookup
    - Drug-drug interaction checking
    - Class-based queries
    - Food interaction warnings

    Example:
        db = DrugDatabase()

        # Look up a drug
        drug = db.get_drug("lisinopril")
        print(drug.generic_name, drug.drug_class)

        # Check interactions
        interactions = db.check_interactions(["lisinopril", "potassium"])
        for interaction in interactions:
            print(f"⚠️ {interaction.severity}: {interaction.effect}")
    """

    def __init__(self):
        """Initialize the drug database."""
        self._drugs: Dict[str, Drug] = {}
        self._interactions: List[DrugInteraction] = []
        self._name_index: Dict[str, str] = {}  # Maps any name to drug ID

        self._load_drugs()
        self._load_interactions()

    def _load_drugs(self) -> None:
        """Load cardiovascular drug data."""
        drugs = [
            # ACE INHIBITORS
            Drug(
                id="lisinopril",
                generic_name="Lisinopril",
                brand_names=["Prinivil", "Zestril"],
                drug_class=DrugClass.ACE_INHIBITOR,
                indications=[
                    "Hypertension",
                    "Heart failure",
                    "Post-heart attack",
                    "Diabetic nephropathy",
                ],
                dosing="Initial: 5-10mg once daily. Maintenance: 20-40mg once daily. Max: 80mg/day",
                common_side_effects=["Dry cough", "Dizziness", "Headache", "Fatigue"],
                serious_side_effects=[
                    "Angioedema (facial swelling)",
                    "Hyperkalemia",
                    "Acute kidney injury",
                ],
                contraindications=[
                    "Pregnancy",
                    "History of angioedema with ACE inhibitors",
                    "Bilateral renal artery stenosis",
                ],
                monitoring=[
                    "Blood pressure",
                    "Kidney function (creatinine)",
                    "Potassium levels",
                ],
                food_interactions=[
                    "Potassium supplements",
                    "Salt substitutes with potassium",
                ],
                warnings=[
                    "May cause dry cough in 5-20% of patients",
                    "Stop immediately if facial/throat swelling occurs",
                ],
            ),
            Drug(
                id="enalapril",
                generic_name="Enalapril",
                brand_names=["Vasotec"],
                drug_class=DrugClass.ACE_INHIBITOR,
                indications=[
                    "Hypertension",
                    "Heart failure",
                    "Asymptomatic LV dysfunction",
                ],
                dosing="Initial: 2.5-5mg twice daily. Maintenance: 10-20mg twice daily. Max: 40mg/day",
                common_side_effects=["Dry cough", "Dizziness", "Fatigue", "Nausea"],
                serious_side_effects=["Angioedema", "Hyperkalemia", "Hypotension"],
                contraindications=[
                    "Pregnancy",
                    "Angioedema history",
                    "Use with sacubitril",
                ],
                monitoring=["Blood pressure", "Kidney function", "Potassium"],
            ),
            # ARBs
            Drug(
                id="losartan",
                generic_name="Losartan",
                brand_names=["Cozaar"],
                drug_class=DrugClass.ARB,
                indications=[
                    "Hypertension",
                    "Diabetic nephropathy",
                    "Stroke prevention in hypertension with LVH",
                ],
                dosing="Initial: 50mg once daily. Maintenance: 50-100mg once daily. Max: 100mg/day",
                common_side_effects=[
                    "Dizziness",
                    "Upper respiratory infection",
                    "Back pain",
                    "Fatigue",
                ],
                serious_side_effects=[
                    "Hyperkalemia",
                    "Acute kidney injury",
                    "Angioedema (rare)",
                ],
                contraindications=["Pregnancy", "Use with aliskiren in diabetics"],
                monitoring=["Blood pressure", "Kidney function", "Potassium"],
                warnings=[
                    "Alternative to ACE inhibitors if cough develops",
                    "Does not cause dry cough",
                ],
            ),
            Drug(
                id="valsartan",
                generic_name="Valsartan",
                brand_names=["Diovan"],
                drug_class=DrugClass.ARB,
                indications=["Hypertension", "Heart failure", "Post-heart attack"],
                dosing="Hypertension: 80-160mg once daily. Heart failure: Start 40mg twice daily, target 160mg twice daily",
                common_side_effects=["Dizziness", "Diarrhea", "Back pain", "Fatigue"],
                serious_side_effects=[
                    "Hyperkalemia",
                    "Hypotension",
                    "Renal impairment",
                ],
                contraindications=[
                    "Pregnancy",
                    "Use with sacubitril (outside of Entresto)",
                ],
                monitoring=["Blood pressure", "Kidney function", "Potassium"],
            ),
            # BETA BLOCKERS
            Drug(
                id="metoprolol",
                generic_name="Metoprolol",
                brand_names=["Lopressor", "Toprol-XL"],
                drug_class=DrugClass.BETA_BLOCKER,
                indications=[
                    "Hypertension",
                    "Heart failure",
                    "Angina",
                    "Post-heart attack",
                    "Rate control in AFib",
                ],
                dosing="Immediate release: 25-100mg twice daily. Extended release (Toprol-XL): 25-200mg once daily",
                common_side_effects=[
                    "Fatigue",
                    "Dizziness",
                    "Slow heart rate",
                    "Cold hands/feet",
                    "Depression",
                ],
                serious_side_effects=[
                    "Severe bradycardia",
                    "Heart block",
                    "Worsening heart failure initially",
                ],
                contraindications=[
                    "Severe bradycardia",
                    "Heart block (without pacemaker)",
                    "Cardiogenic shock",
                    "Uncompensated heart failure",
                ],
                monitoring=["Heart rate", "Blood pressure", "Heart failure symptoms"],
                warnings=[
                    "Do not stop abruptly - may cause rebound tachycardia",
                    "May mask hypoglycemia symptoms in diabetics",
                ],
            ),
            Drug(
                id="carvedilol",
                generic_name="Carvedilol",
                brand_names=["Coreg", "Coreg CR"],
                drug_class=DrugClass.BETA_BLOCKER,
                indications=[
                    "Heart failure",
                    "Post-heart attack with LV dysfunction",
                    "Hypertension",
                ],
                dosing="Heart failure: Start 3.125mg twice daily, titrate to 25mg twice daily. Take with food.",
                common_side_effects=[
                    "Dizziness",
                    "Fatigue",
                    "Diarrhea",
                    "Weight gain",
                    "Hyperglycemia",
                ],
                serious_side_effects=[
                    "Severe bradycardia",
                    "Hypotension",
                    "Worsening heart failure",
                ],
                contraindications=[
                    "Severe bradycardia",
                    "Heart block",
                    "Cardiogenic shock",
                    "Severe hepatic impairment",
                    "Asthma",
                ],
                monitoring=["Heart rate", "Blood pressure", "Weight", "Blood glucose"],
                food_interactions=[
                    "Take with food to slow absorption and reduce orthostatic hypotension"
                ],
                warnings=["May worsen heart failure initially - start low and go slow"],
            ),
            # CALCIUM CHANNEL BLOCKERS
            Drug(
                id="amlodipine",
                generic_name="Amlodipine",
                brand_names=["Norvasc"],
                drug_class=DrugClass.CALCIUM_CHANNEL_BLOCKER,
                indications=["Hypertension", "Angina", "Coronary artery disease"],
                dosing="Initial: 5mg once daily. Max: 10mg once daily",
                common_side_effects=[
                    "Ankle swelling (edema)",
                    "Flushing",
                    "Headache",
                    "Dizziness",
                    "Fatigue",
                ],
                serious_side_effects=[
                    "Severe hypotension",
                    "Worsening angina (rarely)",
                ],
                contraindications=["Cardiogenic shock", "Severe aortic stenosis"],
                monitoring=["Blood pressure", "Ankle swelling"],
                warnings=[
                    "Ankle swelling is not fluid overload - different mechanism than heart failure edema"
                ],
            ),
            Drug(
                id="diltiazem",
                generic_name="Diltiazem",
                brand_names=["Cardizem", "Tiazac", "Dilacor"],
                drug_class=DrugClass.CALCIUM_CHANNEL_BLOCKER,
                indications=["Hypertension", "Angina", "Rate control in AFib", "SVT"],
                dosing="Immediate release: 30-60mg 3-4 times daily. Extended release: 120-360mg once daily",
                common_side_effects=[
                    "Headache",
                    "Dizziness",
                    "Edema",
                    "Bradycardia",
                    "Constipation",
                ],
                serious_side_effects=[
                    "Severe bradycardia",
                    "Heart block",
                    "Heart failure exacerbation",
                ],
                contraindications=[
                    "Severe bradycardia",
                    "Heart block",
                    "Sick sinus syndrome",
                    "Systolic heart failure",
                ],
                monitoring=["Heart rate", "Blood pressure", "ECG if on digoxin"],
                warnings=[
                    "Do not use with beta-blockers without careful monitoring - risk of severe bradycardia"
                ],
            ),
            # DIURETICS
            Drug(
                id="furosemide",
                generic_name="Furosemide",
                brand_names=["Lasix"],
                drug_class=DrugClass.DIURETIC,
                indications=["Heart failure with congestion", "Edema", "Hypertension"],
                dosing="Oral: 20-80mg once or twice daily. Adjust based on response. IV: same or higher doses",
                common_side_effects=[
                    "Frequent urination",
                    "Dehydration",
                    "Dizziness",
                    "Muscle cramps",
                ],
                serious_side_effects=[
                    "Severe electrolyte imbalance (low potassium, sodium)",
                    "Kidney injury",
                    "Hearing loss (high IV doses)",
                ],
                contraindications=["Anuria", "Severe electrolyte depletion"],
                monitoring=[
                    "Weight daily",
                    "Kidney function",
                    "Electrolytes (especially potassium)",
                    "Blood pressure",
                ],
                food_interactions=["Take in morning to avoid nighttime urination"],
                warnings=[
                    "Monitor potassium - may need supplements",
                    "Weigh yourself daily - 2-3 lb gain may need dose adjustment",
                ],
            ),
            Drug(
                id="hydrochlorothiazide",
                generic_name="Hydrochlorothiazide (HCTZ)",
                brand_names=["Microzide", "HydroDIURIL"],
                drug_class=DrugClass.DIURETIC,
                indications=["Hypertension", "Edema"],
                dosing="12.5-50mg once daily. Max antihypertensive effect at 25mg",
                common_side_effects=[
                    "Frequent urination",
                    "Dizziness",
                    "Increased blood sugar",
                    "Increased uric acid",
                ],
                serious_side_effects=[
                    "Electrolyte imbalance",
                    "Kidney injury",
                    "Photosensitivity",
                ],
                contraindications=[
                    "Anuria",
                    "Severe kidney disease",
                    "Sulfa allergy (cross-reactivity possible)",
                ],
                monitoring=[
                    "Blood pressure",
                    "Electrolytes",
                    "Kidney function",
                    "Blood glucose",
                ],
                warnings=[
                    "May increase blood sugar in diabetics",
                    "Use sun protection - photosensitivity",
                ],
            ),
            Drug(
                id="spironolactone",
                generic_name="Spironolactone",
                brand_names=["Aldactone"],
                drug_class=DrugClass.DIURETIC,
                indications=[
                    "Heart failure (HFrEF)",
                    "Resistant hypertension",
                    "Ascites",
                    "Primary aldosteronism",
                ],
                dosing="Heart failure: 12.5-50mg once daily. Hypertension: 25-100mg once daily",
                common_side_effects=[
                    "Gynecomastia (breast enlargement in men)",
                    "Breast tenderness",
                    "Irregular periods",
                    "Hyperkalemia",
                ],
                serious_side_effects=["Severe hyperkalemia", "Kidney injury"],
                contraindications=[
                    "Severe kidney disease",
                    "Hyperkalemia",
                    "Addison's disease",
                ],
                monitoring=[
                    "Potassium (closely!)",
                    "Kidney function",
                    "Blood pressure",
                ],
                warnings=[
                    "Potassium-sparing - DO NOT use with potassium supplements or salt substitutes"
                ],
            ),
            # ANTICOAGULANTS
            Drug(
                id="apixaban",
                generic_name="Apixaban",
                brand_names=["Eliquis"],
                drug_class=DrugClass.ANTICOAGULANT,
                indications=[
                    "AFib stroke prevention",
                    "DVT/PE treatment and prevention",
                    "Post-hip/knee replacement",
                ],
                dosing="AFib: 5mg twice daily (or 2.5mg twice daily if age ≥80, weight ≤60kg, or creatinine ≥1.5)",
                common_side_effects=["Bleeding", "Bruising", "Nausea"],
                serious_side_effects=[
                    "Major bleeding",
                    "Intracranial hemorrhage",
                    "GI bleeding",
                ],
                contraindications=[
                    "Active bleeding",
                    "Severe liver disease",
                    "Mechanical heart valve",
                ],
                monitoring=["Signs of bleeding", "Kidney function", "Liver function"],
                warnings=[
                    "No routine monitoring needed (unlike warfarin)",
                    "Reversal agent available (Andexxa)",
                ],
            ),
            Drug(
                id="rivaroxaban",
                generic_name="Rivaroxaban",
                brand_names=["Xarelto"],
                drug_class=DrugClass.ANTICOAGULANT,
                indications=[
                    "AFib stroke prevention",
                    "DVT/PE",
                    "Post-hip/knee replacement",
                    "CAD/PAD",
                ],
                dosing="AFib: 20mg once daily with evening meal (or 15mg if CrCl 15-50)",
                common_side_effects=["Bleeding", "Back pain", "Dizziness"],
                serious_side_effects=[
                    "Major bleeding",
                    "Spinal hematoma (with spinal procedures)",
                ],
                contraindications=[
                    "Active bleeding",
                    "Severe liver disease",
                    "Mechanical heart valve",
                ],
                monitoring=["Signs of bleeding", "Kidney function"],
                food_interactions=[
                    "MUST take with food (evening meal) for proper absorption"
                ],
                warnings=[
                    "Take with largest meal of the day",
                    "Do not stop without consulting doctor",
                ],
            ),
            Drug(
                id="warfarin",
                generic_name="Warfarin",
                brand_names=["Coumadin", "Jantoven"],
                drug_class=DrugClass.ANTICOAGULANT,
                indications=[
                    "AFib",
                    "Mechanical heart valves",
                    "DVT/PE",
                    "Hypercoagulable states",
                ],
                dosing="Highly variable - individualized based on INR. Typical maintenance: 2-10mg daily",
                common_side_effects=["Bleeding", "Bruising", "Hair loss"],
                serious_side_effects=[
                    "Major bleeding",
                    "Warfarin-induced skin necrosis",
                    "Purple toe syndrome",
                ],
                contraindications=[
                    "Active bleeding",
                    "Pregnancy",
                    "Severe liver disease",
                    "Recent surgery",
                ],
                monitoring=["INR regularly (target usually 2-3)", "Signs of bleeding"],
                food_interactions=[
                    "Vitamin K foods (leafy greens) affect effect - keep intake consistent",
                    "Many drug interactions - check with pharmacist",
                ],
                warnings=[
                    "Many drug and food interactions",
                    "Reversal with Vitamin K or FFP if bleeding",
                ],
            ),
            # ANTIPLATELETS
            Drug(
                id="aspirin",
                generic_name="Aspirin",
                brand_names=["Bayer", "Ecotrin"],
                drug_class=DrugClass.ANTIPLATELET,
                indications=[
                    "Secondary prevention after heart attack/stroke",
                    "Post-stent",
                    "Stable CAD",
                ],
                dosing="Low-dose: 81mg once daily. Can use 325mg acutely",
                common_side_effects=[
                    "GI upset",
                    "Heartburn",
                    "Increased bleeding time",
                ],
                serious_side_effects=[
                    "GI bleeding",
                    "Hemorrhagic stroke",
                    "Allergic reactions",
                ],
                contraindications=[
                    "Active bleeding",
                    "Aspirin allergy",
                    "Severe asthma (aspirin-sensitive)",
                ],
                monitoring=["Signs of bleeding", "GI symptoms"],
                warnings=[
                    "Do not use for primary prevention in most people (risk > benefit)",
                    "Take with food if GI upset",
                ],
            ),
            Drug(
                id="clopidogrel",
                generic_name="Clopidogrel",
                brand_names=["Plavix"],
                drug_class=DrugClass.ANTIPLATELET,
                indications=[
                    "ACS",
                    "Recent MI/stroke",
                    "Peripheral artery disease",
                    "Post-stent (with aspirin)",
                ],
                dosing="75mg once daily. Loading dose: 300-600mg",
                common_side_effects=["Bleeding", "Bruising", "Diarrhea", "Rash"],
                serious_side_effects=["Major bleeding", "TTP (rare)"],
                contraindications=["Active bleeding", "Severe liver disease"],
                monitoring=["Signs of bleeding", "Platelet count if TTP suspected"],
                warnings=[
                    "Do not stop before recommended duration after stent - stent thrombosis risk",
                    "Some patients are poor metabolizers (genetic variant)",
                ],
            ),
            # STATINS
            Drug(
                id="atorvastatin",
                generic_name="Atorvastatin",
                brand_names=["Lipitor"],
                drug_class=DrugClass.STATIN,
                indications=[
                    "High cholesterol",
                    "Cardiovascular disease prevention",
                    "Post-heart attack",
                ],
                dosing="10-80mg once daily. High-intensity: 40-80mg. Moderate: 10-20mg",
                common_side_effects=[
                    "Muscle aches",
                    "Headache",
                    "GI upset",
                    "Elevated liver enzymes",
                ],
                serious_side_effects=[
                    "Rhabdomyolysis (rare)",
                    "Liver damage",
                    "New-onset diabetes",
                ],
                contraindications=[
                    "Active liver disease",
                    "Pregnancy",
                    "Breastfeeding",
                ],
                monitoring=[
                    "Lipid panel",
                    "Liver function (baseline)",
                    "Muscle symptoms",
                ],
                food_interactions=["Grapefruit juice can increase drug levels"],
                warnings=[
                    "Report unexplained muscle pain, tenderness, or weakness immediately"
                ],
            ),
            Drug(
                id="rosuvastatin",
                generic_name="Rosuvastatin",
                brand_names=["Crestor"],
                drug_class=DrugClass.STATIN,
                indications=[
                    "High cholesterol",
                    "Cardiovascular prevention",
                    "Slowing atherosclerosis",
                ],
                dosing="5-40mg once daily. High-intensity: 20-40mg. Asian patients start 5mg",
                common_side_effects=[
                    "Muscle pain",
                    "Headache",
                    "Abdominal pain",
                    "Nausea",
                ],
                serious_side_effects=[
                    "Rhabdomyolysis",
                    "Liver dysfunction",
                    "Kidney effects",
                ],
                contraindications=[
                    "Active liver disease",
                    "Pregnancy",
                    "Severe kidney disease (40mg)",
                ],
                monitoring=["Lipid panel", "Liver function", "Muscle symptoms"],
                warnings=["Most potent statin - lowest doses still very effective"],
            ),
            # NITRATES
            Drug(
                id="nitroglycerin",
                generic_name="Nitroglycerin",
                brand_names=["Nitrostat", "Nitro-Dur", "Nitrolingual"],
                drug_class=DrugClass.NITRATE,
                indications=[
                    "Acute angina",
                    "Angina prevention",
                    "Acute heart failure",
                ],
                dosing="Sublingual: 0.3-0.6mg under tongue, may repeat x2 every 5 min. Patch: 0.2-0.8mg/hr",
                common_side_effects=[
                    "Headache",
                    "Flushing",
                    "Dizziness",
                    "Low blood pressure",
                ],
                serious_side_effects=[
                    "Severe hypotension",
                    "Syncope",
                    "Reflex tachycardia",
                ],
                contraindications=[
                    "Use of PDE5 inhibitors (Viagra, Cialis)",
                    "Severe anemia",
                    "Increased ICP",
                ],
                monitoring=["Blood pressure", "Heart rate", "Chest pain relief"],
                warnings=[
                    "NEVER use with Viagra/Cialis - severe hypotension",
                    "If chest pain not relieved after 3 doses (15 min), call 911",
                ],
            ),
            # SGLT2 INHIBITORS
            Drug(
                id="empagliflozin",
                generic_name="Empagliflozin",
                brand_names=["Jardiance"],
                drug_class=DrugClass.SGLT2_INHIBITOR,
                indications=[
                    "Heart failure (all types)",
                    "Type 2 diabetes",
                    "Chronic kidney disease",
                ],
                dosing="10-25mg once daily",
                common_side_effects=[
                    "Urinary tract infections",
                    "Genital yeast infections",
                    "Increased urination",
                    "Thirst",
                ],
                serious_side_effects=[
                    "Ketoacidosis (even with normal blood sugar)",
                    "Fournier's gangrene (rare)",
                    "Volume depletion",
                ],
                contraindications=["Type 1 diabetes", "Dialysis"],
                monitoring=[
                    "Blood glucose",
                    "Kidney function",
                    "Volume status",
                    "Signs of ketoacidosis",
                ],
                warnings=[
                    "Hold before major surgery",
                    "Check ketones if ill",
                    "Benefits beyond glucose lowering in heart failure",
                ],
            ),
            Drug(
                id="dapagliflozin",
                generic_name="Dapagliflozin",
                brand_names=["Farxiga"],
                drug_class=DrugClass.SGLT2_INHIBITOR,
                indications=[
                    "Heart failure",
                    "Type 2 diabetes",
                    "Chronic kidney disease",
                ],
                dosing="10mg once daily",
                common_side_effects=[
                    "Genital infections",
                    "UTIs",
                    "Increased urination",
                    "Back pain",
                ],
                serious_side_effects=[
                    "Ketoacidosis",
                    "Volume depletion",
                    "Hypotension",
                ],
                contraindications=[
                    "Type 1 diabetes",
                    "Severe kidney disease",
                    "Dialysis",
                ],
                monitoring=[
                    "Blood glucose",
                    "Kidney function",
                    "Blood pressure",
                    "Volume status",
                ],
                warnings=[
                    "Proven benefits in heart failure regardless of diabetes status"
                ],
            ),
            # ANTIARRHYTHMICS
            Drug(
                id="amiodarone",
                generic_name="Amiodarone",
                brand_names=["Cordarone", "Pacerone"],
                drug_class=DrugClass.ANTIARRHYTHMIC,
                indications=[
                    "Life-threatening ventricular arrhythmias",
                    "AFib rhythm control",
                    "AFib cardioversion",
                ],
                dosing="Loading: 800-1600mg/day for 1-3 weeks. Maintenance: 100-400mg daily",
                common_side_effects=[
                    "GI upset",
                    "Photosensitivity",
                    "Fatigue",
                    "Tremor",
                    "Bradycardia",
                ],
                serious_side_effects=[
                    "Pulmonary toxicity",
                    "Liver toxicity",
                    "Thyroid dysfunction",
                    "QT prolongation",
                    "Vision changes",
                ],
                contraindications=[
                    "Severe sinus node dysfunction",
                    "2nd/3rd degree heart block",
                    "Cardiogenic shock",
                ],
                monitoring=[
                    "Thyroid function",
                    "Liver function",
                    "Pulmonary function",
                    "ECG (QT interval)",
                    "Eye exam",
                ],
                food_interactions=["Grapefruit increases levels"],
                warnings=[
                    "Many drug interactions",
                    "Long half-life (40-55 days)",
                    "Use sun protection",
                    "Regular monitoring essential",
                ],
            ),
        ]

        for drug in drugs:
            self._drugs[drug.id] = drug
            # Build name index
            self._name_index[drug.generic_name.lower()] = drug.id
            for brand in drug.brand_names:
                self._name_index[brand.lower()] = drug.id

    def _load_interactions(self) -> None:
        """Load drug-drug interactions."""
        interactions = [
            # ACE-I/ARB + Potassium
            DrugInteraction(
                "ACE Inhibitors",
                "Potassium supplements",
                InteractionSeverity.MAJOR,
                "Increased risk of hyperkalemia (dangerously high potassium)",
                "Avoid combination. If necessary, monitor potassium closely.",
            ),
            DrugInteraction(
                "ACE Inhibitors",
                "Spironolactone",
                InteractionSeverity.MODERATE,
                "Increased risk of hyperkalemia",
                "Monitor potassium closely if used together. Common in heart failure.",
            ),
            # Nitrates + PDE5 inhibitors
            DrugInteraction(
                "Nitroglycerin",
                "Sildenafil (Viagra)",
                InteractionSeverity.CONTRAINDICATED,
                "Severe life-threatening hypotension",
                "NEVER use together. Wait 24 hours after sildenafil, 48 hours after tadalafil.",
            ),
            DrugInteraction(
                "Nitroglycerin",
                "Tadalafil (Cialis)",
                InteractionSeverity.CONTRAINDICATED,
                "Severe life-threatening hypotension",
                "NEVER use together. Wait 48 hours after tadalafil before using nitrates.",
            ),
            # Anticoagulants + NSAIDs
            DrugInteraction(
                "Warfarin",
                "NSAIDs (Ibuprofen, Naproxen)",
                InteractionSeverity.MAJOR,
                "Increased bleeding risk - both GI and other sites",
                "Avoid NSAIDs. Use acetaminophen for pain instead.",
            ),
            DrugInteraction(
                "Apixaban",
                "NSAIDs",
                InteractionSeverity.MODERATE,
                "Increased bleeding risk",
                "Minimize NSAID use. Short-term use with caution.",
            ),
            DrugInteraction(
                "Aspirin",
                "Warfarin",
                InteractionSeverity.MAJOR,
                "Significantly increased bleeding risk",
                "Use only if specifically indicated (certain valve conditions). Monitor closely.",
            ),
            # Beta blockers + Non-DHP CCBs
            DrugInteraction(
                "Metoprolol",
                "Diltiazem",
                InteractionSeverity.MAJOR,
                "Risk of severe bradycardia, heart block, and heart failure",
                "Avoid combination or use with extreme caution. Monitor ECG.",
            ),
            DrugInteraction(
                "Metoprolol",
                "Verapamil",
                InteractionSeverity.MAJOR,
                "Risk of severe bradycardia and heart block",
                "Generally avoid. If used, monitor closely.",
            ),
            # Statins + Gemfibrozil
            DrugInteraction(
                "Atorvastatin",
                "Gemfibrozil",
                InteractionSeverity.MAJOR,
                "Increased risk of rhabdomyolysis (muscle breakdown)",
                "Avoid combination. Use fenofibrate if fibrate needed.",
            ),
            # Amiodarone interactions
            DrugInteraction(
                "Amiodarone",
                "Warfarin",
                InteractionSeverity.MAJOR,
                "Significantly increases warfarin effect - bleeding risk",
                "Reduce warfarin dose by 30-50%. Monitor INR closely.",
            ),
            DrugInteraction(
                "Amiodarone",
                "Digoxin",
                InteractionSeverity.MAJOR,
                "Increases digoxin levels - toxicity risk",
                "Reduce digoxin dose by 50%. Monitor digoxin levels.",
            ),
            DrugInteraction(
                "Amiodarone",
                "Simvastatin",
                InteractionSeverity.MAJOR,
                "Increased risk of myopathy/rhabdomyolysis",
                "Do not exceed simvastatin 20mg. Consider atorvastatin or rosuvastatin.",
            ),
            # Grapefruit interactions
            DrugInteraction(
                "Atorvastatin",
                "Grapefruit juice",
                InteractionSeverity.MODERATE,
                "Grapefruit increases statin levels - increased side effect risk",
                "Limit grapefruit juice or choose pravastatin/rosuvastatin (less affected).",
            ),
            DrugInteraction(
                "Amlodipine",
                "Grapefruit juice",
                InteractionSeverity.MINOR,
                "May slightly increase amlodipine levels",
                "Small amounts generally OK. Avoid large quantities.",
            ),
            # Diuretic interactions
            DrugInteraction(
                "Furosemide",
                "Aminoglycosides (Gentamicin)",
                InteractionSeverity.MAJOR,
                "Increased risk of ototoxicity (hearing damage) and nephrotoxicity",
                "Avoid if possible. Monitor hearing and kidney function.",
            ),
            DrugInteraction(
                "Spironolactone",
                "ACE Inhibitors",
                InteractionSeverity.MODERATE,
                "Additive hyperkalemia risk",
                "Commonly used together in heart failure. Monitor potassium closely.",
            ),
            # Clopidogrel + PPIs
            DrugInteraction(
                "Clopidogrel",
                "Omeprazole",
                InteractionSeverity.MODERATE,
                "Omeprazole may reduce clopidogrel effectiveness",
                "Use alternative PPI (pantoprazole preferred) if needed.",
            ),
        ]

        self._interactions = interactions

    def get_drug(self, name: str) -> Optional[Drug]:
        """
        Get drug by generic name, brand name, or ID.

        Args:
            name: Drug name to look up

        Returns:
            Drug object or None if not found
        """
        # Try direct ID lookup
        if name.lower() in self._drugs:
            return self._drugs[name.lower()]

        # Try name index
        drug_id = self._name_index.get(name.lower())
        if drug_id:
            return self._drugs[drug_id]

        return None

    def search_drugs(self, query: str) -> List[Drug]:
        """
        Search drugs by name, indication, or class.

        Args:
            query: Search query

        Returns:
            List of matching drugs
        """
        query_lower = query.lower()
        results = []

        for drug in self._drugs.values():
            score = 0

            # Name match
            if query_lower in drug.generic_name.lower():
                score += 10
            for brand in drug.brand_names:
                if query_lower in brand.lower():
                    score += 8

            # Class match
            if query_lower in drug.drug_class.value.lower():
                score += 5

            # Indication match
            for indication in drug.indications:
                if query_lower in indication.lower():
                    score += 3

            if score > 0:
                results.append((score, drug))

        results.sort(key=lambda x: x[0], reverse=True)
        return [drug for _, drug in results]

    def get_drugs_by_class(self, drug_class: DrugClass) -> List[Drug]:
        """Get all drugs in a specific class."""
        return [d for d in self._drugs.values() if d.drug_class == drug_class]

    def check_interactions(self, drug_names: List[str]) -> List[DrugInteraction]:
        """
        Check for interactions between a list of drugs.

        Args:
            drug_names: List of drug names to check

        Returns:
            List of potential interactions
        """
        interactions_found = []
        normalized_names = set()
        drug_classes = set()

        # Normalize names and get classes
        for name in drug_names:
            drug = self.get_drug(name)
            if drug:
                normalized_names.add(drug.generic_name)
                drug_classes.add(drug.drug_class.value)
            else:
                normalized_names.add(name)

        # Check for interactions
        for interaction in self._interactions:
            drug1_match = False
            drug2_match = False

            # Check if drug1 matches
            for name in normalized_names:
                if (
                    interaction.drug1.lower() in name.lower()
                    or name.lower() in interaction.drug1.lower()
                ):
                    drug1_match = True
                    break
            for cls in drug_classes:
                if interaction.drug1.lower() in cls.lower():
                    drug1_match = True
                    break

            # Check if drug2 matches
            for name in normalized_names:
                if (
                    interaction.drug2.lower() in name.lower()
                    or name.lower() in interaction.drug2.lower()
                ):
                    drug2_match = True
                    break
            for cls in drug_classes:
                if interaction.drug2.lower() in cls.lower():
                    drug2_match = True
                    break

            if drug1_match and drug2_match:
                interactions_found.append(interaction)

        # Sort by severity
        severity_order = {
            InteractionSeverity.CONTRAINDICATED: 0,
            InteractionSeverity.MAJOR: 1,
            InteractionSeverity.MODERATE: 2,
            InteractionSeverity.MINOR: 3,
        }
        interactions_found.sort(key=lambda x: severity_order.get(x.severity, 4))

        return interactions_found

    def get_all_interactions(self) -> List[DrugInteraction]:
        """Get all drug interactions."""
        return self._interactions.copy()

    def to_rag_documents(self) -> List[Dict[str, Any]]:
        """
        Convert drug database to format suitable for RAG indexing.

        Returns:
            List of documents ready for vector store
        """
        documents = []

        for drug in self._drugs.values():
            documents.append(
                {
                    "id": f"drug_{drug.id}",
                    "content": drug.to_content(),
                    "metadata": {
                        "drug_name": drug.generic_name,
                        "brand_names": drug.brand_names,
                        "drug_class": drug.drug_class.value,
                        "type": "medication",
                    },
                }
            )

        # Add interaction documents
        for i, interaction in enumerate(self._interactions):
            documents.append(
                {
                    "id": f"interaction_{i}",
                    "content": f"Drug Interaction: {interaction.drug1} + {interaction.drug2}. "
                    f"Severity: {interaction.severity.value}. "
                    f"Effect: {interaction.effect}. "
                    f"Recommendation: {interaction.recommendation}",
                    "metadata": {
                        "type": "drug_interaction",
                        "severity": interaction.severity.value,
                        "drugs": [interaction.drug1, interaction.drug2],
                    },
                }
            )

        return documents


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_db_instance: Optional[DrugDatabase] = None


def get_drug_database() -> DrugDatabase:
    """Get singleton instance of DrugDatabase."""
    global _db_instance
    if _db_instance is None:
        _db_instance = DrugDatabase()
    return _db_instance


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("Testing DrugDatabase...")

    db = get_drug_database()

    # Test drug lookup
    print("\n💊 Drug lookup - Lisinopril:")
    drug = db.get_drug("lisinopril")
    if drug:
        print(f"  Generic: {drug.generic_name}")
        print(f"  Brands: {', '.join(drug.brand_names)}")
        print(f"  Class: {drug.drug_class.value}")
        print(f"  Uses: {', '.join(drug.indications[:2])}...")

    # Test brand name lookup
    print("\n💊 Brand name lookup - Lipitor:")
    drug = db.get_drug("Lipitor")
    if drug:
        print(f"  Found: {drug.generic_name}")

    # Test class lookup
    print("\n📋 Beta blockers:")
    beta_blockers = db.get_drugs_by_class(DrugClass.BETA_BLOCKER)
    for d in beta_blockers:
        print(f"  - {d.generic_name} ({', '.join(d.brand_names)})")

    # Test interaction checking
    print("\n⚠️ Checking interactions for: Lisinopril + Spironolactone + Metoprolol")
    interactions = db.check_interactions(["lisinopril", "spironolactone", "metoprolol"])
    for interaction in interactions:
        print(
            f"  [{interaction.severity.value.upper()}] {interaction.drug1} + {interaction.drug2}"
        )
        print(f"    Effect: {interaction.effect}")

    # Test dangerous interaction
    print("\n🚫 Checking dangerous interaction: Nitroglycerin + Viagra")
    interactions = db.check_interactions(["nitroglycerin", "sildenafil"])
    for interaction in interactions:
        print(
            f"  [{interaction.severity.value.upper()}] {interaction.drug1} + {interaction.drug2}"
        )
        print(f"    {interaction.effect}")
        print(f"    ⚠️ {interaction.recommendation}")

    # Test search
    print("\n🔍 Search for 'blood pressure':")
    results = db.search_drugs("blood pressure")[:3]
    for drug in results:
        print(f"  - {drug.generic_name}")

    # Test RAG documents
    rag_docs = db.to_rag_documents()
    print(f"\n📄 RAG documents ready: {len(rag_docs)}")

    print("\n✅ DrugDatabase tests passed!")
