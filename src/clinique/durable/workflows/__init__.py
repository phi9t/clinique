"""Temporal workflow definitions."""

from __future__ import annotations

from clinique.durable.workflows.eval import BatchEvalWorkflow
from clinique.durable.workflows.prescreen import ScreenPatientWorkflow

ALL_WORKFLOWS = [ScreenPatientWorkflow, BatchEvalWorkflow]

__all__ = ["ALL_WORKFLOWS", "BatchEvalWorkflow", "ScreenPatientWorkflow"]
