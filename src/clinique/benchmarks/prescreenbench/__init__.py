"""PrescreenBench — an agent benchmark for evidence-grounded clinical-trial prescreening.

Given a trial eligibility section and a patient record snapshot, an agent must produce a structured
prescreening packet (atomic criteria, criterion-level labels, evidence quotes, conservative overall
recommendation). The benchmark is **decoupled**: an agent emits a ``predictions.jsonl`` artifact and
a standalone scorer grades that file against gold labels — so any agent (a one-shot LLM, the
clinique pipeline, a competitor) is scored by identical code.

See ``benchmarks/prescreenbench/README.md`` and ``DATASET_CARD.md`` for the dataset, splits, and the
headline score definition.
"""

BENCHMARK_ID = "prescreenbench_v0"
SPLITS = ("synthetic", "lite")
TASKS = ("end_to_end_packet", "criterion_judgment")
