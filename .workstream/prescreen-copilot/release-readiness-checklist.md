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

Verification record (2026-05-25, Phases 12–14):

```bash
uv run pytest -q
# 310 passed, 4 skipped
uv run clinique prescreen verify-workstream --workstream .workstream/prescreen-copilot
# goal_complete=True criterion_accuracy=1.000
uv run clinique prescreen troubleshoot-agents
# codex CLI: READY
```

Report: `reports/prescreen/workstream-verification.json`

## Durable execution (Temporal.io)

Separate from `goal_complete` — does not require scale datasets in CI; proven by pytest + optional
prospective `eval-temporal` on scale corpus.

- [x] `clinique/durable/` wraps copilot graph (Pydantic payloads, parallel criteria, batch eval)
- [x] `uv run pytest tests/test_durable_models.py tests/test_durable_prescreen.py tests/test_durable_prescreen_e2e.py -q` passes
- [x] Walkthrough for ML researchers / MLsys in `docs/design/temporal-prescreen.md`
- [x] `prescreen verify-workstream --temporal` runs eval-temporal and checks sync parity
- [x] `tests/test_durable_resume.py` — LLM failure retry + resume CLI
- [ ] Optional: prospective `prescreen verify-workstream --temporal` on scale corpus with live worker (manual)

Quick durable smoke:

```bash
uv sync --group temporal
uv run pytest tests/test_durable_prescreen.py tests/test_durable_prescreen_e2e.py -q
```

## Phase 10+ — Criteria-to-context matching

L0 `goal_complete` proves plumbing; this phase proves **coordinator utility** on real criteria.
Tracker: `.workstream/prescreen-copilot/tracker.org`

### Tier 0 — Atomizer & retrieval (Phase 10)

- [x] Word-boundary domain classifier (fix I-002 `stage`→`age` misclassification)
- [x] Attach retrieved evidence to `unknown` judgments in packet output
- [x] Domain-filtered retrieval (clinical_domain ↔ doc source_type)
- [x] Min BM25 score threshold (drop spurious metformin/ANC hits)
- [x] Expanded `l0_cases.jsonl` + pytest regressions for P1 NSCLC criteria

### Tier 1 — Structured matching (Phase 11)

- [x] Oncology synonym map (`vocab.py`)
- [x] Condition / diagnosis matcher with partial-match rationales
- [x] Medication history matcher (prior systemic therapy)
- [x] ECOG / performance status matcher
- [x] Absence exclusion handling (explicit negative evidence only)
- [x] Gold eval ≥ 0.90 on expanded cases

### Tier 2 — Retrieval upgrade (Phase 12)

- [x] Query expansion from criterion metadata
- [x] Structured-first routing (code lookup before BM25)
- [x] Compound criterion splitting
- [x] Synthea narrative `note` document in normalizer

### Tier 3 — LLM judge & L1 (Phase 13)

- [x] `LLMJudge` behind `Judge` Protocol (Codex CLI)
- [x] `--judge rule|llm` CLI flag
- [x] n2c2 2018 judge-only harness (F1 ≥ 0.80)
- [x] Embedding retriever for PMC-Patients notes

### Phase 14 — Temporal resume & LLM judge durability

- [x] Judge option propagated through batch eval workflows
- [x] Retryable `ApplicationError` when LLM judge fails all channels
- [x] `prescreen resume --workflow-id` CLI command
- [x] `tests/test_durable_resume.py` integration coverage

### Phase 10 smoke (KEY-NOTE P1)

```bash
uv run clinique prescreen screen \
  --trial-id NCT02578680 --patient-id P1 \
  --trials tests/fixtures/prescreen/trials.jsonl \
  --patients /tmp/synthea_patients.jsonl
```

Pass when: I-002 and E-001 include NSCLC condition quote; no junk hits on medication criteria;
every criterion with retrieval hits shows evidence in output.
