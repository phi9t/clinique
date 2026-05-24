"""Seeded-defect fixtures (RFC-0001 §8 validation).

A consistent synthetic matched bundle plus mutators that each inject exactly one inconsistency.
This is the pre-partner validation path: it proves the rules *work* (recall on seeded defects,
zero false positives on the clean bundle) before any proprietary trial data is involved. The
public matched bundles (CDISC Pilot, R-submission pilots) plug in at the same interface later.
"""

from __future__ import annotations

from .graph import ArtifactGraph, Derivation, TLFShell

_ITT = "all randomized participants analyzed as randomized"
_SAFETY = "all participants who received at least one dose"


def consistent_bundle() -> ArtifactGraph:
    """A fully self-consistent protocol/SAP/ADaM/shells bundle (zero findings expected)."""
    endpoints = {
        "protocol": {"primary": 12.0, "key_secondary": 24.0},
        "sap": {"primary": 12.0, "key_secondary": 24.0},
        "adam_spec": {"primary": 12.0, "key_secondary": 24.0},
    }
    populations = {
        "protocol": {"ITT": _ITT, "Safety": _SAFETY},
        "sap": {"ITT": _ITT, "Safety": _SAFETY},
        "adam_spec": {"ITT": _ITT, "Safety": _SAFETY},
    }
    derivations = (
        Derivation("D-PRIM", "CHG_WK12", is_primary=True),
        Derivation("D-SEC", "CHG_WK24", is_primary=False),
    )
    shells = (
        TLFShell("T-14.2.1", "Primary endpoint at Week 12", "SAP 9.1", ("D-PRIM",)),
        TLFShell("T-14.2.2", "Key secondary at Week 24", "SAP 9.2", ("D-SEC",)),
    )
    return ArtifactGraph(endpoints=endpoints, populations=populations, shells=shells, derivations=derivations)


def mutate_timepoint(g: ArtifactGraph) -> ArtifactGraph:
    """Seed an EST-TIMEPOINT-ALIGN defect: ADaM collects the primary endpoint at Week 8."""
    endpoints = {a: dict(eps) for a, eps in g.endpoints.items()}
    endpoints["adam_spec"]["primary"] = 8.0
    return g.with_changes(endpoints=endpoints)


def mutate_population(g: ArtifactGraph) -> ArtifactGraph:
    """Seed a POP-DEF-CONSISTENT defect: SAP redefines ITT."""
    populations = {a: dict(pops) for a, pops in g.populations.items()}
    populations["sap"]["ITT"] = "all randomized participants who received at least one dose"
    return g.with_changes(populations=populations)


def mutate_unbacked_shell(g: ArtifactGraph) -> ArtifactGraph:
    """Seed a SHELL-BACKED defect: a shell references a non-existent derivation."""
    shells = (*g.shells, TLFShell("T-14.3.1", "Exploratory", "SAP 9.3", ("D-MISSING",)))
    return g.with_changes(shells=shells)
