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
        if overlap > best_score and sentence.strip():
            best_score = overlap
            best = sentence.strip()
    if best not in text:
        return truncate_quote(text)
    return best


class EmbeddingRetriever:
    """Pure Python vector space model retriever using TF-IDF representation

    and Cosine Similarity.
    """

    def score(
        self, query_tokens: list[str], documents: list[PatientDocument]
    ) -> list[tuple[PatientDocument, float]]:
        if not query_tokens or not documents:
            return []

        # Tokenize documents
        doc_tokens_list = [tokenize(d.text) for d in documents]

        # Build terms vocabulary
        all_terms = set(query_tokens)
        for tokens in doc_tokens_list:
            all_terms.update(tokens)

        # Compute Document Frequency (DF)
        doc_freq = Counter()
        for tokens in doc_tokens_list:
            doc_freq.update(set(tokens))

        n_docs = len(documents)
        idf = {}
        for term in all_terms:
            df = doc_freq[term]
            idf[term] = math.log(1 + (n_docs / (df + 1)))

        # Vectorize query
        query_vector = {}
        query_tf = Counter(query_tokens)
        for term, tf in query_tf.items():
            query_vector[term] = tf * idf.get(term, 0.0)

        # Vectorize documents and compute cosine similarity
        scored = []
        for doc, doc_tokens in zip(documents, doc_tokens_list, strict=True):
            doc_tf = Counter(doc_tokens)
            doc_vector = {}
            for term, tf in doc_tf.items():
                if term in query_vector:
                    doc_vector[term] = tf * idf[term]

            dot_product = sum(
                query_vector[t] * doc_vector.get(t, 0.0) for t in query_vector if t in doc_vector
            )

            query_norm = math.sqrt(sum(v**2 for v in query_vector.values()))
            doc_norm = math.sqrt(sum((tf * idf[term]) ** 2 for term, tf in doc_tf.items()))

            similarity = 0.0
            if query_norm > 0 and doc_norm > 0:
                similarity = dot_product / (query_norm * doc_norm)

            scored.append((doc, similarity))

        return scored


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

    embedding_retriever = EmbeddingRetriever()
    emb_scores = {
        doc.doc_id: score for doc, score in embedding_retriever.score(query_tokens, eligible_docs)
    }

    scored: list[tuple[float, float, PatientDocument]] = []
    for doc, tokens in zip(eligible_docs, tokenized, strict=True):
        bm25 = _bm25_score(query_tokens, tokens, avg_dl=avg_dl, doc_freq=doc_freq, n_docs=n_docs)
        emb = emb_scores.get(doc.doc_id, 0.0)
        hybrid = 0.5 * bm25 + 0.5 * emb
        boost = STRUCTURED_BOOST if _structured_match(criterion, doc) else 0.0
        if boost >= STRUCTURED_BOOST or bm25 >= MIN_BM25_SCORE or emb >= 0.05:
            scored.append((hybrid + boost, bm25, doc))

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
