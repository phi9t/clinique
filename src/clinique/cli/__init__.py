"""CLI entry point."""

from __future__ import annotations

import sys

from clinique.cli.benchmark import handle_benchmark
from clinique.cli.edc import handle_edc
from clinique.cli.parser import build_parser
from clinique.cli.prescreen import handle_prescreen


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv if argv is not None else sys.argv[1:])
    for handler in (handle_edc, handle_prescreen, handle_benchmark):
        code = handler(args)
        if code is not None:
            return code
    print("clinique — biostatistician agent suite.")
    print("Design: docs/design/  |  Index: docs/README.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
