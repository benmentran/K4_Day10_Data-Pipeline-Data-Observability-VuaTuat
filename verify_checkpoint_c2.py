"""Script to verify Checkpoint C2 - Frozen Evaluation Set."""
import json
import os
import sys
from pathlib import Path

# Fix Unicode output on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Define paths - use current working directory as project root
PROJECT_ROOT = Path.cwd()
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
CLEAN_DIR = DATA_DIR / "clean"
EVAL_DIR = DATA_DIR / "eval"


def check_file_exists(path: Path, description: str) -> bool:
    """Check if file exists and print status."""
    exists = path.exists()
    status = "[OK]" if exists else "[FAIL]"
    print(f"  {status} {description}: {path}")
    if exists:
        size = path.stat().st_size
        print(f"      Size: {size:,} bytes")
    return exists


def main():
    print("=" * 60)
    print("CHECKPOINT C2 - Pha 1a: Du lieu sach & Bo test")
    print("=" * 60)

    all_passed = True

    # Check data/raw/
    print("\n[1] Checking data/raw/ directory:")
    raw_files = [
        (RAW_DIR / "crossref_response.json", "Raw API response"),
        (RAW_DIR / "crossref_records.json", "Raw records"),
    ]
    for path, desc in raw_files:
        if not check_file_exists(path, desc):
            all_passed = False

    # Check data/clean/
    print("\n[2] Checking data/clean/ directory:")
    clean_files = [
        (CLEAN_DIR / "papers_clean.csv", "Cleaned CSV"),
        (CLEAN_DIR / "papers_clean.json", "Cleaned JSON"),
    ]
    for path, desc in clean_files:
        if not check_file_exists(path, desc):
            all_passed = False

    # Check data/eval/
    print("\n[3] Checking data/eval/ directory:")
    eval_files = [
        (EVAL_DIR / "test_set.json", "Evaluation test set"),
    ]
    for path, desc in eval_files:
        if not check_file_exists(path, desc):
            all_passed = False

    # Validate test_set.json schema
    print("\n[4] Validating test_set.json schema:")
    test_set_path = EVAL_DIR / "test_set.json"
    if test_set_path.exists():
        with open(test_set_path, "r", encoding="utf-8") as f:
            test_set = json.load(f)

        required_fields = ["id", "question_type", "question", "ground_truth", "ground_truth_doc_ids"]
        print(f"  Total questions: {len(test_set)}")

        for i, q in enumerate(test_set):
            missing = [f for f in required_fields if f not in q]
            if missing:
                print(f"  [FAIL] Question {q.get('id', i+1)} missing fields: {missing}")
                all_passed = False
            else:
                print(f"  [OK] {q['id']}: {q['question'][:50]}...")

        # Check if at least 5 questions
        if len(test_set) < 5:
            print(f"  [FAIL] Need at least 5 questions, got {len(test_set)}")
            all_passed = False
    else:
        print("  [FAIL] test_set.json not found")
        all_passed = False

    # Summary
    print("\n" + "=" * 60)
    if all_passed:
        print("[OK] CHECKPOINT C2 VERIFIED - All files present and valid")
    else:
        print("[FAIL] CHECKPOINT C2 FAILED - Some files missing")
    print("=" * 60)

    return all_passed


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
