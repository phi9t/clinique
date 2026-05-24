"""Temporal data converter for prescreen Pydantic payloads."""

from __future__ import annotations

from temporalio.contrib.pydantic import pydantic_data_converter

DATA_CONVERTER = pydantic_data_converter

__all__ = ["DATA_CONVERTER"]
