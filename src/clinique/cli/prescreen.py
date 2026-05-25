"""Trial prescreening CLI handlers."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import urllib.error
from pathlib import Path

from clinique.prescreen.atomizer import ReferenceAtomizer
from clinique.prescreen.eval import load_eval_cases, run_eval_cases, verify_workstream
from clinique.prescreen.explorer_export import (
    export_explorer as write_explorer_json,
    find_repo_root,
)
from clinique.prescreen.ingestion import (
    load_recorded_studies,
    record_search,
    record_studies,
)
from clinique.prescreen.mimic_demo import normalize_mimic_corpus, read_mimic_csv_dir
from clinique.prescreen.normalizer import normalize_synthea_corpus, read_synthea_csv_dir
from clinique.prescreen.orchestrator import PrescreenOrchestrator
from clinique.prescreen.pmc_patients import load_pmc_corpora, record_pmc
from clinique.prescreen.retrieval import retrieve_for_criteria
from clinique.prescreen.schemas import PatientCorpus, Trial
from clinique.prescreen.validation import corpus_from_dict, report_for


def _resolve_repo_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return find_repo_root() / candidate


def _load_screen_case(
    *,
    trials_path: str,
    trial_id: str,
    patient_id: str,
    patients_path: str | None = None,
    source: str = "synthea",
    synthea_csv_dir: str | None = None,
    snapshot: str | None = None,
) -> tuple[Trial, PatientCorpus]:
    trials = load_recorded_studies(str(_resolve_repo_path(trials_path)))
    trial = next((t for t in trials if t.trial_id == trial_id), None)
    if trial is None:
        raise ValueError("trial_id not found")

    if patients_path:
        resolved_patients = str(_resolve_repo_path(patients_path))
        if source == "pmc":
            corpora = load_pmc_corpora(resolved_patients)
        else:
            with Path(resolved_patients).open(encoding="utf-8") as handle:
                corpora = [corpus_from_dict(json.loads(line)) for line in handle if line.strip()]
    elif synthea_csv_dir is not None:
        tables = read_synthea_csv_dir(_resolve_repo_path(synthea_csv_dir))
        corpora = normalize_synthea_corpus(tables, snapshot_date=snapshot)
    else:
        raise ValueError("patients_path or synthea_csv_dir is required")

    corpus = next((c for c in corpora if c.patient_id == patient_id), None)
    if corpus is None:
        raise ValueError("patient_id not found")
    return trial, corpus


def _run_temporal_screen(args: argparse.Namespace, trial, corpus) -> int:
    try:
        from temporalio.client import WorkflowFailureError

        from clinique.durable.cli_runtime import (
            connect_client,
            ensure_temporalio,
            temporal_import_error,
        )
        from clinique.durable.client import execute_screen
        from clinique.durable.models import PatientCorpusModel, TrialModel
    except ImportError as exc:
        return temporal_import_error(exc)

    ensure_temporalio()

    async def _run():
        client = await connect_client(args.temporal_host)
        return await execute_screen(
            client,
            trial=TrialModel.from_domain(trial),
            corpus=PatientCorpusModel.from_domain(corpus),
            append_ledger=bool(args.ledger),
            ledger_path=args.ledger,
        )

    try:
        packet = asyncio.run(_run())
    except WorkflowFailureError as exc:
        print(f"prescreen screen temporal workflow failed: {exc.cause}", file=sys.stderr)
        return 3
    except OSError as exc:
        print(f"prescreen screen temporal connect failed: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(packet.model_dump(), indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


def handle_prescreen(args: argparse.Namespace) -> int | None:
    if args.command != "prescreen":
        return None
    if args.prescreen_command == "ingest":
        nct_ids = [n.strip() for n in args.nct_ids.split(",") if n.strip()]
        try:
            recorded = record_studies(nct_ids, args.out)
        except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
            print(f"prescreen ingest failed: {exc}", file=sys.stderr)
            return 2
        print(f"recorded {len(recorded)} studies to {args.out}: {', '.join(recorded)}")
        return 0
    if args.prescreen_command == "search":
        status = [s.strip() for s in args.status.split(",") if s.strip()] if args.status else None
        try:
            recorded = record_search(
                args.out, cond=args.cond, term=args.term, status=status, max_studies=args.max
            )
        except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
            print(f"prescreen search failed: {exc}", file=sys.stderr)
            return 2
        print(f"recorded {len(recorded)} studies to {args.out}")
        return 0
    if args.prescreen_command == "normalize-synthea":
        try:
            tables = read_synthea_csv_dir(args.csv_dir)
            corpora = normalize_synthea_corpus(tables, snapshot_date=args.snapshot)
        except (OSError, ValueError) as exc:
            print(f"prescreen normalize-synthea failed: {exc}", file=sys.stderr)
            return 2
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as handle:
            for corpus in corpora:
                handle.write(json.dumps(corpus.to_dict(), sort_keys=True) + "\n")
        print(f"normalized {len(corpora)} patients to {args.out}")
        return 0
    if args.prescreen_command == "ingest-pmc":
        try:
            count = record_pmc(args.out, limit=args.limit)
        except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
            print(f"prescreen ingest-pmc failed: {exc}", file=sys.stderr)
            return 2
        print(f"recorded {count} PMC-Patients records to {args.out}")
        return 0
    if args.prescreen_command == "normalize-mimic-demo":
        try:
            tables = read_mimic_csv_dir(args.csv_dir)
            corpora = normalize_mimic_corpus(tables, snapshot_date=args.snapshot)
        except (OSError, ValueError) as exc:
            print(f"prescreen normalize-mimic-demo failed: {exc}", file=sys.stderr)
            return 2
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as handle:
            for corpus in corpora:
                handle.write(json.dumps(corpus.to_dict(), sort_keys=True) + "\n")
        print(f"normalized {len(corpora)} patients to {args.out}")
        return 0
    if args.prescreen_command == "atomize":
        try:
            trials = load_recorded_studies(args.trials)
        except (OSError, ValueError) as exc:
            print(f"prescreen atomize failed: {exc}", file=sys.stderr)
            return 2
        atomizer = ReferenceAtomizer()
        lines: list[str] = []
        for trial in trials:
            if args.trial_id and trial.trial_id != args.trial_id:
                continue
            for criterion in atomizer.atomize(trial):
                lines.append(json.dumps(criterion.to_dict(), sort_keys=True))
        text = "\n".join(lines) + ("\n" if lines else "")
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
        else:
            print(text, end="")
        print(f"atomized {len(lines)} criteria", file=sys.stderr)
        return 0
    if args.prescreen_command == "screen":
        try:
            trial, corpus = _load_screen_case(
                trials_path=args.trials,
                patients_path=args.patients,
                trial_id=args.trial_id,
                patient_id=args.patient_id,
                source=args.source,
            )
        except (OSError, ValueError) as exc:
            print(f"prescreen screen failed: {exc}", file=sys.stderr)
            return 2
        if args.temporal:
            return _run_temporal_screen(args, trial, corpus)
        try:
            from clinique.prescreen.judge import make_judge

            j = make_judge(args.judge)
            orchestrator = PrescreenOrchestrator(judge=j)
            if args.ledger:
                from clinique.substrate.provenance import ProvenanceLedger

                packet = orchestrator.screen_and_append(
                    trial, corpus, ProvenanceLedger(args.ledger)
                )
            else:
                packet = orchestrator.screen(trial, corpus)
        except Exception as exc:
            from clinique.prescreen.evidence_gate import EvidenceProvenanceError

            if isinstance(exc, EvidenceProvenanceError):
                print(f"prescreen screen evidence gate failed: {exc}", file=sys.stderr)
                return 8
            print(f"prescreen screen failed: {exc}", file=sys.stderr)
            return 2
        text = json.dumps(packet.to_dict(), indent=2, sort_keys=True) + "\n"
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
        else:
            print(text, end="")
        return 0
    if args.prescreen_command == "worker":
        try:
            from clinique.durable.cli_runtime import ensure_temporalio, temporal_import_error
            from clinique.durable.worker import run_worker
        except ImportError as exc:
            return temporal_import_error(exc)
        ensure_temporalio()
        try:
            asyncio.run(run_worker(host=args.host))
        except OSError as exc:
            print(f"prescreen worker connect failed: {exc}", file=sys.stderr)
            return 2
        return 0
    if args.prescreen_command == "eval-temporal":
        try:
            from temporalio.client import WorkflowFailureError

            from clinique.durable.cli_runtime import (
                connect_client,
                ensure_temporalio,
                temporal_import_error,
            )
            from clinique.durable.client import execute_batch_eval
            from clinique.durable.models import BatchEvalInput
        except ImportError as exc:
            return temporal_import_error(exc)
        ensure_temporalio()

        async def _run_eval() -> dict:
            client = await connect_client(args.host)
            return await execute_batch_eval(
                client,
                BatchEvalInput(
                    cases_path=args.cases,
                    trials_path=args.trials,
                    synthea_patients_path=args.synthea_patients,
                    pmc_patients_path=args.pmc_patients,
                    mimic_patients_path=args.mimic_patients,
                    reports_dir=args.reports_dir,
                ),
            )

        try:
            report = asyncio.run(_run_eval())
        except WorkflowFailureError as exc:
            print(f"prescreen eval-temporal workflow failed: {exc.cause}", file=sys.stderr)
            return 3
        except OSError as exc:
            print(f"prescreen eval-temporal connect failed: {exc}", file=sys.stderr)
            return 2
        print(
            f"criterion_accuracy={report.get('criterion_accuracy', 0):.3f} "
            f"wrote {report.get('report_path', args.reports_dir)}",
            file=sys.stderr,
        )
        if report.get("errors") or report.get("criterion_accuracy", 0) < 0.90:
            return 9
        return 0
    if args.prescreen_command == "eval":
        try:
            cases = load_eval_cases(args.cases)
            trials = load_recorded_studies(args.trials)
            synthea_path = args.synthea_patients or args.patients
            corpora_by_source = {}
            if synthea_path:
                with Path(synthea_path).open(encoding="utf-8") as handle:
                    corpora_by_source["synthea"] = [
                        corpus_from_dict(json.loads(line)) for line in handle if line.strip()
                    ]
            if args.pmc_patients:
                corpora_by_source["pmc"] = load_pmc_corpora(args.pmc_patients)
            if args.mimic_patients:
                with Path(args.mimic_patients).open(encoding="utf-8") as handle:
                    corpora_by_source["mimic"] = [
                        corpus_from_dict(json.loads(line)) for line in handle if line.strip()
                    ]
            from clinique.prescreen.judge import make_judge

            j = make_judge(args.judge)
            metrics = run_eval_cases(
                cases, trials=trials, corpora_by_source=corpora_by_source, judge=j
            )
        except (OSError, ValueError) as exc:
            print(f"prescreen eval failed: {exc}", file=sys.stderr)
            return 2
        report = metrics.to_dict()
        text = json.dumps(report, indent=2, sort_keys=True) + "\n"
        out_dir = Path(args.reports_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "l0-eval.json"
        out_path.write_text(text, encoding="utf-8")
        print(f"wrote {out_path}", file=sys.stderr)
        if metrics.errors or metrics.criterion_accuracy < 0.90 or metrics.evidence_violations:
            return 9
        return 0
    if args.prescreen_command == "verify-workstream":
        try:
            from clinique.prescreen.judge import make_judge

            j = make_judge(args.judge)
            report = verify_workstream(
                workstream_dir=args.workstream,
                datasets_dir=args.datasets_dir,
                reports_dir=args.reports_dir,
                cases_path=args.cases,
                temporal=args.temporal,
                temporal_host=args.temporal_host,
                judge=j,
            )
        except FileNotFoundError as exc:
            print(f"prescreen verify-workstream failed: {exc}", file=sys.stderr)
            return 3
        except ImportError as exc:
            print(f"prescreen verify-workstream failed: {exc}", file=sys.stderr)
            return 2
        except (OSError, ValueError) as exc:
            print(f"prescreen verify-workstream failed: {exc}", file=sys.stderr)
            return 2
        msg = (
            f"goal_complete={report['goal_complete']} "
            f"criterion_accuracy={report['eval']['criterion_accuracy']:.3f}"
        )
        if args.temporal:
            temporal = report.get("temporal", {})
            msg += (
                f" temporal_goal_complete={temporal.get('temporal_goal_complete')} "
                f"parity_ok={temporal.get('parity_ok')}"
            )
        print(msg, file=sys.stderr)
        return 0 if report["verification_complete"] else 9
    if args.prescreen_command == "validate":
        if not args.trials and not args.patients:
            print("prescreen validate: pass --trials and/or --patients", file=sys.stderr)
            return 2
        try:
            trials = load_recorded_studies(args.trials) if args.trials else []
            corpora = []
            if args.patients:
                if args.source == "pmc":
                    corpora = load_pmc_corpora(args.patients)
                else:
                    with Path(args.patients).open(encoding="utf-8") as handle:
                        corpora = [
                            corpus_from_dict(json.loads(line)) for line in handle if line.strip()
                        ]
        except (OSError, ValueError) as exc:
            print(f"prescreen validate failed: {exc}", file=sys.stderr)
            return 2
        report = report_for(trials=trials, corpora=corpora)
        text = json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"
        if args.out:
            Path(args.out).write_text(text)
        else:
            print(text, end="")
        print(
            f"checked {report.records_checked} records: "
            f"{report.error_count} errors, {report.warning_count} warnings",
            file=sys.stderr,
        )
        return 0 if report.ok else 7
    if args.prescreen_command == "show":
        try:
            trials = load_recorded_studies(args.fixtures)
        except (OSError, ValueError) as exc:
            print(f"prescreen show failed: {exc}", file=sys.stderr)
            return 2
        for trial in trials:
            age = trial.minimum_age.years
            print(
                f"{trial.trial_id}  [{trial.phase or '-'}] {trial.recruitment_status or '-'}  "
                f"min_age={age if age is not None else '-'}  {trial.title[:70]}"
            )
        return 0
    if args.prescreen_command == "export-explorer":
        try:
            written = write_explorer_json(
                args.out,
                fixtures_dir=args.fixtures_dir,
            )
        except (OSError, ValueError) as exc:
            print(f"prescreen export-explorer failed: {exc}", file=sys.stderr)
            return 2
        out_display = args.out or "explorer/public/data/prescreen"
        print(f"exported {len(written)} files to {out_display}: {', '.join(written)}")
        return 0
    if args.prescreen_command == "troubleshoot-agents":
        from clinique.prescreen.diagnostics import run_diagnostics

        return run_diagnostics()
    if args.prescreen_command == "agent-judge":
        try:
            if args.patients and args.source != "synthea":
                raise ValueError("--patients with --source other than synthea is not supported yet")
            trial, corpus = _load_screen_case(
                trials_path=args.trials,
                trial_id=args.trial_id,
                patient_id=args.patient_id,
                patients_path=args.patients,
                source=args.source,
                synthea_csv_dir=args.synthea_csv_dir if not args.patients else None,
                snapshot=args.snapshot,
            )
        except (OSError, ValueError) as exc:
            print(f"prescreen agent-judge failed: {exc}", file=sys.stderr)
            return 2

        from clinique.prescreen.judge import LLMJudge, codex_available, is_llm_agent_failure

        if not codex_available():
            print(
                "prescreen agent-judge: Codex CLI not available "
                "(install with: npm install -g @codex/cli; "
                "run prescreen troubleshoot-agents)",
                file=sys.stderr,
            )
            return 2

        judge = LLMJudge()
        criteria = ReferenceAtomizer().atomize(trial)
        if args.criterion_id:
            wanted = {item.strip() for item in args.criterion_id.split(",") if item.strip()}
            criteria = [c for c in criteria if c.criterion_id in wanted]
            if not criteria:
                print(
                    "prescreen agent-judge: no criteria matched "
                    f"--criterion-id {args.criterion_id!r}",
                    file=sys.stderr,
                )
                return 2
        if args.limit is not None and args.limit < 1:
            print("prescreen agent-judge: --limit must be >= 1", file=sys.stderr)
            return 2
        if not args.all:
            criteria = criteria[: args.limit]

        evidence_by_criterion = retrieve_for_criteria(criteria, corpus)
        results: list[dict[str, object]] = []
        failed = False
        for criterion in criteria:
            evidence = evidence_by_criterion[criterion.criterion_id]
            prompt = judge._build_prompt(criterion, evidence, corpus)
            if args.show_prompt:
                print(
                    f"--- prompt for {criterion.criterion_id} ---\n{prompt}\n",
                    file=sys.stderr,
                )
            judgment = judge.judge(criterion, evidence, corpus, prompt=prompt)
            if is_llm_agent_failure(judgment):
                failed = True
            entry: dict[str, object] = {
                "criterion": criterion.to_dict(),
                "judgment": judgment.to_dict(),
            }
            if args.show_evidence:
                entry["retrieved_evidence"] = [item.to_dict() for item in evidence]
            results.append(entry)

        payload = {
            "trial_id": trial.trial_id,
            "patient_id": corpus.patient_id,
            "snapshot_date": corpus.snapshot_date,
            "agent": "codex",
            "judge": {"name": judge.name, "version": judge.version},
            "results": results,
        }
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
        else:
            print(text, end="")

        if failed:
            print(
                "prescreen agent-judge: one or more criteria failed via Codex CLI",
                file=sys.stderr,
            )
            return 3
        return 0
    if args.prescreen_command == "resume":
        try:
            from temporalio.client import WorkflowFailureError

            from clinique.durable.cli_runtime import (
                connect_client,
                ensure_temporalio,
                temporal_import_error,
            )
        except ImportError as exc:
            return temporal_import_error(exc)
        ensure_temporalio()

        async def _run_resume() -> int:
            import shutil
            import subprocess

            client = await connect_client(args.host)
            handle = client.get_workflow_handle(args.workflow_id)
            try:
                desc = await handle.describe()
                status_str = desc.status.name
            except Exception as exc:
                print(
                    f"Could not find workflow execution {args.workflow_id}: {exc}",
                    file=sys.stderr,
                )
                return 2

            print(f"Workflow {args.workflow_id} status is {status_str}.", file=sys.stderr)

            if status_str == "RUNNING":
                print("Workflow is already running. Awaiting completion...", file=sys.stderr)
            elif status_str == "COMPLETED":
                print("Workflow is already completed successfully.", file=sys.stderr)
            else:
                print(
                    f"Workflow needs reset. Resetting workflow {args.workflow_id}...",
                    file=sys.stderr,
                )
                if not shutil.which("temporal"):
                    print(
                        "Error: 'temporal' CLI is required to reset workflow execution.",
                        file=sys.stderr,
                    )
                    return 2

                cmd = [
                    "temporal",
                    "workflow",
                    "reset",
                    "--workflow-id",
                    args.workflow_id,
                    "--reset-type",
                    "LastWorkflowTask",
                    "--reason",
                    "Resuming via clinique CLI",
                ]
                print(f"Executing: {' '.join(cmd)}", file=sys.stderr)
                res = subprocess.run(cmd, capture_output=True, text=True, check=False)
                if res.returncode != 0:
                    print(f"Reset failed: {res.stderr}", file=sys.stderr)
                    return 3
                print("Reset successful. Awaiting workflow completion...", file=sys.stderr)

            try:
                packet = await handle.result()
                from clinique.durable.models import PrescreeningPacketModel

                if isinstance(packet, PrescreeningPacketModel):
                    data = packet.model_dump()
                elif hasattr(packet, "to_dict"):
                    data = packet.to_dict()
                else:
                    data = packet
                print(json.dumps(data, indent=2, sort_keys=True) + "\n")
                return 0
            except WorkflowFailureError as exc:
                print(f"Workflow failed after resume: {exc.cause}", file=sys.stderr)
                return 3
            except Exception as exc:
                print(f"Error awaiting workflow result: {exc}", file=sys.stderr)
                return 3

        return asyncio.run(_run_resume())
    return None
