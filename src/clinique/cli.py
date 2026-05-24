"""Minimal CLI entry point."""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    _ = argv if argv is not None else sys.argv[1:]
    print("clinique — biostatistician agent suite.")
    print("Design: docs/rfcs/  |  Workstream: .workstreams/biostat-agent-suite/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
