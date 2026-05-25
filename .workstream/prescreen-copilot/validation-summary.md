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

## Full pytest evidence (2026-05-25)

```bash
uv sync --group temporal
uv run pytest -q
# 310 passed, 4 skipped in ~29s
```

Phase 12–14 focused modules:

```bash
uv run pytest tests/test_prescreen_splitting.py tests/test_prescreen_embedding.py \
  tests/test_prescreen_llm_judge.py tests/test_n2c2_harness.py \
  tests/test_durable_resume.py -q
```

Optional live LLM judge (host must have Codex CLI):

```bash
CLINIQUE_LIVE_LLM=1 uv run pytest tests/test_prescreen_llm_judge_live.py -q
```

Agent diagnostics:

```bash
uv run clinique prescreen troubleshoot-agents
# codex CLI; Codex-only LLM judge
```

## Durable pytest evidence

```bash
uv sync --group temporal
uv run pytest tests/test_durable_models.py tests/test_durable_prescreen.py \
  tests/test_durable_prescreen_e2e.py tests/test_durable_resume.py -q
```

Temporal workstream gate:

```bash
uv run clinique prescreen verify-workstream --workstream .workstream/prescreen-copilot --temporal
```
