"""Command line: python -m backend {collect,detect,selftest}

  collect   Walk the feeds, queue new articles in backend/state/queue.json and write the run report.
  detect    Same walk, but print what would be queued without changing any file.
  selftest  Read page 1 of every source and check it still parses (no files written).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys

from . import collect


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m backend", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["collect", "detect", "selftest"])
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")

    if args.command == "selftest":
        return 0 if collect.selftest() else 1

    report = collect.run(dry_run=args.command == "detect")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    # A failed source is retried on the next run, so the command still succeeds and the workflow
    # can commit what was collected. The workflow fails afterwards when report["errors"] is not empty.
    return 0


if __name__ == "__main__":
    sys.exit(main())
