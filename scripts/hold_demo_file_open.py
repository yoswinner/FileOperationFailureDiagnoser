#!/usr/bin/env python3
"""
Dedicated Lock-Holding Helper for Teacher Demonstrations.

Holds open an active handle on a managed fixture file so that the
File Operation Failure Diagnoser can detect it live via the Windows
Restart Manager API.

Safety:
    - Strictly operates ONLY on files inside 'artifacts/review3/demo_fixtures/teacher_demo/'.
    - Runs until Ctrl+C or until optional timeout expires.
    - Guarantees handle closure in finally block.
    - Never modifies or terminates other processes.
"""

import argparse
import os
import sys
import time

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, ".."))
_DEFAULT_DEMO_DIR = os.path.abspath(
    os.path.join(_PROJECT_ROOT, "artifacts", "review3", "demo_fixtures", "teacher_demo")
)
_DEFAULT_TARGET = os.path.join(_DEFAULT_DEMO_DIR, "05_locked_file.txt")


def validate_target_path(path: str) -> str:
    """Ensure target path is strictly within the managed teacher_demo directory."""
    abs_path = os.path.abspath(path)
    abs_demo_dir = os.path.abspath(_DEFAULT_DEMO_DIR)

    # Path safety validation
    if not abs_path.startswith(abs_demo_dir):
        raise ValueError(
            f"Security Violation: Target path '{abs_path}' is outside the managed "
            f"demo directory: '{abs_demo_dir}'"
        )
    return abs_path


def main():
    parser = argparse.ArgumentParser(
        description="Hold a demo fixture open to demonstrate live Restart Manager lock detection."
    )
    parser.add_argument(
        "--file",
        default=_DEFAULT_TARGET,
        help="Path to demo file (must be inside artifacts/review3/demo_fixtures/teacher_demo).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Timeout in seconds before automatically releasing handle (default: 300s).",
    )
    args = parser.parse_args()

    try:
        target_path = validate_target_path(args.file)
    except ValueError as exc:
        print(f"\n[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(target_path):
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write("Demo lock content.")

    current_pid = os.getpid()
    print("=" * 65)
    print(" File Operation Failure Diagnoser — Teacher Demo Lock Helper")
    print("=" * 65)
    print(f" Locking Process PID : {current_pid}")
    print(f" Executable Path     : {sys.executable}")
    print(f" Target Fixture      : {target_path}")
    print(f" Active Duration     : Up to {args.timeout} seconds (or press Ctrl+C to release)")
    print("=" * 65)
    print("\nInstructions for Teacher Demonstration:")
    print(" 1. Leave this window OPEN.")
    print(" 2. In the GUI, select the target file above.")
    print(" 3. Choose operation: WRITE.")
    print(" 4. Click 'Diagnose'.")
    print(f" 5. Observe status 'FILE_LOCKED' and process list showing PID {current_pid}.\n")

    handle = None
    try:
        handle = open(target_path, "r", encoding="utf-8", errors="replace")
        start_time = time.time()
        while time.time() - start_time < args.timeout:
            remaining = int(args.timeout - (time.time() - start_time))
            print(f"\r[LOCK ACTIVE] Holding open '{os.path.basename(target_path)}'... Auto-release in {remaining}s. Press Ctrl+C to stop.", end="", flush=True)
            time.sleep(1)
        print("\n\nTimeout reached. Releasing file handle.")
    except KeyboardInterrupt:
        print("\n\nKeyboardInterrupt received. Releasing file handle immediately.")
    finally:
        if handle:
            handle.close()
            print("[CLEANUP] File handle closed successfully. File is now unlocked.\n")


if __name__ == "__main__":
    main()
