"""L0 eval harness and workstream verification."""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .atomizer import ReferenceAtomizer
from .datasets import ensure_datasets_present, resolve_all_datasets
from .evidence_gate import check_evidence_provenance
from .ingestion import load_recorded_studies
from .orchestrator import PrescreenOrchestrator, packet_fingerprint
from .pmc_patients import load_pmc_corpora
from .schemas import PatientCorpus, Trial
from .validation import corpus_from_dict, report_for


@dataclass(frozen=True)
class EvalCase:
    trial_id: str
    patient_id: str
    snapshot_date: str | None
    gold_judgments: tuple[dict[str, str], ...]
    patient_source: str = "synthea"

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> EvalCase:
        return cls(
            trial_id=raw["trial_id"],
            patient_id=raw["patient_id"],
            snapshot_date=raw.get("snapshot_date"),
            gold_judgments=tuple(raw.get("gold_judgments", [])),
            patient_source=raw.get("patient_source", "synthea"),
        )


def load_eval_cases(path: str | Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                cases.append(EvalCase.from_dict(json.loads(line)))
    return cases


def load_patient_corpora(path: str | Path, *, source: str) -> list[PatientCorpus]:
    if source == "pmc":
        return load_pmc_corpora(path)
    corpora: list[PatientCorpus] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                corpora.append(corpus_from_dict(json.loads(line)))
    return corpora


def _index_trials(trials: list[Trial]) -> dict[str, Trial]:
    return {t.trial_id: t for t in trials}


def _index_corpora(corpora: list[PatientCorpus]) -> dict[str, PatientCorpus]:
    return {c.patient_id: c for c in corpora}


@dataclass
class EvalMetrics:
    cases_run: int = 0
    criterion_total: int = 0
    criterion_correct: int = 0
    evidence_violations: int = 0
    exclusion_false_negatives: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def criterion_accuracy(self) -> float:
        if self.criterion_total == 0:
            return 1.0
        return self.criterion_correct / self.criterion_total

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "criterion_accuracy": self.criterion_accuracy,
        }


def run_eval_cases(
    cases: list[EvalCase],
    *,
    trials: list[Trial],
    corpora_by_source: dict[str, list[PatientCorpus]],
) -> EvalMetrics:
    metrics = EvalMetrics()
    orchestrator = PrescreenOrchestrator()
    trials_by_id = _index_trials(trials)
    corpora_index = {source: _index_corpora(items) for source, items in corpora_by_source.items()}

    for case in cases:
        trial = trials_by_id.get(case.trial_id)
        if trial is None:
            metrics.errors.append(f"missing trial {case.trial_id}")
            continue
        corpus = corpora_index.get(case.patient_source, {}).get(case.patient_id)
        if corpus is None:
            metrics.errors.append(f"missing patient {case.patient_id} source={case.patient_source}")
            continue
        if case.snapshot_date and corpus.snapshot_date != case.snapshot_date:
            corpus = PatientCorpus(
                patient_id=corpus.patient_id,
                snapshot_date=case.snapshot_date,
                source=corpus.source,
                demographics=corpus.demographics,
                documents=corpus.documents,
            )
        try:
            packet = orchestrator.screen(trial, corpus)
        except Exception as exc:  # noqa: BLE001 — collect eval errors
            metrics.errors.append(f"screen failed {case.trial_id}/{case.patient_id}: {exc}")
            continue
        metrics.cases_run += 1
        gold = {g["criterion_id"]: g["prediction"] for g in case.gold_judgments}
        pred_by_id = {j.criterion_id: j for j in packet.judgments}
        for cid, expected in gold.items():
            metrics.criterion_total += 1
            actual = pred_by_id.get(cid)
            if actual and actual.prediction == expected:
                metrics.criterion_correct += 1
            elif actual and actual.criterion_type == "exclusion" and actual.prediction == "not_met":
                if expected == "unknown":
                    metrics.exclusion_false_negatives += 1
        metrics.evidence_violations += len(check_evidence_provenance(packet, corpus))
    return metrics


@dataclass
class WorkstreamGates:
    corpus_conformance_ok: bool = False
    atomizer_coverage: float = 0.0
    criterion_accuracy: float = 0.0
    evidence_violations: int = 0
    exclusion_false_negatives: int = 0
    scale_smoke_ok: bool = False
    determinism_ok: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def goal_complete(self) -> bool:
        return (
            self.corpus_conformance_ok
            and self.atomizer_coverage >= 0.95
            and self.criterion_accuracy >= 0.90
            and self.evidence_violations == 0
            and self.exclusion_false_negatives == 0
            and self.scale_smoke_ok
            and self.determinism_ok
        )


def eval_metrics_passes_gates(metrics: EvalMetrics | dict[str, Any]) -> bool:
    if isinstance(metrics, EvalMetrics):
        accuracy = metrics.criterion_accuracy
        violations = metrics.evidence_violations
        false_negs = metrics.exclusion_false_negatives
        errors = metrics.errors
        cases_run = metrics.cases_run
        criterion_total = metrics.criterion_total
    else:
        accuracy = float(metrics.get("criterion_accuracy", 0))
        violations = int(metrics.get("evidence_violations", 0))
        false_negs = int(metrics.get("exclusion_false_negatives", 0))
        errors = list(metrics.get("errors") or [])
        cases_run = int(metrics.get("cases_run", 0))
        criterion_total = int(metrics.get("criterion_total", 0))
    return (
        cases_run > 0
        and criterion_total > 0
        and accuracy >= 0.90
        and violations == 0
        and false_negs == 0
        and not errors
    )


def eval_metrics_parity(
    sync: EvalMetrics,
    temporal: dict[str, Any],
) -> tuple[bool, list[str]]:
    issues: list[str] = []
    pairs = (
        ("cases_run", sync.cases_run, temporal.get("cases_run")),
        ("criterion_total", sync.criterion_total, temporal.get("criterion_total")),
        ("criterion_correct", sync.criterion_correct, temporal.get("criterion_correct")),
        ("evidence_violations", sync.evidence_violations, temporal.get("evidence_violations")),
        (
            "exclusion_false_negatives",
            sync.exclusion_false_negatives,
            temporal.get("exclusion_false_negatives"),
        ),
    )
    for name, left, right in pairs:
        if left != right:
            issues.append(f"{name}: sync={left} temporal={right}")
    if sync.criterion_accuracy != temporal.get("criterion_accuracy"):
        issues.append(
            "criterion_accuracy: "
            f"sync={sync.criterion_accuracy} temporal={temporal.get('criterion_accuracy')}"
        )
    return not issues, issues


async def _run_temporal_batch_eval_async(
    *,
    cases_path: Path,
    dataset_paths: dict[str, Path],
    reports_dir: Path,
    temporal_host: str,
) -> dict[str, Any]:
    from clinique.durable.cli_runtime import connect_client
    from clinique.durable.client import execute_batch_eval
    from clinique.durable.models import BatchEvalInput

    client = await connect_client(temporal_host)
    return await execute_batch_eval(
        client,
        BatchEvalInput(
            cases_path=str(cases_path),
            trials_path=str(dataset_paths["trials"]),
            synthea_patients_path=str(dataset_paths["synthea_patients"]),
            pmc_patients_path=str(dataset_paths["pmc_patients"]),
            mimic_patients_path=str(dataset_paths["mimic_demo_patients"]),
            reports_dir=str(reports_dir),
        ),
    )


def run_temporal_batch_eval(
    *,
    cases_path: Path,
    dataset_paths: dict[str, Path],
    reports_dir: Path,
    temporal_host: str = "localhost:7233",
) -> dict[str, Any]:
    import asyncio

    return asyncio.run(
        _run_temporal_batch_eval_async(
            cases_path=cases_path,
            dataset_paths=dataset_paths,
            reports_dir=reports_dir,
            temporal_host=temporal_host,
        )
    )


def verify_workstream(
    *,
    workstream_dir: str | Path = ".workstream/prescreen-copilot",
    datasets_dir: str | Path | None = None,
    reports_dir: str | Path = "reports/prescreen",
    cases_path: str | Path | None = None,
    smoke_pairs: int = 50,
    seed: int = 42,
    temporal: bool = False,
    temporal_host: str = "localhost:7233",
    temporal_eval_runner=run_temporal_batch_eval,
) -> dict[str, Any]:
    ws = Path(workstream_dir)
    manifest_path = ws / "datasets.manifest.json"
    missing = ensure_datasets_present(datasets_dir=datasets_dir, manifest_path=manifest_path)
    if missing:
        raise FileNotFoundError(
            "missing datasets: "
            f"{', '.join(missing)} under {datasets_dir or '~/.clinique/datasets'}. "
            "Run fetch recipes in .workstream/prescreen-copilot/data-inventory.md"
        )

    paths = resolve_all_datasets(datasets_dir=datasets_dir, manifest_path=manifest_path)
    trials = load_recorded_studies(paths["trials"])
    fixture_trials = load_recorded_studies("tests/fixtures/prescreen/trials.jsonl")
    trials_by_id = {t.trial_id: t for t in trials}
    for trial in fixture_trials:
        trials_by_id.setdefault(trial.trial_id, trial)
    trials = list(trials_by_id.values())
    synthea = load_patient_corpora(paths["synthea_patients"], source="synthea")
    pmc = load_patient_corpora(paths["pmc_patients"], source="pmc")
    mimic = load_patient_corpora(paths["mimic_demo_patients"], source="mimic")

    conformance = report_for(trials=trials, corpora=synthea + pmc + mimic)
    gates = WorkstreamGates()
    gates.corpus_conformance_ok = conformance.ok

    atomizer = ReferenceAtomizer()
    produced = sum(1 for t in trials if atomizer.atomize(t))
    gates.atomizer_coverage = produced / len(trials) if trials else 1.0

    cases_file = Path(cases_path or ws / "l0_cases.jsonl")
    cases = load_eval_cases(cases_file)
    eval_metrics = run_eval_cases(
        cases,
        trials=trials,
        corpora_by_source={"synthea": synthea, "pmc": pmc, "mimic": mimic},
    )
    gates.criterion_accuracy = eval_metrics.criterion_accuracy
    gates.evidence_violations = eval_metrics.evidence_violations
    gates.exclusion_false_negatives = eval_metrics.exclusion_false_negatives

    if eval_metrics.cases_run == 0 or eval_metrics.criterion_total == 0:
        eval_metrics.errors.append("no gold eval cases executed")

    orchestrator = PrescreenOrchestrator()
    rng = random.Random(seed)
    trial_sample = trials[:]
    patient_pool = synthea + pmc + mimic
    rng.shuffle(trial_sample)
    smoke_ok = True
    attempts = min(smoke_pairs, len(trial_sample) * max(len(patient_pool), 1))
    for i in range(attempts):
        trial = trial_sample[i % len(trial_sample)]
        patient = patient_pool[i % len(patient_pool)]
        try:
            orchestrator.screen(trial, patient)
        except Exception:
            smoke_ok = False
            break
    gates.scale_smoke_ok = smoke_ok

    if trials and synthea:
        p1 = orchestrator.screen(trials[0], synthea[0])
        p2 = orchestrator.screen(trials[0], synthea[0])
        gates.determinism_ok = packet_fingerprint(p1) == packet_fingerprint(p2)
    else:
        gates.determinism_ok = True

    output_dir = Path(reports_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    temporal_block: dict[str, Any] = {"ran": False}
    if temporal:
        temporal_eval = temporal_eval_runner(
            cases_path=cases_file,
            dataset_paths=paths,
            reports_dir=output_dir,
            temporal_host=temporal_host,
        )
        parity_ok, parity_issues = eval_metrics_parity(eval_metrics, temporal_eval)
        temporal_block = {
            "ran": True,
            "host": temporal_host,
            "eval": temporal_eval,
            "eval_passes": eval_metrics_passes_gates(temporal_eval),
            "parity_ok": parity_ok,
            "parity_issues": parity_issues,
            "temporal_goal_complete": eval_metrics_passes_gates(temporal_eval) and parity_ok,
        }

    report = {
        "goal_complete": gates.goal_complete
        and eval_metrics.cases_run > 0
        and eval_metrics.criterion_total > 0,
        "gates": gates.as_dict(),
        "conformance": conformance.to_dict(),
        "eval": eval_metrics.to_dict(),
        "temporal": temporal_block,
        "verification_complete": (
            gates.goal_complete
            and eval_metrics.cases_run > 0
            and eval_metrics.criterion_total > 0
            and (not temporal or temporal_block.get("temporal_goal_complete", False))
        ),
        "datasets": {k: str(v) for k, v in paths.items()},
        "records": {
            "trials": len(trials),
            "synthea_patients": len(synthea),
            "pmc_patients": len(pmc),
            "mimic_patients": len(mimic),
        },
    }
    (output_dir / "workstream-verification.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary_lines = [
        "# Prescreen Copilot Validation Summary",
        "",
        "## Sync verification (`goal_complete`)",
        "",
        f"- goal_complete: **{report['goal_complete']}**",
        f"- corpus_conformance_ok: {gates.corpus_conformance_ok}",
        f"- atomizer_coverage: {gates.atomizer_coverage:.3f}",
        f"- criterion_accuracy: {gates.criterion_accuracy:.3f}",
        f"- evidence_violations: {gates.evidence_violations}",
        f"- exclusion_false_negatives: {gates.exclusion_false_negatives}",
        f"- scale_smoke_ok: {gates.scale_smoke_ok}",
        f"- determinism_ok: {gates.determinism_ok}",
        "",
        f"Full report: `{output_dir / 'workstream-verification.json'}`",
        "",
    ]
    if temporal:
        summary_lines.extend(
            [
                "## Temporal verification (`--temporal`)",
                "",
                f"- temporal_goal_complete: **{temporal_block['temporal_goal_complete']}**",
                f"- eval_passes: {temporal_block['eval_passes']}",
                f"- parity_with_sync: {temporal_block['parity_ok']}",
            ]
        )
        if temporal_block["parity_issues"]:
            summary_lines.append(f"- parity_issues: {temporal_block['parity_issues']}")
        summary_lines.extend(
            [
                "",
                f"Temporal eval report: `{temporal_block['eval'].get('report_path', 'n/a')}`",
                "",
            ]
        )
    summary_lines.extend(
        [
            "## Durable pytest evidence",
            "",
            "```bash",
            "uv sync --group temporal",
            "uv run pytest tests/test_durable_models.py tests/test_durable_prescreen.py "
            "tests/test_durable_prescreen_e2e.py -q",
            "```",
            "",
        ]
    )
    summary_path = ws / "validation-summary.md"
    summary_path.write_text("\n".join(summary_lines), encoding="utf-8")
    return report
