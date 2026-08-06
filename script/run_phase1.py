from __future__ import annotations

import argparse

from pipelines.phase1 import main


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the clean baseline, evaluate it and report on it.")
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Rebuild data/reports/phase1_report.md from existing artifacts without re-evaluating.",
    )
    main(report_only=parser.parse_args().report_only)
