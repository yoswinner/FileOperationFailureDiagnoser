# File Operation Failure Diagnoser

A Windows-focused desktop application that diagnoses why common file operations
(delete, rename, move, copy, modify) may fail.

## Project Overview

This tool helps users understand **why** a file operation failed by analysing:
- Process/file-lock detection (which process holds the file open)
- File system attributes and metadata
- Permission and ownership issues
- Synchronisation-related conflicts

It provides a **human-readable diagnosis** and **safe, actionable recommendations**
without automatically modifying the system.

## Target Platform
- Windows 10 / 11
- Development may occur on macOS; Windows-specific functionality requires a Windows VM for testing.

## Technology Stack
- Python 3.8+
- PyQt6 (GUI — future milestone)
- psutil (process information)
- ctypes / Windows Restart Manager API (file-lock detection)

## Project Structure

```
FileOperationFailureDiagnoser/
├── src/diagnoser/
│   ├── models.py                  # Shared data models
│   ├── analyzers/
│   │   ├── base.py                # Abstract analyzer interface
│   │   ├── process_lock.py        # Process/file-lock detection
│   │   ├── permissions.py         # (stub) Permission analysis
│   │   ├── file_attributes.py     # (stub) File attribute analysis
│   │   └── sync_conflict.py       # (stub) Sync conflict detection
│   ├── engine/
│   │   └── diagnosis.py           # (stub) Rule-based diagnosis engine
│   ├── recommendations/
│   │   └── recommender.py         # (stub) Safe recommendation generator
│   └── gui/
│       └── main_window.py         # (stub) PyQt6 GUI
├── tests/
│   ├── test_models.py             # Data model tests
│   └── test_process_lock.py       # Lock detection tests
├── scripts/
│   └── test_lock_demo.py          # Interactive demo script
└── requirements.txt
```

## Current Status — Milestone 2

✅ Project architecture  
✅ Process/file-lock detection module (Windows Restart Manager API)  
✅ Permission/ownership analysis (os.access + Windows advapi32.dll)  
⬜ File attribute analysis  
⬜ Synchronisation conflict detection  
⬜ Diagnosis engine  
⬜ Recommendations engine  
⬜ Desktop GUI  

## Setup

```bash
pip install -r requirements.txt
```

## Running Tests

```bash
python -m pytest tests/ -v
```

Note: Windows-specific lock detection tests are automatically skipped on non-Windows platforms.

## Safety Policy

This application **diagnoses only** — it does not:
- Terminate processes
- Modify permissions
- Take ownership of files
- Forcefully unlock files
