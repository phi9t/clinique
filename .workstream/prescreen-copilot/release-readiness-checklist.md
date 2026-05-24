# Prescreen Copilot — Release Readiness

## Sync copilot (goal_complete)

- [x] Scale corpus recorded under `~/.clinique/datasets/prescreen-copilot/`
- [x] `prescreen validate` passes on full corpus (0 errors)
- [x] `prescreen eval` passes on `l0_cases.jsonl` (accuracy ≥ 0.90)
- [x] `prescreen verify-workstream` reports `goal_complete: true`
- [x] Prescreen pytest modules pass
- [x] `validation-summary.md` updated with evidence paths

Verification record (2026-05-24):

```bash
uv run clinique prescreen verify-workstream --workstream .workstream/prescreen-copilot
# goal_complete=True criterion_accuracy=1.000
```

Report: `reports/prescreen/workstream-verification.json`

## Durable execution (Temporal.io)

Separate from `goal_complete` — does not require scale datasets in CI; proven by pytest + optional
prospective `eval-temporal` on scale corpus.

- [x] `clinique/durable/` wraps copilot graph (Pydantic payloads, parallel criteria, batch eval)
- [x] `uv run pytest tests/test_durable_models.py tests/test_durable_prescreen.py tests/test_durable_prescreen_e2e.py -q` passes
- [x] Walkthrough for ML researchers / MLsys in `docs/design/temporal-prescreen.md`
- [ ] Optional: `prescreen eval-temporal` on scale corpus → `l0-eval-temporal.json` (prospective; needs running worker)
- [ ] Optional: wire `eval-temporal` into `verify-workstream --temporal` (not implemented — sync oracle stays canonical for `goal_complete`)

Quick durable smoke:

```bash
uv sync --group temporal
uv run pytest tests/test_durable_prescreen.py tests/test_durable_prescreen_e2e.py -q
```
