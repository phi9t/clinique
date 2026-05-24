# EDC Query Validation Access Boundary

## Allowed

- Read PHI-free synthetic fixtures from `tests/fixtures/edc_query/`.
- Read approved internal EDC exports only after owner approval and privacy review.
- Preflight an internal data manifest without reading PHI-bearing exports.
- Produce local validation reports under `reports/edc-query/`.
- Generate draft candidate queries for evaluation.
- Record provenance for snapshot ids, rule ids, replay timestamps, and reviewer state.

## Prohibited

- Writing to EDC or any validated system of record.
- Closing, issuing, modifying, or suppressing live queries.
- Editing subject data.
- Accessing treatment assignment or unblinded data.
- Using future snapshots or future query resolutions as agent input during replay.
- Treating synthetic validation as evidence of production workflow impact.

## Boundary Gate

Every implementation artifact must preserve draft-only behavior. Any new API with names or
effects resembling `write`, `update`, `delete`, `issue_query`, or `close_query` must be reviewed
as a potential boundary violation.

Run the internal-data preflight before connecting approved exports:

```bash
uv run clinique edc-query preflight-internal-data --manifest <approved-manifest.json>
```
