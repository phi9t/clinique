# Prescreen Copilot Validation Summary

## Sync verification (`goal_complete`)

- goal_complete: **True**
- corpus_conformance_ok: True
- atomizer_coverage: 1.000
- criterion_accuracy: 1.000
- evidence_violations: 0
- exclusion_false_negatives: 0
- scale_smoke_ok: True
- determinism_ok: True

Full report: `reports/prescreen/workstream-verification.json`

Re-run:

```bash
uv run clinique prescreen verify-workstream --workstream .workstream/prescreen-copilot
```

## Durable verification (Temporal.io)

Not part of `goal_complete` today — sync orchestrator remains the release oracle. Durable layer
verified independently:

| Check | Status | Evidence |
|---|---|---|
| Pydantic wire round-trip | pass | `tests/test_durable_models.py` (4 tests) |
| Workflow ↔ sync parity | pass | `test_screen_workflow_matches_sync_orchestrator` |
| Determinism under Temporal | pass | `test_screen_workflow_is_deterministic` |
| Transient retry + gate failure | pass | `tests/test_durable_prescreen_e2e.py` |
| Real dev server E2E | pass | session fixtures, ~17s suite |
| **Total durable tests** | **15 passed** | last run 2026-05-24 |

```bash
uv sync --group temporal
uv run pytest tests/test_durable_models.py tests/test_durable_prescreen.py tests/test_durable_prescreen_e2e.py -q
```

Prospective scale check (optional, needs worker + scale datasets):

```bash
uv run clinique prescreen eval-temporal \
  --cases .workstream/prescreen-copilot/l0_cases.jsonl \
  --trials ~/.clinique/datasets/prescreen-copilot/trials.jsonl \
  --synthea-patients ~/.clinique/datasets/prescreen-copilot/synthea_patients.jsonl \
  --reports-dir reports/prescreen
```

## Known gaps / follow-ups

| Gap | Severity | Notes |
|---|---|---|
| `l0_cases.jsonl` has 3 gold cases | low | Enough for CI gate; expand for richer criterion coverage |
| `verify-workstream` is sync-only | intentional | Adding `--temporal` would couple release to running cluster |
| No committed `l0-eval-temporal.json` | low | Generated on demand; sync `l0-eval.json` in reports is canonical |
| Human-review workflow signal | deferred | Ledger writes `pending`; no Temporal wait on reviewer |
| Durable ingest/normalize workflows | deferred | CT.gov fetch still sync CLI |

Design: [`docs/design/temporal-prescreen.md`](../../docs/design/temporal-prescreen.md)
