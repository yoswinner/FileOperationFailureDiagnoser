#!/usr/bin/env python3
"""
Interactive demo script for the Process Lock Analyzer.

This script demonstrates the lock detection workflow:
  1. Creates a temporary file
  2. Analyses it while unlocked
  3. Holds it open and re-analyses (Windows-only: detects the lock)
  4. Releases it and confirms the lock is cleared

Run:
    cd FileOperationFailureDiagnoser
    python -m scripts.test_lock_demo

Or directly:
    python scripts/test_lock_demo.py

On macOS/Linux, lock detection returns 'unsupported_platform'.
On Windows, the Restart Manager detects the lock and reports the process.
"""

import os
import sys
import tempfile

# Ensure the src directory is on the import path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from diagnoser.analyzers.process_lock import ProcessLockAnalyzer
from diagnoser.models import LockDetectionResult


def print_result(label: str, result: LockDetectionResult) -> None:
    """Pretty-print a LockDetectionResult."""
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}")
    print(f"  File path        : {result.file_path}")
    print(f"  Is locked        : {result.is_locked}")
    print(f"  Detection method : {result.detection_method}")

    if result.error:
        print(f"  Error            : {result.error}")

    if result.processes:
        print(f"  Locking processes: {len(result.processes)}")
        for i, proc in enumerate(result.processes, 1):
            print(f"    [{i}] {proc.process_name}")
            print(f"        PID : {proc.pid}")
            print(f"        Path: {proc.executable_path or '(unknown)'}")
    else:
        print(f"  Locking processes: (none)")

    print()


def main():
    analyzer = ProcessLockAnalyzer()

    # --- Test 1: Nonexistent file ---
    print_result(
        "Test 1: Nonexistent file",
        analyzer.analyze("/nonexistent/path/file.txt"),
    )

    # --- Test 2: Unlocked file ---
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=".txt", mode="w"
    ) as f:
        temp_path = f.name
        f.write("Hello, this is a test file.\n")

    try:
        print_result(
            "Test 2: Unlocked file",
            analyzer.analyze(temp_path),
        )

        # --- Test 3: File held open (lock simulation) ---
        print("Holding file open to simulate a lock...")
        with open(temp_path, "r") as locked_handle:
            print_result(
                "Test 3: File held open by this process",
                analyzer.analyze(temp_path),
            )

        # --- Test 4: File released ---
        print_result(
            "Test 4: File released (should be unlocked)",
            analyzer.analyze(temp_path),
        )

    finally:
        os.unlink(temp_path)
        print("Temporary file cleaned up.")


if __name__ == "__main__":
    main()
