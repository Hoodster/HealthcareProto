# Entry kinds for medical history (§2 ust.3, §2 ust.4)
from typing import Literal


type EntryKindsEnhanced = Literal[
    # Clinical Documentation (§2 ust.3 - dokumentacja wewnętrzna)
    'diagnosis',                    # Rozpoznanie
    'symptom',                      # Objaw
    'episode_af',                   # Epizod migotania przedsionków
    'vital_signs',                  # Parametry życiowe (HR, BP, temp)

    # Risk Assessment
    'risk_score',                   # Skale ryzyka (CHA₂DS₂-VASc, HAS-BLED)

    # Diagnostics (§2 ust.3 pkt 20 - wyniki badań)
    'diagnostic_ecg',               # EKG
    'diagnostic_holter',            # Holter EKG
    'diagnostic_echo',              # Echokardiografia
    'diagnostic_imaging',           # Inne obrazowanie (CT, MRI, RTG)
    'lab_result',                   # Wyniki laboratoryjne
    'lab_inr',                      # INR (częste dla warfaryny)

    # Treatments & Medications
    'prescription',                 # Recepta/zlecenie leku
    'medication_change',            # Zmiana leczenia
    'anticoagulation',              # Leczenie przeciwzakrzepowe

    # Procedures (§2 ust.3 pkt 17,21 - procedury)
    'procedure_cardioversion',      # Kardiowersja
    'procedure_ablation',           # Ablacja
    'operation_protocol',           # Protokół operacyjny

    # Observations & Monitoring
    'observation',                  # Obserwacja pacjenta
    'followup',                     # Wizyta kontrolna

    # External Documentation (§2 ust.4 - dokumentacja zewnętrzna)
    'referral',                     # Skierowanie
    'discharge_summary',            # Karta informacyjna z leczenia

    # Adverse Events
    'adverse_event',                # Zdarzenie niepożądane
    'complication',                 # Powikłanie

    # Patient Education & Lifestyle
    'patient_education',            # Edukacja pacjenta
    'lifestyle',                    # Czynniki ryzyka/styl życia

    # Administrative (§2 ust.5 - wymogi administracyjne)
    'consent',                      # Zgoda
    'external_doc_issued',          # Wpis o wydaniu dok. zewnętrznej

    # General
    'health_history',               # Historia zdrowia
    'note',                         # Notatka ogólna
]

type EntryKinds = Literal['prescription',
               'operation_protocol',
               'observation',
                'diagnosis',
               'health_history',
               'visit']