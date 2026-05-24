"""Deterministic drug-class / oncology synonym lookup (RxNorm/ATC subset)."""

from __future__ import annotations

import re

MAX_EVIDENCE_QUOTE_LEN = 240

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

NSCLC_TERMS = frozenset(
    {
        "nsclc",
        "non small cell lung cancer",
        "non-small cell lung cancer",
        "nonsmall cell lung cancer",
        "non small cell lung carcinoma",
        "non-small cell lung carcinoma",
        "lung cancer",
        "lung carcinoma",
    }
)

SQUAMOUS_TERMS = frozenset(
    {
        "squamous",
        "squamous cell",
        "predominantly squamous",
    }
)

SYSTEMIC_ONCOLOGY_TERMS = frozenset(
    {
        "chemotherapy",
        "chemo",
        "pembrolizumab",
        "nivolumab",
        "atezolizumab",
        "erlotinib",
        "crizotinib",
        "cetuximab",
        "bevacizumab",
        "carboplatin",
        "cisplatin",
        "pemetrexed",
        "paclitaxel",
        "docetaxel",
        "antineoplastic",
        "immunotherapy",
        "targeted therapy",
        "systemic therapy",
        "systemic treatment",
    }
)

LAB_ANALYTE_TERMS = frozenset({"anc", "neutrophil", "hemoglobin", "platelet"})

_ECOG_RE = re.compile(r"\becog\b|\bperformance status\b", re.I)
_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Criterion token → additional retrieval tokens (query expansion).
_QUERY_EXPANSIONS: dict[str, tuple[str, ...]] = {
    "nsclc": ("non", "small", "cell", "lung", "cancer"),
    "nonsquamous": ("non", "small", "cell", "lung", "cancer"),
    "squamous": ("lung", "cancer", "histology"),
    "egfr": ("epidermal", "growth", "factor", "receptor"),
    "alk": ("anaplastic", "lymphoma", "kinase"),
    "ecog": ("performance", "status"),
}


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def truncate_quote(text: str, *, limit: int = MAX_EVIDENCE_QUOTE_LEN) -> str:
    return text[:limit]


def normalize_clinical_text(text: str) -> str:
    return " ".join(text.lower().replace("-", " ").split())


def _contains_term(text: str, terms: frozenset[str]) -> bool:
    lowered = normalize_clinical_text(text)
    return any(term in lowered for term in terms)


def is_anti_pd1_mention(text: str) -> bool:
    return _contains_term(text, ANTI_PD1_TERMS)


def is_nsclc_mention(text: str) -> bool:
    return _contains_term(text, NSCLC_TERMS)


def is_squamous_mention(text: str) -> bool:
    return _contains_term(text, SQUAMOUS_TERMS)


def is_systemic_oncology_mention(text: str) -> bool:
    return _contains_term(text, SYSTEMIC_ONCOLOGY_TERMS)


def is_prior_systemic_criterion(text: str) -> bool:
    lowered = text.lower()
    return "not received" in lowered and "systemic" in lowered


def is_ecog_criterion(text: str) -> bool:
    return bool(_ECOG_RE.search(text))


def medication_matches_class(description: str, drug_class: str) -> bool:
    if drug_class == "anti_pd1":
        return is_anti_pd1_mention(description)
    if drug_class == "systemic_oncology":
        return is_systemic_oncology_mention(description)
    return False


def expand_query_tokens(tokens: list[str]) -> list[str]:
    expanded = list(tokens)
    seen = set(tokens)
    for token in tokens:
        for extra in _QUERY_EXPANSIONS.get(token, ()):
            if extra not in seen:
                seen.add(extra)
                expanded.append(extra)
    return expanded


def _token_overlap(crit: str, doc: str, *, min_overlap: int) -> bool:
    crit_tokens = set(tokenize(crit))
    doc_tokens = set(tokenize(doc))
    return len(crit_tokens & doc_tokens) >= min_overlap


def condition_matches_criterion(criterion_text: str, doc_text: str) -> bool:
    """True when a condition document is plausibly relevant to the criterion."""
    crit = normalize_clinical_text(criterion_text)
    doc = normalize_clinical_text(doc_text)
    if is_nsclc_mention(crit) and is_nsclc_mention(doc):
        return True
    if is_squamous_mention(crit) and ("lung" in doc or "cancer" in doc or is_squamous_mention(doc)):
        return True
    return _token_overlap(crit, doc, min_overlap=2)


def medication_matches_criterion(criterion_text: str, doc_text: str) -> bool:
    crit = normalize_clinical_text(criterion_text)
    doc = normalize_clinical_text(doc_text)
    if is_anti_pd1_mention(crit) and is_anti_pd1_mention(doc):
        return True
    if is_systemic_oncology_mention(crit) and is_systemic_oncology_mention(doc):
        return True
    return _token_overlap(crit, doc, min_overlap=1)


# Backward-compatible alias for callers using the old name.
normalize_drug_term = normalize_clinical_text
