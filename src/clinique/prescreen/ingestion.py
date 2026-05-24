"""ClinicalTrials.gov v2 ingestion + a JSONL fixture recorder.

Public, ungated data source: the ClinicalTrials.gov REST API needs no key or DUA. The design
deliberately splits *fetching* (network, non-deterministic, rate-limited) from *parsing* (pure,
deterministic). For ML workflows this matters: you fetch once, **record** the raw payloads to a
versioned JSONL fixture, then run all training/eval/tests against that frozen snapshot. That gives
reproducibility (the live API mutates as trials update) and offline CI, mirroring the repo's
record-and-replay posture for EDC data.

JSONL layout: one raw API single-study payload (``{"protocolSection": {...}}``) per line. Each line
round-trips through ``Trial.from_api``.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from collections.abc import Iterable, Iterator
from pathlib import Path

from .schemas import Trial

API_BASE = "https://clinicaltrials.gov/api/v2/studies"

# Only the modules the parser consumes — keeps recorded fixtures small and stable.
DEFAULT_FIELDS = (
    "protocolSection.identificationModule",
    "protocolSection.statusModule",
    "protocolSection.conditionsModule",
    "protocolSection.designModule",
    "protocolSection.eligibilityModule",
    "protocolSection.sponsorCollaboratorsModule",
)


def fetch_study_raw(
    nct_id: str, *, timeout: float = 30.0, fields: Iterable[str] = DEFAULT_FIELDS
) -> dict:
    """Fetch one study's raw API payload (network). Not used by tests — see ``parse_study``."""
    query = urllib.parse.urlencode({"fields": ",".join(fields)})
    url = f"{API_BASE}/{urllib.parse.quote(nct_id)}?{query}"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (https only)
        payload = json.loads(response.read().decode("utf-8"))
    if "protocolSection" not in payload:
        raise ValueError(f"unexpected API payload for {nct_id}: no protocolSection")
    return payload


def parse_study(raw: dict) -> Trial:
    """Pure parse of a raw API payload into a ``Trial``. Deterministic; offline-testable."""
    return Trial.from_api(raw)


def fetch_study(nct_id: str, **kwargs) -> Trial:
    """Convenience: fetch + parse one study (network)."""
    return parse_study(fetch_study_raw(nct_id, **kwargs))


def record_studies(
    nct_ids: Iterable[str], out_path: str | Path, *, fields: Iterable[str] = DEFAULT_FIELDS
) -> list[str]:
    """Fetch each study and append its raw payload as one JSONL line. Returns recorded NCT ids.

    This is how the offline fixture corpus is built. Re-recording overwrites the file so the
    snapshot is explicit and reviewable in version control.
    """
    field_list = tuple(fields)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    recorded: list[str] = []
    with out.open("w", encoding="utf-8") as handle:
        for nct_id in nct_ids:
            payload = fetch_study_raw(nct_id, fields=field_list)
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
            recorded.append(payload["protocolSection"]["identificationModule"]["nctId"])
    return recorded


def iter_raw_studies(path: str | Path) -> Iterator[dict]:
    """Yield raw payloads from a recorded JSONL corpus (offline)."""
    with Path(path).open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{Path(path).name}:{line_no} is not valid JSON: {exc}") from exc


def load_recorded_studies(path: str | Path) -> list[Trial]:
    """Parse a recorded JSONL corpus into ``Trial`` records (offline, deterministic)."""
    return [parse_study(raw) for raw in iter_raw_studies(path)]
