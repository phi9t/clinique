"""Hybrid evidence retrieval over PatientCorpus (stdlib BM25 + structured boost)."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence

from .schemas import DOC_SOURCE_TYPES, Criterion, Evidence, PatientCorpus, PatientDocument
from .temporal import document_eligible
from .vocab import (
    LAB_ANALYTE_TERMS,
    condition_matches_criterion,
    expand_query_tokens,
    is_ecog_criterion,
    medication_matches_criterion,
    tokenize,
    truncate_quote,
)

# Domain → eligible document source types. ``other`` searches all types.
_DOMAIN_SOURCE_TYPES: dict[str, frozenset[str]] = {
    "laboratory": frozenset({"observation", "note"}),
    "medication": frozenset({"medication", "note"}),
    "condition": frozenset({"condition", "note"}),
    "procedure": frozenset({"procedure", "note"}),
    "performance_status": frozenset({"observation", "note"}),
    "demographic": frozenset({"note"}),
    "other": DOC_SOURCE_TYPES,
}

MIN_BM25_SCORE = 0.05
STRUCTURED_BOOST = 2.0


def _bm25_score(
    query_tokens: list[str],
    doc_tokens: list[str],
    *,
    avg_dl: float,
    doc_freq: Counter[str],
    n_docs: int,
    k1: float = 1.5,
    b: float = 0.75,
) -> float:
    if not query_tokens or not doc_tokens:
        return 0.0
    dl = len(doc_tokens)
    tf = Counter(doc_tokens)
    score = 0.0
    for term in query_tokens:
        df = doc_freq.get(term, 0)
        if df == 0:
            continue
        idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
        freq = tf.get(term, 0)
        denom = freq + k1 * (1 - b + b * dl / avg_dl)
        score += idf * (freq * (k1 + 1)) / denom
    return score


def eligible_source_types(criterion: Criterion) -> frozenset[str]:
    return _DOMAIN_SOURCE_TYPES.get(criterion.clinical_domain, DOC_SOURCE_TYPES)


def _skip_synthea_summary(criterion: Criterion, doc: PatientDocument) -> bool:
    if doc.source_type != "note":
        return False
    if doc.structured.get("kind") != "synthea_summary":
        return False
    return criterion.clinical_domain not in {"demographic", "other"}


def _structured_match(criterion: Criterion, doc: PatientDocument) -> bool:
    domain = criterion.clinical_domain
    if domain == "laboratory" and doc.source_type == "observation":
        crit = criterion.raw_text.lower()
        desc = (doc.structured.get("description") or doc.text).lower()
        if any(term in crit for term in LAB_ANALYTE_TERMS):
            return any(term in desc for term in LAB_ANALYTE_TERMS)
        return False
    if domain == "condition" and doc.source_type == "condition":
        return condition_matches_criterion(criterion.raw_text, doc.text)
    if domain == "medication" and doc.source_type == "medication":
        return medication_matches_criterion(criterion.raw_text, doc.text)
    if domain == "procedure" and doc.source_type == "procedure":
        return bool(set(tokenize(criterion.raw_text)) & set(tokenize(doc.text)))
    if domain == "performance_status" and doc.source_type == "observation":
        return is_ecog_criterion(criterion.raw_text) and "ecog" in doc.text.lower()
    return False


def _best_quote(query_tokens: list[str], text: str) -> str:
    """Return a verbatim substring of text that best matches query tokens."""
    if not text:
        return ""
    sentences = re.split(r"(?<=[.;:\n])\s+", text)
    if not sentences:
        sentences = [text]
    best = truncate_quote(text)
    best_score = -1.0
    for sentence in sentences:
        stoks = set(tokenize(sentence))
        overlap = sum(1 for t in query_tokens if t in stoks)
        if overlap > best_score and sentence.strip():
            best_score = overlap
            best = sentence.strip()
    if best not in text:
        return truncate_quote(text)
    return best


def retrieve(
    criterion: Criterion,
    corpus: PatientCorpus,
    *,
    top_k: int = 5,
) -> tuple[Evidence, ...]:
    allowed = eligible_source_types(criterion)
    eligible_docs = [
        doc
        for doc in corpus.documents
        if document_eligible(doc.date, corpus.snapshot_date)
        and doc.source_type in allowed
        and not _skip_synthea_summary(criterion, doc)
    ]
    if not eligible_docs:
        return ()

    query_tokens = expand_query_tokens(tokenize(criterion.raw_text))
    tokenized = [tokenize(doc.text) for doc in eligible_docs]
    avg_dl = sum(len(t) for t in tokenized) / len(tokenized) if tokenized else 1.0
    doc_freq: Counter[str] = Counter()
    for tokens in tokenized:
        doc_freq.update(set(tokens))
    n_docs = len(eligible_docs)

    scored: list[tuple[float, float, PatientDocument]] = []
    for doc, tokens in zip(eligible_docs, tokenized, strict=True):
        bm25 = _bm25_score(query_tokens, tokens, avg_dl=avg_dl, doc_freq=doc_freq, n_docs=n_docs)
        boost = STRUCTURED_BOOST if _structured_match(criterion, doc) else 0.0
        if boost >= STRUCTURED_BOOST or bm25 >= MIN_BM25_SCORE:
            scored.append((bm25 + boost, bm25, doc))

    scored.sort(key=lambda pair: (-pair[0], -pair[1], pair[2].doc_id))
    evidence: list[Evidence] = []
    for _score, _bm25, doc in scored[:top_k]:
        quote = _best_quote(query_tokens, doc.text)
        if quote and quote not in doc.text:
            quote = truncate_quote(doc.text)
        evidence.append(
            Evidence(
                criterion_id=criterion.criterion_id,
                doc_id=doc.doc_id,
                quote=quote,
            )
        )
    return tuple(evidence)


def retrieve_for_criteria(
    criteria: Sequence[Criterion], corpus: PatientCorpus, *, top_k: int = 5
) -> dict[str, tuple[Evidence, ...]]:
    return {c.criterion_id: retrieve(c, corpus, top_k=top_k) for c in criteria}
