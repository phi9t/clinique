# Controlled Draft-Only Rollout Gate

## Entry Criteria

- Internal L1 offline and L2 retrospective reports meet predefined thresholds.
- Silent prospective run completes without stop criteria.
- False and duplicate query burden are acceptable to data-management reviewers.
- Every candidate query is evidence-backed and draft-only.

## Design Options

Randomize by study, site, form family, or data-manager queue. Gate manifests must encode this as
`study`, `site`, `form_family`, or `data_manager_queue`. Use the smallest unit that avoids
operational contamination while preserving staffing practicality.

## Primary Endpoints

- Manual minutes per accepted query.
- True discrepancies found.
- False query rate.
- Duplicate query rate.
- Query resolution time.
- Open queries at database lock.
- Data-manager acceptance rate.

## Safety Endpoints

Unauthorized write-back, unsupported evidence citation, privacy incident, blinding breach, and
excessive reviewer burden.

## Rollback Criteria

Rollback immediately for any boundary violation, privacy incident, blinding concern, or sustained
false-query burden above the predefined tolerance.

## Executable Gate Evaluation

Use the structured gate evaluator before any draft-only rollout decision:

```bash
uv run clinique edc-query evaluate-rollout-gate \
  --gate tests/fixtures/edc_query/controlled_rollout_gate.json \
  --output reports/edc-query/controlled-rollout-gate.json
```

The evaluator checks primary endpoint thresholds, safety endpoints, and the human approval path.
It returns a nonzero exit code when the gate fails. The bundled fixture is synthetic and verifies
the gate mechanics; it is not evidence that a live rollout is approved.
