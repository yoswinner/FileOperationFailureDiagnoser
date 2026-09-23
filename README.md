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
- Tkinter (desktop GUI — bundled with Python)
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
│   │   ├── permissions.py         # Permission/ownership analysis
│   │   ├── file_attributes.py     # (stub) File attribute analysis
│   │   └── sync_conflict.py       # (stub) Sync conflict detection
│   ├── engine/
│   │   └── diagnosis.py           # Rule-based diagnosis engine
│   ├── recommendations/
│   │   └── recommender.py         # (stub) Safe recommendation generator
│   └── gui/
│       ├── app.py                 # Application entry point
│       └── main_window.py         # Tkinter desktop GUI
├── tests/
│   ├── test_models.py             # Data model tests
│   ├── test_process_lock.py       # Lock detection tests
│   ├── test_permissions.py        # Permission analysis tests
│   └── test_diagnoser.py          # Diagnosis engine tests
├── scripts/
│   └── test_lock_demo.py          # Interactive demo script
└── requirements.txt
```

## Current Status

✅ Process/file-lock detection module (Windows Restart Manager API)
✅ Permission/ownership analysis (os.access + Windows advapi32.dll)
✅ Diagnosis engine (rule-based, deterministic)
✅ Desktop GUI (Tkinter — first functional prototype)
⬜ File attribute analysis
⬜ Synchronisation conflict detection
⬜ Advanced recommendation engine

## Launching the GUI

From the project root directory:

```bash
# Windows (with project venv)
.\venv\Scripts\Python.exe -m diagnoser.gui.app

# macOS / Linux
python -m diagnoser.gui.app
```

The GUI connects directly to the existing `DiagnosisEngine` backend.
All results shown are real — there is no mock data.

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
