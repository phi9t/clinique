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

### L0 infrastructure (addressed)

| Gap | Status | Notes |
|---|---|---|
| `verify-workstream --temporal` | done | sync `goal_complete` + temporal parity |
| Durable layer | done | 15 pytest; walkthrough in `temporal-prescreen.md` |
| Human-review workflow signal | deferred | Ledger writes `pending`; no Temporal wait on reviewer |
| Durable ingest/normalize workflows | deferred | CT.gov fetch still sync CLI |

### Phase 10+ — criteria-to-context matching (active)

Diagnosed on KEY-NOTE-189 (NCT02578680) + Synthea P1 (2026-05-24): 1/36 criteria resolved;
35 `unknown` with empty evidence. See `design.md` § Phase 10+.

| Gap | Severity | Phase | Notes |
|---|---|---|---|
| Atomizer substring domain bugs | **high** | 10 | I-002: `"age"` in `"stage"` → demographic → zero retrieval |
| Evidence discarded on `unknown` | **high** | 10 | Retrieval hits exist (E-001 NSCLC) but packet shows `evidence: []` |
| No domain-filtered retrieval | **high** | 10 | Metformin/ANC spurious hits for unrelated criteria |
| `RuleJudge` covers age/labs/anti-PD-1 only | **high** | 11–13 | No condition, therapy history, ECOG, or free-text rules |
| No oncology synonym expansion | medium | 11 | `NSCLC` vs `non-small cell lung cancer` — zero BM25 overlap |
| `l0_cases.jsonl` has 3 gold cases | medium | 10–11 | Expand for I-002, E-001, partial-match scenarios |
| Synthea P1 lacks staging/ECOG/notes | medium | 12 | 5 structured rows; narrative note doc would help retrieval |
| LLM judge + n2c2 L1 eval | medium | 13 | Real clinical matching signal; credentialed corpus |
| Embedding retriever | low | 13 | PMC-Patients free-text; deferred from L0 |

Design: [`docs/design/temporal-prescreen.md`](../../docs/design/temporal-prescreen.md)
Roadmap: [`.workstream/prescreen-copilot/design.md`](design.md) § Phase roadmap
Tracker: [`.workstream/prescreen-copilot/tracker.org`](tracker.org)
