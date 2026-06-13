"""Patient context model for rule evaluation."""

from typing import Optional
from pydantic import BaseModel, Field


class PatientContext(BaseModel):
    """
    Patient clinical context used for drug safety evaluation.

    Attributes:
        patient_id: Optional identifier for the patient
        egfr: Estimated glomerular filtration rate in mL/min/1.73m² (normal: >90)
        medications: List of current medications (generic names)
        conditions: List of medical conditions/comorbidities
        age: Patient age in years
        gender: Patient gender ('M', 'F', or 'Other')
        weight: Patient weight in kg (optional)
    """

    patient_id: Optional[str] = None
    egfr: float = Field(..., ge=0, le=200, description="eGFR in mL/min/1.73m²")
    medications: list[str] = Field(default_factory=list, description="Current medications")
    conditions: list[str] = Field(default_factory=list, description="Medical conditions")
    age: Optional[int] = None
    gender: Optional[str] = None
    weight: Optional[float] = None

    class Config:
        json_schema_extra = {
            "example": {
                "patient_id": "P12345",
                "egfr": 45,
                "medications": ["metoprolol", "lisinopril", "metformin"],
                "conditions": ["hypertension", "diabetes", "chronic kidney disease"],
                "age": 65,
                "gender": "M",
                "weight": 80
            }
        }
