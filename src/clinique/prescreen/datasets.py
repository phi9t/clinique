"""Dataset path resolution for prescreen workstream corpora."""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_DATASETS_ROOT = Path.home() / ".clinique" / "datasets"
DEFAULT_MANIFEST = Path(".workstream/prescreen-copilot/datasets.manifest.json")


def datasets_root(override: str | Path | None = None) -> Path:
    if override is not None:
        return Path(override).expanduser()
    env = os.environ.get("CLINIQUE_DATASETS_DIR")
    if env:
        return Path(env).expanduser()
    return DEFAULT_DATASETS_ROOT


def load_manifest(path: str | Path | None = None) -> dict:
    manifest_path = Path(path or DEFAULT_MANIFEST)
    if not manifest_path.is_file():
        raise FileNotFoundError(f"datasets manifest not found: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def resolve_dataset_path(
    logical_name: str,
    *,
    datasets_dir: str | Path | None = None,
    manifest_path: str | Path | None = None,
) -> Path:
    manifest = load_manifest(manifest_path)
    rel = manifest.get("files", {}).get(logical_name)
    if not rel:
        raise KeyError(f"unknown dataset logical name: {logical_name!r}")
    return datasets_root(datasets_dir) / rel


def resolve_all_datasets(
    *,
    datasets_dir: str | Path | None = None,
    manifest_path: str | Path | None = None,
) -> dict[str, Path]:
    manifest = load_manifest(manifest_path)
    root = datasets_root(datasets_dir)
    return {name: root / rel for name, rel in manifest.get("files", {}).items()}


def ensure_datasets_present(
    *,
    datasets_dir: str | Path | None = None,
    manifest_path: str | Path | None = None,
) -> list[str]:
    """Return list of missing logical dataset names."""
    missing: list[str] = []
    for name, path in resolve_all_datasets(
        datasets_dir=datasets_dir, manifest_path=manifest_path
    ).items():
        if not path.is_file():
            missing.append(name)
    return missing
