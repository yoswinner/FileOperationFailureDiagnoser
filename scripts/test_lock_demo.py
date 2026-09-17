#!/usr/bin/env python3
"""
Interactive demo script for the File Operation Failure Diagnoser.

This script demonstrates:
  Part A — Lock Detection (Milestone 1)
    1. Nonexistent file
    2. Unlocked file
    3. File held open (lock simulation)
    4. File released

  Part B — Permission Analysis (Milestone 2)
    5. Read permission on a normal file
    6. Write permission on a read-only file
    7. All permission bits summary

Run:
    cd FileOperationFailureDiagnoser
    PYTHONPATH=src python scripts/test_lock_demo.py

On macOS/Linux, lock detection returns 'unsupported_platform'.
On Windows, the Restart Manager detects locks and advapi32.dll
resolves NTFS owners.
"""

import os
import stat
import sys
import tempfile

# Ensure the src directory is on the import path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from diagnoser.analyzers.process_lock import ProcessLockAnalyzer
from diagnoser.analyzers.permissions import PermissionAnalyzer
from diagnoser.models import FileOperation, LockDetectionResult, PermissionCheckResult


def print_lock_result(label: str, result: LockDetectionResult) -> None:
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


def print_perm_result(label: str, result: PermissionCheckResult) -> None:
    """Pretty-print a PermissionCheckResult."""
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}")
    print(f"  File path        : {result.file_path}")
    print(f"  Operation        : {result.operation}")
    print(f"  Permitted        : {result.permitted}")
    print(f"  Owner            : {result.owner or '(unknown)'}")
    print(f"  Current user     : {result.current_user}")
    print(f"  Detection method : {result.detection_method}")

    if result.error:
        print(f"  Error            : {result.error}")

    if result.permission_bits:
        bits = ", ".join(
            f"{k}={'yes' if v else 'no'}"
            for k, v in sorted(result.permission_bits.items())
        )
        print(f"  Permission bits  : {bits}")

    if result.details:
        print(f"  Details:")
        for line in result.details.split("\n"):
            print(f"    {line}")

    print()


def main():
    lock_analyzer = ProcessLockAnalyzer()
    perm_analyzer = PermissionAnalyzer()

    print("\n" + "=" * 60)
    print("  PART A: Lock Detection (Milestone 1)")
    print("=" * 60)

    # --- Lock Test 1: Nonexistent file ---
    print_lock_result(
        "Test 1: Nonexistent file",
        lock_analyzer.analyze("/nonexistent/path/file.txt"),
    )

    # --- Lock Test 2-4: Lock lifecycle ---
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=".txt", mode="w"
    ) as f:
        temp_path = f.name
        f.write("Hello, this is a test file.\n")

    try:
        print_lock_result(
            "Test 2: Unlocked file",
            lock_analyzer.analyze(temp_path),
        )

        print("Holding file open to simulate a lock...")
        with open(temp_path, "r") as locked_handle:
            print_lock_result(
                "Test 3: File held open by this process",
                lock_analyzer.analyze(temp_path),
            )

        print_lock_result(
            "Test 4: File released (should be unlocked)",
            lock_analyzer.analyze(temp_path),
        )
    finally:
        os.unlink(temp_path)
        print("Temporary lock-test file cleaned up.")

    print("\n" + "=" * 60)
    print("  PART B: Permission Analysis (Milestone 2)")
    print("=" * 60)

    # --- Perm Test 5: Read permission on a normal file ---
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=".txt", mode="w"
    ) as f:
        perm_temp = f.name
        f.write("Permission test content.\n")

    try:
        print_perm_result(
            "Test 5: READ permission (normal file)",
            perm_analyzer.analyze(perm_temp, FileOperation.READ),
        )

        # --- Perm Test 6: Write permission on a read-only file ---
        os.chmod(perm_temp, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        print_perm_result(
            "Test 6: WRITE permission (read-only file)",
            perm_analyzer.analyze(perm_temp, FileOperation.WRITE),
        )

        # --- Perm Test 7: All operations summary ---
        os.chmod(perm_temp, stat.S_IRUSR | stat.S_IWUSR)
        print("Test 7: All operations on a normal file:")
        for op in FileOperation:
            result = perm_analyzer.analyze(perm_temp, op)
            status = "GRANTED" if result.permitted else "DENIED"
            print(f"  {op.value.upper():>8}: {status}")
        print()

    finally:
        # Ensure writable for cleanup
        try:
            os.chmod(perm_temp, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
        os.unlink(perm_temp)
        print("Temporary permission-test file cleaned up.")

    # --- Perm Test 8: Nonexistent file ---
    print_perm_result(
        "Test 8: Permission check on nonexistent file",
        perm_analyzer.analyze("/nonexistent/file.txt", FileOperation.WRITE),
    )


if __name__ == "__main__":
    main()
