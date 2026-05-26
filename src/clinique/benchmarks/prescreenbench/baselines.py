"""Reference agents for PrescreenBench.

Each baseline maps ``(case, trial, corpus) -> SubmissionPacket``. They span the failure space the
benchmark is designed to separate:

- ``always_unknown`` — conservative floor. Abstains on everything: passes every safety gate but has
  near-zero macro-F1 and blocking recall ("safe but useless").
- ``keyword_rule`` — naive retrieval. Treats any retrieved snippet as satisfying the criterion, so
  it *clears exclusions from mere keyword presence* — the canonical unsafe-clearance failure.
- ``clinique_rule`` — the deterministic clinique pipeline (atomize → retrieve → RuleJudge).
- ``clinique_llm`` — the clinique pipeline with the LLM judge (requires credentials).
- ``one_shot_llm`` — LLM judge with no retrieval (criterion + raw corpus). Requires credentials.

All baselines atomize with ``ReferenceAtomizer`` so their ``criterion_id``s align with the gold
labels (which were authored against that atomizer).
"""

from __future__ import annotations

from collections.abc import Callable

from clinique.prescreen.aggregator import aggregate
from clinique.prescreen.atomizer import ReferenceAtomizer
from clinique.prescreen.orchestrator import PrescreenOrchestrator
from clinique.prescreen.retrieval import retrieve
from clinique.prescreen.schemas import (
    Criterion,
    CriterionJudgment,
    PatientCorpus,
    PrescreeningPacket,
    Trial,
)

from .schema import SubmissionPacket, packet_to_submission

BaselineFn = Callable[[object, Trial, PatientCorpus], SubmissionPacket]

# Baselines that run fully offline and are exercised in tests.
DETERMINISTIC = ("always_unknown", "keyword_rule", "clinique_rule")
# Baselines that call an external LLM and need credentials at run time.
LLM_BACKED = ("clinique_llm", "one_shot_llm")


def _packet_from_judgments(
    case_id: str,
    trial: Trial,
    corpus: PatientCorpus,
    criteria: tuple[Criterion, ...],
    judgments: list[CriterionJudgment],
) -> SubmissionPacket:
    packet = PrescreeningPacket(
        trial_id=trial.trial_id,
        patient_id=corpus.patient_id,
        snapshot_date=corpus.snapshot_date,
        criteria=criteria,
        judgments=tuple(judgments),
        recommendation=aggregate(judgments),
    )
    return packet_to_submission(case_id, packet)


def always_unknown(case, trial: Trial, corpus: PatientCorpus) -> SubmissionPacket:
    criteria = ReferenceAtomizer().atomize(trial)
    judgments = [
        CriterionJudgment(
            criterion_id=c.criterion_id,
            criterion_type=c.criterion_type,
            prediction="unknown",
            rationale="baseline abstains",
            human_review_required=True,
        )
        for c in criteria
    ]
    return _packet_from_judgments(case.case_id, trial, corpus, criteria, judgments)


def keyword_rule(case, trial: Trial, corpus: PatientCorpus) -> SubmissionPacket:
    criteria = ReferenceAtomizer().atomize(trial)
    judgments: list[CriterionJudgment] = []
    for crit in criteria:
        evidence = retrieve(crit, corpus, top_k=1)
        if evidence:
            # Naive: presence of a keyword hit "satisfies" the criterion. For an exclusion this
            # means predicting not_met (cleared) — deliberately unsafe, to exercise the metric.
            prediction = "met" if crit.criterion_type == "inclusion" else "not_met"
            judgments.append(
                CriterionJudgment(
                    criterion_id=crit.criterion_id,
                    criterion_type=crit.criterion_type,
                    prediction=prediction,
                    evidence=evidence,
                    rationale=f"keyword match: {evidence[0].quote[:60]}",
                )
            )
        else:
            judgments.append(
                CriterionJudgment(
                    criterion_id=crit.criterion_id,
                    criterion_type=crit.criterion_type,
                    prediction="unknown",
                    rationale="no keyword match",
                )
            )
    return _packet_from_judgments(case.case_id, trial, corpus, criteria, judgments)


def clinique_rule(case, trial: Trial, corpus: PatientCorpus) -> SubmissionPacket:
    packet = PrescreenOrchestrator().screen(trial, corpus)
    return packet_to_submission(case.case_id, packet)


def clinique_llm(case, trial: Trial, corpus: PatientCorpus) -> SubmissionPacket:
    from clinique.prescreen.judge import make_judge

    packet = PrescreenOrchestrator(judge=make_judge("llm")).screen(trial, corpus)
    return packet_to_submission(case.case_id, packet)


def one_shot_llm(case, trial: Trial, corpus: PatientCorpus) -> SubmissionPacket:
    """LLM judge with *no retrieval* — each criterion is judged against the raw corpus."""
    from clinique.prescreen.judge import make_judge

    judge = make_judge("llm")
    criteria = ReferenceAtomizer().atomize(trial)
    judgments = [judge.judge(crit, (), corpus) for crit in criteria]
    return _packet_from_judgments(case.case_id, trial, corpus, criteria, judgments)


BASELINES: dict[str, BaselineFn] = {
    "always_unknown": always_unknown,
    "keyword_rule": keyword_rule,
    "clinique_rule": clinique_rule,
    "clinique_llm": clinique_llm,
    "one_shot_llm": one_shot_llm,
}


def get_baseline(name: str) -> BaselineFn:
    try:
        return BASELINES[name]
    except KeyError:
        raise ValueError(
            f"unknown baseline {name!r}; choose from {', '.join(sorted(BASELINES))}"
        ) from None
