"""Deterministic drug-class / synonym lookup (RxNorm/ATC subset)."""

from __future__ import annotations

# Minimal committed subset for KEY-NOTE / NSCLC fixtures — not LLM recall.
ANTI_PD1_TERMS = frozenset(
    {
        "anti-pd-1",
        "anti-pd1",
        "anti-pd-l1",
        "anti-pdl1",
        "pd-1",
        "pd1",
        "pd-l1",
        "pdl1",
        "pembrolizumab",
        "nivolumab",
        "atezolizumab",
        "durvalumab",
        "avelumab",
        "cemiplimab",
        "envafolimab",
        "programmed cell death-1",
        "programmed death-1",
        "immuno-regulatory",
        "immunoregulatory",
    }
)


def normalize_drug_term(text: str) -> str:
    return " ".join(text.lower().replace("-", " ").split())


def is_anti_pd1_mention(text: str) -> bool:
    lowered = text.lower()
    for term in ANTI_PD1_TERMS:
        if term in lowered:
            return True
    return False


def medication_matches_class(description: str, drug_class: str) -> bool:
    if drug_class == "anti_pd1":
        return is_anti_pd1_mention(description)
    return False
