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


def parse_search_page(raw: dict) -> list[dict]:
    """Pure extraction of the per-study payloads from a v2 search-response page.

    The search endpoint wraps results as ``{"studies": [{"protocolSection": {...}}, ...],
    "nextPageToken": ...}``. Each element is exactly the shape ``parse_study`` consumes, so search
    is just another way to populate the same ``Trial`` corpus. Offline-testable.
    """
    studies = raw.get("studies")
    if studies is None:
        raise ValueError("search payload is missing 'studies' (not a v2 search response?)")
    return list(studies)


def search_studies_raw(
    *,
    cond: str | None = None,
    term: str | None = None,
    status: str | Iterable[str] | None = None,
    page_size: int = 100,
    max_studies: int | None = None,
    fields: Iterable[str] = DEFAULT_FIELDS,
    timeout: float = 30.0,
) -> Iterator[dict]:
    """Yield per-study raw payloads matching a search query, following pagination (network).

    Drives the v2 ``/studies`` search endpoint with ``query.cond`` / ``query.term`` /
    ``filter.overallStatus`` and follows ``nextPageToken`` until the results are exhausted or
    ``max_studies`` payloads have been yielded. Like ``fetch_study_raw`` this is not exercised by
    tests; ``parse_search_page`` is the pure, offline-tested half.

    Refuses an unbounded sweep: at least one of ``cond`` / ``term`` / ``status`` or an explicit
    ``max_studies`` is required, so a bare call cannot accidentally page the whole registry.
    """
    if not (cond or term or status) and max_studies is None:
        raise ValueError(
            "refusing an unbounded search of the full registry: pass a query "
            "(cond/term/status) or set max_studies"
        )
    if max_studies is not None:
        page_size = min(page_size, max_studies)
    base_params: list[tuple[str, str]] = [
        ("fields", ",".join(fields)),
        ("pageSize", str(page_size)),
        ("countTotal", "true"),
    ]
    if cond:
        base_params.append(("query.cond", cond))
    if term:
        base_params.append(("query.term", term))
    if status:
        statuses = [status] if isinstance(status, str) else list(status)
        base_params.append(("filter.overallStatus", ",".join(statuses)))

    yielded = 0
    page_token: str | None = None
    while True:
        params = list(base_params)
        if page_token:
            params.append(("pageToken", page_token))
        url = f"{API_BASE}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (https)
            payload = json.loads(response.read().decode("utf-8"))
        for study in parse_search_page(payload):
            yield study
            yielded += 1
            if max_studies is not None and yielded >= max_studies:
                return
        page_token = payload.get("nextPageToken")
        if not page_token:
            return


def record_search(out_path: str | Path, **search_kwargs) -> list[str]:
    """Run a search and append each matched study as one JSONL line. Returns recorded NCT ids.

    Writes the same one-study-per-line format as ``record_studies`` so the resulting corpus loads
    uniformly through ``load_recorded_studies``. Re-recording overwrites the file.
    """
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    recorded: list[str] = []
    with out.open("w", encoding="utf-8") as handle:
        for payload in search_studies_raw(**search_kwargs):
            if "protocolSection" not in payload:
                raise ValueError("search study payload has no protocolSection")
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
