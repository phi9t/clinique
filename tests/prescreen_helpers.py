"""Shared prescreen test tables."""

TABLES = {
    "patients": [
        {"Id": "P1", "BIRTHDATE": "1963-07-01", "GENDER": "M"},
        {"Id": "P2", "BIRTHDATE": "1990-01-01", "GENDER": "F"},
    ],
    "conditions": [
        {
            "PATIENT": "P1",
            "START": "2025-09-10",
            "CODE": "254637007",
            "DESCRIPTION": "Non-small cell lung cancer",
        },
    ],
    "observations": [
        {
            "PATIENT": "P1",
            "DATE": "2026-02-20T09:00:00Z",
            "CODE": "751-8",
            "DESCRIPTION": "Absolute Neutrophil Count",
            "VALUE": "2.1",
            "UNITS": "10*3/uL",
        },
    ],
    "medications": [
        {"PATIENT": "P1", "START": "2025-10-01", "CODE": "860975", "DESCRIPTION": "metformin"},
    ],
}
