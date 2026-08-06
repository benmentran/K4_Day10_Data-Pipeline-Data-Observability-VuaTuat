from __future__ import annotations

import argparse

from pipelines.corruption_flow import main


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Corrupt, repair and compare the three pipeline states.")
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Rebuild data/reports/corruption_report.md from existing artifacts without re-evaluating.",
    )
    main(report_only=parser.parse_args().report_only)
