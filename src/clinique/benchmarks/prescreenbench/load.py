"""Load a PrescreenBench split from disk into typed records.

A split directory (``benchmarks/prescreenbench/data/<split>/``) holds four JSONL files:
``trials.jsonl`` (recorded ClinicalTrials.gov payloads), ``patients.jsonl`` (normalized
``PatientCorpus`` dicts — uniform across sources), ``cases.jsonl`` (:class:`BenchmarkCase`), and
``labels.jsonl`` (:class:`GoldLabel`). Patients are stored pre-normalized so the loader never needs
source-specific parsers — the source survives on ``corpus.source`` and the case binding.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from clinique.prescreen.explorer_export import find_repo_root
from clinique.prescreen.ingestion import load_recorded_studies
from clinique.prescreen.schemas import PatientCorpus, Trial
from clinique.prescreen.validation import corpus_from_dict

from .schema import BenchmarkCase, GoldLabel


def split_dir(split: str, *, base: str | Path | None = None) -> Path:
    """Resolve ``benchmarks/prescreenbench/data/<split>/`` (repo-relative unless ``base`` given)."""
    if base is not None:
        return Path(base) / split
    for candidate_root in (
        find_repo_root(),
        Path(__file__).resolve().parents[4] / "benchmarks" / "prescreenbench",
    ):
        candidate = candidate_root / "data" / split
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(
        f"split directory not found for {split}; tried repo-relative and package fallback"
    )


def _read_jsonl(path: str | Path) -> list[dict]:
    rows: list[dict] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_cases(path: str | Path) -> list[BenchmarkCase]:
    return [BenchmarkCase.from_dict(r) for r in _read_jsonl(path)]


def load_gold(path: str | Path) -> dict[str, GoldLabel]:
    return {r["case_id"]: GoldLabel.from_dict(r) for r in _read_jsonl(path)}


def load_corpora(path: str | Path) -> list[PatientCorpus]:
    return [corpus_from_dict(r) for r in _read_jsonl(path)]


@dataclass(frozen=True)
class SplitData:
    """Everything the scorer needs for one split, indexed for O(1) case lookup."""

    split: str
    cases: tuple[BenchmarkCase, ...]
    gold: dict[str, GoldLabel]
    trials_by_id: dict[str, Trial]
    corpora_by_id: dict[str, PatientCorpus]


def load_split(split: str, *, base: str | Path | None = None) -> SplitData:
    directory = split_dir(split, base=base)
    if not directory.is_dir():
        raise FileNotFoundError(f"split directory not found: {directory}")
    trials = load_recorded_studies(directory / "trials.jsonl")
    corpora = load_corpora(directory / "patients.jsonl")
    cases = load_cases(directory / "cases.jsonl")
    gold_path = directory / "labels.jsonl"
    gold = load_gold(gold_path) if gold_path.is_file() else {}
    return SplitData(
        split=split,
        cases=tuple(cases),
        gold=gold,
        trials_by_id={t.trial_id: t for t in trials},
        corpora_by_id={c.patient_id: c for c in corpora},
    )
