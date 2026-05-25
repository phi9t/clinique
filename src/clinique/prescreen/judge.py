"""Per-criterion judge — Protocol + deterministic RuleJudge."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections.abc import Sequence
from typing import Protocol

from .schemas import Criterion, CriterionJudgment, Evidence, PatientCorpus, PatientDocument
from .temporal import evidence_within_window
from .units import compare_threshold
from .vocab import (
    is_anti_pd1_mention,
    is_ecog_criterion,
    is_nsclc_mention,
    is_prior_systemic_criterion,
    is_squamous_mention,
    medication_matches_class,
    truncate_quote,
)

EVIDENCE_LIMIT = 3
CODEX_MODEL = "gpt-5.4-mini"
CODEX_AGENT_LABEL = f"Codex CLI ({CODEX_MODEL})"
AGENT_FAILURE_MARKER = "[Agent: None]"

CODEX_JUDGMENT_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "prediction": {
            "type": "string",
            "enum": [
                "met",
                "not_met",
                "unknown",
                "not_applicable",
                "conflicting_evidence",
            ],
        },
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "criterion_id": {"type": "string"},
                    "doc_id": {"type": "string"},
                    "quote": {"type": "string"},
                    "normalized_fact": {"type": ["string", "null"]},
                },
                "required": ["criterion_id", "doc_id", "quote", "normalized_fact"],
                "additionalProperties": False,
            },
        },
        "rationale": {"type": "string"},
        "confidence": {"type": ["number", "null"]},
        "human_review_required": {"type": "boolean"},
    },
    "required": [
        "prediction",
        "evidence",
        "rationale",
        "confidence",
        "human_review_required",
    ],
    "additionalProperties": False,
}

_codex_schema_file: str | None = None


class Judge(Protocol):
    def judge(
        self,
        criterion: Criterion,
        evidence: Sequence[Evidence],
        corpus: PatientCorpus,
    ) -> CriterionJudgment: ...


def _doc_by_id(corpus: PatientCorpus) -> dict[str, PatientDocument]:
    return {doc.doc_id: doc for doc in corpus.documents}


def _evidence_from_doc(criterion_id: str, doc: PatientDocument) -> Evidence:
    return Evidence(
        criterion_id=criterion_id,
        doc_id=doc.doc_id,
        quote=truncate_quote(doc.text),
        normalized_fact=doc.structured.get("description") or doc.text,
    )


def _enrich_evidence(
    criterion_id: str,
    evidence: Sequence[Evidence],
    docs: dict[str, PatientDocument],
) -> tuple[Evidence, ...]:
    hits: list[Evidence] = []
    for ev in evidence[:EVIDENCE_LIMIT]:
        doc = docs.get(ev.doc_id)
        if doc is None:
            hits.append(ev)
            continue
        hits.append(
            Evidence(
                criterion_id=criterion_id,
                doc_id=ev.doc_id,
                quote=ev.quote,
                normalized_fact=ev.normalized_fact or doc.structured.get("description") or doc.text,
            )
        )
    return tuple(hits)


def _medication_hits(
    criterion_id: str,
    evidence: Sequence[Evidence],
    docs: dict[str, PatientDocument],
    *,
    drug_class: str,
) -> tuple[Evidence, ...]:
    hits: list[Evidence] = []
    for ev in evidence:
        doc = docs.get(ev.doc_id)
        if doc is None or doc.source_type != "medication":
            continue
        desc = doc.structured.get("description") or doc.text
        if medication_matches_class(desc, drug_class):
            hits.append(_evidence_from_doc(criterion_id, doc))
    return tuple(hits[:EVIDENCE_LIMIT])


def _base_judgment(
    criterion: Criterion,
    *,
    prediction: str,
    rationale: str,
    human_review_required: bool = False,
    evidence: Sequence[Evidence] = (),
    confidence: float | None = None,
) -> CriterionJudgment:
    return CriterionJudgment(
        criterion_id=criterion.criterion_id,
        criterion_type=criterion.criterion_type,
        prediction=prediction,
        rationale=rationale,
        human_review_required=human_review_required,
        evidence=tuple(evidence),
        confidence=confidence,
    )


def _abstain(
    criterion: Criterion,
    evidence: Sequence[Evidence],
    rationale: str,
    *,
    human_review_required: bool = True,
) -> CriterionJudgment:
    return _base_judgment(
        criterion,
        prediction="unknown",
        rationale=rationale,
        human_review_required=human_review_required,
        evidence=evidence[:EVIDENCE_LIMIT],
    )


def _judge_condition(
    criterion: Criterion,
    evidence: Sequence[Evidence],
    docs: dict[str, PatientDocument],
) -> CriterionJudgment:
    hits = _enrich_evidence(criterion.criterion_id, evidence, docs)
    if not hits:
        return _abstain(criterion, evidence, "No matching condition evidence found.")
    raw = criterion.raw_text.lower()
    if criterion.criterion_type == "inclusion" and is_nsclc_mention(raw):
        return _abstain(
            criterion,
            hits,
            "NSCLC documented; stage/histology details not confirmed in record.",
        )
    if criterion.criterion_type == "exclusion" and is_squamous_mention(raw):
        if any(is_squamous_mention(h.normalized_fact or h.quote) for h in hits):
            return _base_judgment(
                criterion,
                prediction="met",
                rationale="Squamous histology suggested in condition record.",
                evidence=hits,
            )
        return _abstain(
            criterion,
            hits,
            "Lung cancer documented; squamous histology not confirmed.",
        )
    return _abstain(
        criterion,
        hits,
        "Relevant condition evidence found; criterion not fully evaluable.",
    )


class RuleJudge:
    """Deterministic judge for demographic, lab, medication-class, and condition criteria."""

    name = "rule-judge"
    version = "0.2.0"

    def judge(
        self,
        criterion: Criterion,
        evidence: Sequence[Evidence],
        corpus: PatientCorpus,
    ) -> CriterionJudgment:
        docs = _doc_by_id(corpus)

        if criterion.ambiguity_flags and criterion.clinical_domain not in {
            "demographic",
            "laboratory",
        }:
            return _abstain(
                criterion,
                evidence,
                "Criterion flagged as ambiguous; abstaining.",
            )

        if criterion.clinical_domain == "demographic" and criterion.operator == ">=":
            age = corpus.demographics.get("age")
            threshold = criterion.threshold.value if criterion.threshold else None
            if age is None or threshold is None:
                return _abstain(criterion, evidence, "Age or threshold missing.")
            met = age >= threshold
            return _base_judgment(
                criterion,
                prediction="met" if met else "not_met",
                rationale=f"Patient age {age} vs minimum {threshold}.",
            )

        if criterion.clinical_domain == "laboratory" and criterion.threshold and criterion.operator:
            for ev in evidence:
                doc = docs.get(ev.doc_id)
                if doc is None:
                    continue
                value = doc.structured.get("value")
                unit = doc.structured.get("unit")
                if value is None:
                    continue
                if criterion.temporal_constraint:
                    ok = evidence_within_window(
                        doc.date,
                        corpus.snapshot_date,
                        window_value=criterion.temporal_constraint.window_value,
                        window_unit=criterion.temporal_constraint.window_unit,
                    )
                    if ok is False:
                        continue
                    if ok is None:
                        return _abstain(
                            criterion,
                            evidence,
                            "Temporal window could not be evaluated.",
                        )
                cmp = compare_threshold(
                    float(value),
                    unit,
                    operator=criterion.operator,
                    threshold_value=criterion.threshold.value,
                    threshold_unit=criterion.threshold.unit,
                )
                if cmp is None:
                    continue
                fact = f"{value} {unit or ''}".strip()
                enriched = Evidence(
                    criterion_id=ev.criterion_id,
                    doc_id=ev.doc_id,
                    quote=ev.quote,
                    normalized_fact=fact,
                )
                return _base_judgment(
                    criterion,
                    prediction="met" if cmp else "not_met",
                    rationale=f"Structured lab comparison: {fact} {criterion.operator} "
                    f"{criterion.threshold.value} {criterion.threshold.unit or ''}".strip(),
                    evidence=(enriched,),
                )
            return _abstain(
                criterion,
                evidence,
                "No in-window structured lab evidence found.",
            )

        if criterion.clinical_domain == "condition":
            return _judge_condition(criterion, evidence, docs)

        if criterion.clinical_domain == "medication":
            if criterion.criterion_type == "inclusion" and is_prior_systemic_criterion(
                criterion.raw_text
            ):
                oncology = _medication_hits(
                    criterion.criterion_id,
                    evidence,
                    docs,
                    drug_class="systemic_oncology",
                )
                if oncology:
                    return _base_judgment(
                        criterion,
                        prediction="not_met",
                        rationale="Prior systemic oncology therapy documented.",
                        evidence=oncology,
                    )
                med_evidence = _enrich_evidence(criterion.criterion_id, evidence, docs)
                if not med_evidence:
                    med_evidence = tuple(
                        _evidence_from_doc(criterion.criterion_id, doc)
                        for doc in corpus.documents
                        if doc.source_type == "medication"
                    )[:EVIDENCE_LIMIT]
                return _abstain(
                    criterion,
                    med_evidence,
                    "No systemic oncology therapy in medication list; "
                    "complete history not verified.",
                )

            if criterion.criterion_type == "exclusion" and is_anti_pd1_mention(criterion.raw_text):
                hits = _medication_hits(
                    criterion.criterion_id,
                    evidence,
                    docs,
                    drug_class="anti_pd1",
                )
                if hits:
                    return _base_judgment(
                        criterion,
                        prediction="met",
                        rationale="Anti-PD-1/PD-L1 agent documented.",
                        evidence=hits,
                    )
                return _abstain(
                    criterion,
                    evidence,
                    "No conclusive prior immunotherapy history found.",
                )

        if criterion.clinical_domain == "performance_status" and is_ecog_criterion(
            criterion.raw_text
        ):
            for ev in evidence:
                doc = docs.get(ev.doc_id)
                if doc is None:
                    continue
                value = doc.structured.get("value")
                if value is not None and "ecog" in doc.text.lower():
                    enriched = Evidence(
                        criterion_id=ev.criterion_id,
                        doc_id=ev.doc_id,
                        quote=ev.quote,
                        normalized_fact=f"ECOG {value}",
                    )
                    if float(value) in {0.0, 1.0}:
                        return _base_judgment(
                            criterion,
                            prediction="met",
                            rationale=f"ECOG performance status {value} (0 or 1 required).",
                            evidence=(enriched,),
                        )
                    return _base_judgment(
                        criterion,
                        prediction="not_met",
                        rationale=f"ECOG performance status {value} outside required 0–1.",
                        evidence=(enriched,),
                    )
            return _abstain(
                criterion,
                evidence,
                "No structured ECOG performance status found.",
            )

        if criterion.criterion_type == "exclusion" and criterion.requires_absence_evidence:
            return _abstain(
                criterion,
                evidence,
                "Exclusion requires explicit negative evidence; none found.",
            )

        return _abstain(
            criterion,
            evidence,
            "No deterministic rule applies; human review required.",
        )


def _extract_json(text: str) -> dict | None:
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL | re.I)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass
    try:
        return json.loads(text.strip())
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(text[start : end + 1])
        except Exception:
            pass
    return None


def codex_available() -> bool:
    return shutil.which("codex") is not None


def is_llm_agent_failure(judgment: CriterionJudgment) -> bool:
    return AGENT_FAILURE_MARKER in judgment.rationale


def make_judge(kind: str) -> Judge:
    if kind == "llm":
        return LLMJudge()
    return RuleJudge()


def _codex_schema_path() -> str:
    global _codex_schema_file
    if _codex_schema_file is None:
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as handle:
            json.dump(CODEX_JUDGMENT_SCHEMA, handle)
            _codex_schema_file = handle.name
    return _codex_schema_file


class LLMJudge:
    """Judge using Codex CLI structured output."""

    name = "llm-judge"
    version = "0.1.0"

    def _build_prompt(
        self,
        criterion: Criterion,
        evidence: Sequence[Evidence],
        corpus: PatientCorpus,
    ) -> str:
        docs_text = []
        docs = _doc_by_id(corpus)
        for ev in evidence:
            doc = docs.get(ev.doc_id)
            if doc:
                docs_text.append(
                    f"Document ID: {doc.doc_id}\n"
                    f"Date: {doc.date or 'N/A'}\n"
                    f"Type: {doc.source_type}\n"
                    f"Content: {doc.text}\n"
                    f"---"
                )
        docs_str = "\n".join(docs_text)

        prompt = (
            f"You are a clinical trial screening judge.\n"
            f"Determine if the patient satisfies the following criterion based ONLY on the "
            f"provided patient documents.\n\n"
            f"Criterion ID: {criterion.criterion_id}\n"
            f"Type: {criterion.criterion_type}\n"
            f"Clinical Domain: {criterion.clinical_domain}\n"
            f"Text: {criterion.raw_text}\n\n"
            f"Patient Documents:\n"
            f"{docs_str}\n\n"
            f"Rules:\n"
            f"1. For inclusion criteria, prediction should be 'met' if evidence supports it, "
            f"'not_met' if it contradicts, or 'unknown' if silent.\n"
            f"2. For exclusion criteria, prediction should be 'met' if the exclusion "
            f"condition is present, 'not_met' if the exclusion is explicitly absent/cleared, "
            f"or 'unknown' if silent. DO NOT assume exclusion is cleared from silence.\n"
            f"3. Every 'met' or 'not_met' prediction MUST have at least one verbatim quote "
            f"from the documents.\n"
            f"4. The quote in the evidence MUST match word-for-word in the document text.\n"
            f"5. Provide a clear rationale.\n\n"
            f"You must return a JSON object with the following schema:\n"
            f"{{\n"
            f'  "prediction": "met" | "not_met" | "unknown" | "not_applicable" '
            f'| "conflicting_evidence",\n'
            f'  "evidence": [\n'
            f"    {{\n"
            f'      "criterion_id": "{criterion.criterion_id}",\n'
            f'      "doc_id": "string",\n'
            f'      "quote": "string",\n'
            f'      "normalized_fact": "string"\n'
            f"    }}\n"
            f"  ],\n"
            f'  "rationale": "string",\n'
            f'  "confidence": float,\n'
            f'  "human_review_required": boolean\n'
            f"}}\n"
        )
        return prompt

    def _build_judgment_from_json(
        self, criterion: Criterion, data: dict, agent_name: str
    ) -> CriterionJudgment:
        evidence_list = []
        for ev in data.get("evidence", []):
            evidence_list.append(
                Evidence(
                    criterion_id=ev.get("criterion_id") or criterion.criterion_id,
                    doc_id=ev.get("doc_id", ""),
                    quote=ev.get("quote", ""),
                    normalized_fact=ev.get("normalized_fact"),
                )
            )

        provenance_suffix = f" [Agent: {agent_name}]"
        raw_rationale = data.get("rationale") or "LLM judgment generated successfully."
        rationale = f"{raw_rationale.strip()}{provenance_suffix}"

        return CriterionJudgment(
            criterion_id=criterion.criterion_id,
            criterion_type=criterion.criterion_type,
            prediction=data.get("prediction") or "unknown",
            evidence=tuple(evidence_list),
            rationale=rationale,
            confidence=data.get("confidence"),
            human_review_required=bool(data.get("human_review_required", True)),
        )

    def _call_codex_cli(self, criterion: Criterion, prompt: str) -> CriterionJudgment | None:
        schema_path = _codex_schema_path()
        try:
            cmd = [
                "codex",
                "exec",
                "--model",
                CODEX_MODEL,
                "--output-schema",
                schema_path,
                "--dangerously-bypass-approvals-and-sandbox",
                prompt,
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=45
            )
            if result.returncode == 0:
                data = _extract_json(result.stdout)
                if data:
                    return self._build_judgment_from_json(criterion, data, CODEX_AGENT_LABEL)
                print(f"[LLMJudge Debug] Codex CLI stdout did not contain JSON: {result.stdout}")
            else:
                print(
                    f"[LLMJudge Debug] Codex CLI exited with {result.returncode}.\n"
                    f"stdout: {result.stdout}\nstderr: {result.stderr}"
                )
        except Exception as exc:
            import traceback

            print(f"[LLMJudge Debug] Codex CLI exception: {exc}")
            traceback.print_exc()
        return None

    def judge(
        self,
        criterion: Criterion,
        evidence: Sequence[Evidence],
        corpus: PatientCorpus,
        *,
        prompt: str | None = None,
    ) -> CriterionJudgment:
        if not codex_available():
            raise RuntimeError(
                "Codex CLI not found for LLMJudge. Install with: npm install -g @codex/cli"
            )

        resolved_prompt = prompt or self._build_prompt(criterion, evidence, corpus)
        judgment = self._call_codex_cli(criterion, resolved_prompt)
        if judgment:
            return judgment

        return CriterionJudgment(
            criterion_id=criterion.criterion_id,
            criterion_type=criterion.criterion_type,
            prediction="unknown",
            rationale=f"LLM judgment failed via Codex CLI. {AGENT_FAILURE_MARKER}",
            human_review_required=True,
        )
