"""Artifact graph + finding model (RFC-0001 §4/§5.5).

The graph is a read-only normalized view over a trial's statistical artifacts. It has no API to
mutate source artifacts — the checker only ever *reports* (RFC-0001 §3, read-only invariant).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class TLFShell:
    shell_id: str
    title: str
    sap_section: str
    backing_derivation_ids: tuple[str, ...]


@dataclass(frozen=True)
class Derivation:
    derivation_id: str
    target_var: str
    is_primary: bool = False


@dataclass(frozen=True)
class ArtifactGraph:
    """Normalized, read-only bundle. Keys of the dicts are artifact ids (protocol/sap/adam/...)."""

    # artifact -> {endpoint_name: timepoint_weeks}
    endpoints: dict[str, dict[str, float]] = field(default_factory=dict)
    # artifact -> {population_name: definition_text}
    populations: dict[str, dict[str, str]] = field(default_factory=dict)
    shells: tuple[TLFShell, ...] = ()
    derivations: tuple[Derivation, ...] = ()

    def with_changes(self, **kw) -> ArtifactGraph:
        """Return a NEW graph with changes (used by seed mutators). Never mutates in place."""
        return replace(self, **kw)


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str  # blocker | major | minor | info
    estimand_attribute: str
    artifacts_involved: tuple[str, ...]
    explanation: str
    suggested_resolution: str
    evidence: tuple[dict[str, str], ...] = ()
    confidence: float = 1.0
    needs_human_review: bool = True

    @property
    def finding_id(self) -> str:
        seed = f"{self.rule_id}|{','.join(sorted(self.artifacts_involved))}|{self.explanation}"
        return hashlib.sha256(seed.encode()).hexdigest()[:16]
