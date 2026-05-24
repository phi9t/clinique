"""Deterministic consistency rules (RFC-0001 §5.4).

Each rule is a pure function ArtifactGraph -> list[Finding]. Deterministic rules carry
confidence 1.0. (LLM semantic-diff rules are a separate, advisory layer added later.)
"""

from __future__ import annotations

from .graph import ArtifactGraph, Finding


def est_timepoint_align(g: ArtifactGraph) -> list[Finding]:
    """Primary endpoint timepoint must be identical across every artifact that declares it."""
    findings: list[Finding] = []
    # collect {endpoint -> {artifact: timepoint}}
    by_endpoint: dict[str, dict[str, float]] = {}
    for artifact, eps in g.endpoints.items():
        for name, tp in eps.items():
            by_endpoint.setdefault(name, {})[artifact] = tp
    for name, per_artifact in by_endpoint.items():
        distinct = set(per_artifact.values())
        if len(distinct) > 1:
            findings.append(
                Finding(
                    rule_id="EST-TIMEPOINT-ALIGN",
                    severity="major",
                    estimand_attribute="endpoint_variable",
                    artifacts_involved=tuple(sorted(per_artifact)),
                    explanation=(
                        f"Endpoint '{name}' has conflicting timepoints across artifacts: "
                        + ", ".join(f"{a}={per_artifact[a]}wk" for a in sorted(per_artifact))
                    ),
                    suggested_resolution=f"Align the '{name}' timepoint across protocol, SAP, ADaM, and shells.",
                    evidence=tuple(
                        {"artifact": a, "timepoint_weeks": str(per_artifact[a])}
                        for a in sorted(per_artifact)
                    ),
                )
            )
    return findings


def pop_def_consistent(g: ArtifactGraph) -> list[Finding]:
    """Analysis-population definitions must agree across artifacts that define them."""
    findings: list[Finding] = []
    by_pop: dict[str, dict[str, str]] = {}
    for artifact, pops in g.populations.items():
        for name, definition in pops.items():
            by_pop.setdefault(name, {})[artifact] = definition.strip().lower()
    for name, per_artifact in by_pop.items():
        if len(set(per_artifact.values())) > 1:
            findings.append(
                Finding(
                    rule_id="POP-DEF-CONSISTENT",
                    severity="major",
                    estimand_attribute="population",
                    artifacts_involved=tuple(sorted(per_artifact)),
                    explanation=f"Analysis population '{name}' is defined inconsistently across artifacts.",
                    suggested_resolution=f"Reconcile the '{name}' population definition to a single wording.",
                    evidence=tuple(
                        {"artifact": a, "definition": per_artifact[a]} for a in sorted(per_artifact)
                    ),
                )
            )
    return findings


def shell_backed(g: ArtifactGraph) -> list[Finding]:
    """Every shell must reference existing derivations; every primary derivation needs a shell."""
    findings: list[Finding] = []
    deriv_ids = {d.derivation_id for d in g.derivations}
    referenced: set[str] = set()
    for shell in g.shells:
        referenced.update(shell.backing_derivation_ids)
        missing = [d for d in shell.backing_derivation_ids if d not in deriv_ids]
        if missing:
            findings.append(
                Finding(
                    rule_id="SHELL-BACKED",
                    severity="blocker",
                    estimand_attribute="endpoint_variable",
                    artifacts_involved=("tlf_shells", "adam_spec"),
                    explanation=f"Shell '{shell.shell_id}' references missing derivation(s): {', '.join(missing)}.",
                    suggested_resolution="Add the missing derivation(s) to the ADaM spec or fix the shell reference.",
                    evidence=({"artifact": "tlf_shells", "shell": shell.shell_id},),
                )
            )
    for d in g.derivations:
        if d.is_primary and d.derivation_id not in referenced:
            findings.append(
                Finding(
                    rule_id="SHELL-BACKED",
                    severity="major",
                    estimand_attribute="endpoint_variable",
                    artifacts_involved=("adam_spec", "tlf_shells"),
                    explanation=f"Primary derivation '{d.derivation_id}' ({d.target_var}) has no backing shell.",
                    suggested_resolution="Add a TLF shell for the primary derivation or demote it.",
                    evidence=({"artifact": "adam_spec", "derivation": d.derivation_id},),
                )
            )
    return findings


ALL_RULES = (est_timepoint_align, pop_def_consistent, shell_backed)
