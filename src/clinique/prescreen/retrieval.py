"""Hybrid evidence retrieval over PatientCorpus (stdlib BM25 + structured boost)."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence

from .schemas import Criterion, Evidence, PatientCorpus, PatientDocument
from .temporal import document_eligible

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


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


def _structured_boost(criterion: Criterion, doc: PatientDocument) -> float:
    domain = criterion.clinical_domain
    if domain == "laboratory" and doc.source_type == "observation":
        return 2.0
    if domain == "medication" and doc.source_type == "medication":
        return 2.0
    if domain == "condition" and doc.source_type == "condition":
        return 2.0
    if domain == "demographic":
        return 0.0
    return 0.0


def _best_quote(query_tokens: list[str], text: str) -> str:
    """Return a verbatim substring of text that best matches query tokens."""
    if not text:
        return ""
    sentences = re.split(r"(?<=[.;:\n])\s+", text)
    if not sentences:
        sentences = [text]
    best = text[: min(len(text), 240)]
    best_score = -1.0
    for sentence in sentences:
        stoks = set(_tokenize(sentence))
        overlap = sum(1 for t in query_tokens if t in stoks)
        if overlap > best_score and sentence.strip():
            best_score = overlap
            best = sentence.strip()
    if best not in text:
        return text[: min(len(text), 240)]
    return best


def retrieve(
    criterion: Criterion,
    corpus: PatientCorpus,
    *,
    top_k: int = 5,
) -> tuple[Evidence, ...]:
    eligible_docs = [
        doc
        for doc in corpus.documents
        if document_eligible(doc.date, corpus.snapshot_date)
    ]
    if not eligible_docs:
        return ()

    query_tokens = _tokenize(criterion.raw_text)
    tokenized = [_tokenize(doc.text) for doc in eligible_docs]
    avg_dl = sum(len(t) for t in tokenized) / len(tokenized) if tokenized else 1.0
    doc_freq: Counter[str] = Counter()
    for tokens in tokenized:
        doc_freq.update(set(tokens))
    n_docs = len(eligible_docs)

    scored: list[tuple[float, PatientDocument]] = []
    for doc, tokens in zip(eligible_docs, tokenized, strict=True):
        base = _bm25_score(query_tokens, tokens, avg_dl=avg_dl, doc_freq=doc_freq, n_docs=n_docs)
        base += _structured_boost(criterion, doc)
        if base > 0:
            scored.append((base, doc))

    scored.sort(key=lambda pair: (-pair[0], pair[1].doc_id))
    evidence: list[Evidence] = []
    for _score, doc in scored[:top_k]:
        quote = _best_quote(query_tokens, doc.text)
        if quote and quote not in doc.text:
            quote = doc.text[: min(len(doc.text), 240)]
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
