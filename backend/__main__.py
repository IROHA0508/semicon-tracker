"""Command line: python -m backend <command>

  update     collect + summarize + publish, then write the run report (what the workflow runs)
  collect    Walk the feeds and queue new articles in backend/state/queue.json
  summarize  Summarize queued articles (newest first, --limit at most) and rebuild the manifest
  publish    Rebuild data/manifest.json from data/news/*.json
  validate   Check data/ (tags, units, article files, manifest); exit 1 on any problem
  detect     Walk the feeds and print what would be queued, without changing any file
  selftest   Read page 1 of every source and check it still parses and carries article text
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys

from . import collect, config, publish, store


def _summarize(limit: int | None) -> dict:
    from . import digest

    return digest.run(limit=limit)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m backend", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["update", "collect", "summarize", "publish", "validate",
                                            "detect", "selftest"])
    parser.add_argument("--limit", type=int, default=None,
                        help=f"articles to summarize in this run (default {config.SUMMARY_LIMIT})")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")

    if args.command == "selftest":
        return 0 if collect.selftest(notice=os.environ.get("GITHUB_ACTIONS") == "true") else 1
    if args.command == "validate":
        problems = publish.validate()
        for p in problems:
            print(f"::error title=데이터 점검::{p}" if os.environ.get("GITHUB_ACTIONS") == "true" else f"FAIL {p}")
        print(f"{len(problems)} problems")
        return 1 if problems else 0
    if args.command == "publish":
        print(json.dumps(publish.build(), ensure_ascii=False))
        return 0
    if args.command == "detect":
        print(json.dumps(collect.run(dry_run=True), ensure_ascii=False, indent=2))
        return 0
    if args.command == "collect":
        print(json.dumps(collect.run(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "update":
        report = collect.run(save_report=False)
    else:  # summarize only: keep the latest collect report and replace its summary part
        report = json.loads(config.REPORT_FILE.read_text(encoding="utf-8")) if config.REPORT_FILE.exists() else {}
    report["summary"] = _summarize(args.limit)
    report["manifest"] = publish.build()
    store.save_report(report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    # Failed sources and articles are retried on the next run, so the command still succeeds and the
    # workflow commits what was done. The workflow then fails on collect errors or an auth error.
    return 0


if __name__ == "__main__":
    sys.exit(main())
