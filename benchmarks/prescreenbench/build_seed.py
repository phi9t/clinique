"""Deterministically build the PrescreenBench V0 seed splits from committed repo fixtures.

This is the provenance of ``data/synthetic`` and ``data/lite``: there is *no hand-entered clinical
data here*. Trials come from the recorded ClinicalTrials.gov fixture; patients are the committed
PHI-free Synthea/PMC fixtures; gold labels are lifted from the already-reviewed L0 eval cases
(``.workstream/prescreen-copilot/l0_cases.jsonl``). Criterion type / safety flags come from the
deterministic atomizer, and each split's overall label is the deterministic aggregation of its gold
criterion labels.

Run from the repo root:  ``uv run python benchmarks/prescreenbench/build_seed.py``
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from clinique.prescreen.aggregator import aggregate
from clinique.prescreen.atomizer import ReferenceAtomizer
from clinique.prescreen.explorer_export import find_repo_root
from clinique.prescreen.ingestion import load_recorded_studies
from clinique.prescreen.normalizer import normalize_synthea_corpus, read_synthea_csv_dir
from clinique.prescreen.pmc_patients import load_pmc_corpora
from clinique.prescreen.schemas import CriterionJudgment, PatientCorpus

# Each L0 case fixes a (patient, snapshot) pair; bake the snapshot into the stored corpus so the
# benchmark is self-contained (no per-case snapshot override needed at score time).
_PATIENT_SNAPSHOT = {"P1": "2026-03-01", "SYN-PMC-1": "2026-01-15"}


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _with_snapshot(corpus: PatientCorpus, snapshot: str | None) -> PatientCorpus:
    if snapshot is None or corpus.snapshot_date == snapshot:
        return corpus
    return PatientCorpus(
        patient_id=corpus.patient_id,
        snapshot_date=snapshot,
        source=corpus.source,
        demographics=corpus.demographics,
        documents=corpus.documents,
    )


def main() -> None:
    root = find_repo_root()
    fixtures = root / "tests" / "fixtures" / "prescreen"
    out_root = root / "benchmarks" / "prescreenbench" / "data"

    trials = load_recorded_studies(fixtures / "trials.jsonl")
    # Keep trials in the repo's canonical *raw* ClinicalTrials.gov format (what
    # load_recorded_studies re-parses), copied verbatim — not the normalized to_dict() form.
    crit_meta: dict[str, dict[str, dict]] = {}
    for trial in trials:
        crit_meta[trial.trial_id] = {
            c.criterion_id: {
                "criterion_type": c.criterion_type,
                "clinical_domain": c.clinical_domain,
                "is_safety_critical": c.is_safety_critical,
            }
            for c in ReferenceAtomizer().atomize(trial)
        }

    synthea = {
        c.patient_id: c
        for c in normalize_synthea_corpus(
            read_synthea_csv_dir(fixtures / "synthea"), snapshot_date="2026-03-01"
        )
    }
    pmc = {c.patient_id: c for c in load_pmc_corpora(fixtures / "pmc_patients.jsonl")}

    l0 = [
        json.loads(line)
        for line in (root / ".workstream/prescreen-copilot/l0_cases.jsonl").read_text().splitlines()
        if line.strip()
    ]

    raw_trials = [
        json.loads(line)
        for line in (fixtures / "trials.jsonl").read_text().splitlines()
        if line.strip()
    ]

    # Collect every referenced patient corpus, snapshot baked in.
    patient_rows: dict[str, dict] = {}
    for case in l0:
        pid, source = case["patient_id"], case["patient_source"]
        corpus = (synthea if source == "synthea" else pmc)[pid]
        corpus = _with_snapshot(corpus, _PATIENT_SNAPSHOT.get(pid, case.get("snapshot_date")))
        patient_rows[pid] = corpus.to_dict()
    patients = list(patient_rows.values())

    _DEFAULT_META = {
        "criterion_type": "inclusion",
        "clinical_domain": "other",
        "is_safety_critical": False,
    }

    def gold_criterion(trial_id: str, cid: str, label: str) -> dict:
        meta = crit_meta[trial_id].get(cid, _DEFAULT_META)
        return {
            "criterion_id": cid,
            "label": label,
            "criterion_type": meta["criterion_type"],
            "clinical_domain": meta["clinical_domain"],
            "is_safety_critical": meta["is_safety_critical"],
            "gold_evidence": [],
            "missing_information": None,
        }

    def overall(trial_id: str, crit_labels: list[dict]) -> str:
        return aggregate(
            [
                CriterionJudgment(
                    criterion_id=cl["criterion_id"],
                    criterion_type=cl["criterion_type"],
                    prediction=cl["label"],
                )
                for cl in crit_labels
            ]
        )

    # synthetic split: group by (trial, patient) -> one end_to_end case.
    grouped: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"snapshot": None, "source": None, "labels": []}
    )
    for case in l0:
        key = (case["trial_id"], case["patient_id"])
        grouped[key]["snapshot"] = case.get("snapshot_date")
        grouped[key]["source"] = case["patient_source"]
        for g in case["gold_judgments"]:
            grouped[key]["labels"].append(
                gold_criterion(case["trial_id"], g["criterion_id"], g["prediction"])
            )

    trial_ids = {trial_id for trial_id, _ in grouped}
    trial_rows = [
        trial
        for trial in raw_trials
        if trial.get("identificationModule", {}).get("nctId") in trial_ids
    ]

    syn_cases, syn_labels = [], []
    for (trial_id, patient_id), info in sorted(grouped.items()):
        case_id = f"PB-SYN-{trial_id}-{patient_id}"
        syn_cases.append(
            {
                "case_id": case_id,
                "trial_id": trial_id,
                "patient_id": patient_id,
                "patient_source": info["source"],
                "snapshot_date": _PATIENT_SNAPSHOT.get(patient_id, info["snapshot"]),
                "task": "end_to_end_packet",
            }
        )
        syn_labels.append(
            {
                "case_id": case_id,
                "overall_label": overall(trial_id, info["labels"]),
                "criterion_labels": info["labels"],
            }
        )

    # lite split: one criterion_judgment case per labeled criterion.
    lite_cases, lite_labels = [], []
    for i, case in enumerate(l0):
        for g in case["gold_judgments"]:
            cl = gold_criterion(case["trial_id"], g["criterion_id"], g["prediction"])
            case_id = f"PB-LITE-{i:03d}-{g['criterion_id']}"
            lite_cases.append(
                {
                    "case_id": case_id,
                    "trial_id": case["trial_id"],
                    "patient_id": case["patient_id"],
                    "patient_source": case["patient_source"],
                    "snapshot_date": _PATIENT_SNAPSHOT.get(
                        case["patient_id"], case.get("snapshot_date")
                    ),
                    "task": "criterion_judgment",
                }
            )
            lite_labels.append(
                {
                    "case_id": case_id,
                    "overall_label": overall(case["trial_id"], [cl]),
                    "criterion_labels": [cl],
                }
            )

    for split, cases, labels in (
        ("synthetic", syn_cases, syn_labels),
        ("lite", lite_cases, lite_labels),
    ):
        _write_jsonl(out_root / split / "trials.jsonl", trial_rows)
        _write_jsonl(out_root / split / "patients.jsonl", patients)
        _write_jsonl(out_root / split / "cases.jsonl", cases)
        _write_jsonl(out_root / split / "labels.jsonl", labels)
        print(
            f"{split}: {len(cases)} cases, {sum(len(c['criterion_labels']) for c in labels)} labels"
        )


if __name__ == "__main__":
    main()
