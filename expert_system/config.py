"""Configuration for expert system rules and thresholds."""

# QTc thresholds (milliseconds)
QTC_CRITICAL_THRESHOLD = 500  # Absolute contraindication
QTC_MODERATE_THRESHOLD = 470  # Dose reduction + monitoring
QTC_MILD_THRESHOLD = 450      # Monitoring recommended
QTC_NORMAL_MALE = 450
QTC_NORMAL_FEMALE = 460

# eGFR thresholds (mL/min/1.73m²)
EGFR_SEVERE_THRESHOLD = 30    # Stage 4-5 CKD
EGFR_MODERATE_THRESHOLD = 60  # Stage 3 CKD
EGFR_MILD_THRESHOLD = 90      # Stage 2 CKD
EGFR_NORMAL = 90

# Risk score weights
RISK_WEIGHT_CRITICAL = 40
RISK_WEIGHT_HIGH = 25
RISK_WEIGHT_MODERATE = 15
RISK_WEIGHT_LOW = 5

# Known drug lists (can be loaded from database in production)
QT_PROLONGING_DRUGS = {
    # Antiarrhythmics
    "amiodarone", "sotalol", "quinidine", "procainamide", "disopyramide", 
    "dofetilide", "ibutilide", "dronedarone",
    
    # Antibiotics
    "azithromycin", "clarithromycin", "erythromycin", "levofloxacin", 
    "moxifloxacin", "ciprofloxacin",
    
    # Antipsychotics
    "haloperidol", "quetiapine", "ziprasidone", "risperidone", "olanzapine",
    
    # Antidepressants
    "citalopram", "escitalopram", "amitriptyline", "nortriptyline",
    
    # Antiemetics
    "ondansetron", "metoclopramide", "domperidone",
    
    # Antifungals
    "fluconazole", "ketoconazole", "itraconazole",
    
    # Others
    "methadone", "chloroquine", "hydroxychloroquine"
}

CYP_INHIBITORS = {
    "ketoconazole", "itraconazole", "clarithromycin", "erythromycin",
    "diltiazem", "verapamil", "amiodarone", "dronedarone",
    "fluoxetine", "paroxetine", "ritonavir", "grapefruit"
}

BETA_BLOCKERS = {
    "metoprolol", "atenolol", "bisoprolol", "carvedilol", "propranolol",
    "labetalol", "nebivolol", "nadolol", "timolol"
}

# Age-related adjustments
ELDERLY_AGE_THRESHOLD = 75
VERY_ELDERLY_AGE_THRESHOLD = 85

# Enable/disable rule categories
ENABLE_QTC_RULES = True
ENABLE_RENAL_RULES = True
ENABLE_INTERACTION_RULES = True
ENABLE_AGE_RULES = True

# Logging configuration
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
