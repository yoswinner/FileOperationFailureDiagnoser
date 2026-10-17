# Review 3 Engineering Log: File Operation Failure Diagnoser

This document serves as the living engineering record and architectural reference for **Review 3** of the Operating Systems Lab mini-project: **File Operation Failure Diagnoser**. It maintains requirements traceability, technical specifications, test matrices, and implementation milestones.

---

## 1. Project Overview and Final Scope

### 1.1 Problem Statement and Review 1 Objectives
In multi-tasking operating systems such as Windows, users and applications frequently encounter silent or generic file-operation failures (e.g. `Access Denied`, `File in Use`, `Sharing Violation`). Traditional error reporting fails to differentiate whether a failure stems from:
1. An active file handle held by another process.
2. Inadequate user permissions or missing NTFS discretionary access controls.
3. Restrictive filesystem attributes (e.g. read-only, hidden, or system flags).
4. Cloud-synchronization background daemons (OneDrive, Google Drive) locking or offloading files.

The **File Operation Failure Diagnoser** provides a non-invasive, explanatory diagnostic tool that inspects the underlying operating system state and translates low-level kernel and filesystem telemetry into human-understandable root-cause diagnoses and actionable recommendations.

### 1.2 Four-Peer-Analyzer Architecture
The system employs a modular architecture featuring four decoupled, peer analyzers coordinated by an orchestrating Diagnosis Engine:
1. **Process Lock Analyzer (`ProcessLockAnalyzer`)**: Detects active file locks and identifies holding processes via the native Windows Restart Manager API (`rstrtmgr.dll`).
2. **Permission Analyzer (`PermissionAnalyzer`)**: Checks user access rights against file operations (`READ`, `WRITE`, `EXECUTE`, `DELETE`) and determines file ownership.
3. **File Attribute Analyzer (`FileAttributeAnalyzer`)**: Evaluates filesystem metadata flags (`READONLY`, `HIDDEN`, `SYSTEM`, `ARCHIVE`, `REPARSE_POINT`, `OFFLINE`).
4. **Cloud-Sync Conflict Analyzer (`SyncConflictAnalyzer`)**: Discovers local cloud synchronization folder roots (OneDrive, Google Drive), client processes, and placeholder contention.

```
                              +------------------------+
                              |      GUI / CLI         |
                              +-----------+------------+
                                          |
                                          v
                              +------------------------+
                              |    Diagnosis Engine    |
                              +-----------+------------+
                                          |
         +-------------------+------------+------------+--------------------+
         |                   |                         |                    |
         v                   v                         v                    v
+-----------------+ +-----------------+       +-----------------+  +-----------------+
|   ProcessLock   | |   Permission    |       |  FileAttribute  |  |  SyncConflict   |
|    Analyzer     | |    Analyzer     |       |    Analyzer     |  |    Analyzer     |
+--------+--------+ +--------+--------+       +--------+--------+  +--------+--------+
         |                   |                         |                    |
         +-------------------+------------+------------+--------------------+
                                          | (Structured Dataclass Results)
                                          v
                              +------------------------+
                              |  Recommender Module    |
                              +-----------+------------+
                                          |
                                          v
                              +------------------------+
                              |    DiagnosisResult     |
                              +------------------------+
```

### 1.3 Read-Only Diagnostic Safety Policy
The diagnoser is strictly read-only and non-destructive:
- **No Process Termination**: It never kills, suspends, or injects into running processes.
- **No File Mutation**: It never deletes, modifies, unlinks, or alters file contents or timestamps.
- **No Attribute/Permission Changes**: It never modifies DACLs, ownership, or attribute bits.
- **No Registry/Cloud Mutation**: It reads local registry keys and environment variables without modifying them.

### 1.4 Supported Four-Operation Model
The system analyzes operations against four explicit file operation verbs:
- `READ`: Opening and retrieving file data.
- `WRITE`: Modifying or appending file content.
- `EXECUTE`: Launching executable binaries or scripts.
- `DELETE`: Removing directory entries and unlinking files.

---

## 2. Architecture and Design Decisions

### 2.1 Component Responsibilities
- **GUI Layer (`src/diagnoser/gui/`)**: Built on Tkinter / ttk; presents a clean, responsive interface displaying primary diagnosis, holding processes, permission tables, attribute flags, and sync provider status.
- **Diagnosis Engine (`src/diagnoser/engine/`)**: Orchestrates peer analyzers, applies deterministic priority classification, attaches raw evidence from all four peers, and produces a consolidated `DiagnosisResult`.
- **Recommender (`src/diagnoser/recommendations/`)**: Translates structured technical findings into non-destructive, context-aware remediation steps.

### 2.2 Decision Priority Order
When multiple failure conditions coexist on a single file, the Diagnosis Engine resolves them deterministically:
1. `FILE_NOT_FOUND`: Highest priority; if the file path is nonexistent, deeper analysis cannot proceed.
2. `SYNC_CONFLICT`: Confirmed lock held specifically by a supported cloud-sync daemon (OneDrive, Google Drive) via lock correlation.
3. `FILE_LOCKED`: Confirmed active process lock held by an ordinary application (e.g. Word, Excel, Notepad).
4. `READ_ONLY`: If a write/delete operation fails due to the `FILE_ATTRIBUTE_READONLY` flag.
5. `PERMISSION_DENIED`: If the user lacks filesystem access rights and no higher-priority blocker explains it.
6. `OPERATION_ALLOWED`: If all diagnostic checks pass without detecting blockers.
7. `UNKNOWN_ERROR`: Critical inspection failure or directory target.

### 2.3 Approved Design Choices
1. **Conservative Evidence Policy for Cloud Sync**:
   A running sync client (`OneDrive.exe`, `GoogleDriveFS.exe`) is **never** treated as definitive proof of a file lock. Evidence is strictly tiered:
   - `none`: File is not associated with any detected sync root.
   - `path_only`: File is within a sync root, but sync client is not running and no placeholder flags exist.
   - `potential_contention`: Sync client is running, or file has cloud placeholder/reparse attributes.
   - `confirmed_lock`: Lock correlation proves that a supported sync client process holds the handle.
2. **Directory-Boundary Path Matching**:
   Path matching enforces directory boundaries and Windows case-insensitivity (`is_subpath`) to prevent false matches against sibling directories (e.g. `OneDriveBackup` vs `OneDrive`).
3. **Decoupled Analyzers**:
   Analyzers do not instantiate or depend on one another. Lock correlation is handled via a dedicated, testable correlation contract (`correlate_sync_lock`).
4. **All-Peer Structured Attachment**:
   Every valid diagnosed file retains structured findings from all four peer analyzers attached to `DiagnosisResult` (`lock_result`, `permission_result`, `attribute_result`, `sync_result`), ensuring the GUI and caller have complete access to both primary and secondary evidence.

---

## 3. Implementation Timeline

### Sprint 1: Data Models + File Attribute Analyzer + Recommender
- **Scope**: Extended structured dataclasses, implemented `FileAttributeAnalyzer`, implemented standalone `Recommender`, and wrote full unit test suites.
- **Files Modified / Created**:
  - `src/diagnoser/models.py`
  - `src/diagnoser/analyzers/file_attributes.py`
  - `src/diagnoser/recommendations/recommender.py`
  - `tests/test_models.py`
  - `tests/test_file_attributes.py`
  - `tests/test_recommender.py`
- **Test Baseline**: 104 collected tests: **103 passed, 1 skipped, 0 failed** (Windows).
- **Git Commit**: `87be4bc` (`feat: add file attribute analyzer and recommender`).

### Sprint 2: Cloud-Sync Analyzer + Correlation Helper + Tests + Documentation
- **Scope**: Replaced stub in `src/diagnoser/analyzers/sync_conflict.py` with full local discovery for OneDrive and Google Drive; created `correlate_sync_lock` helper; added 20 comprehensive unit tests; established living engineering log.
- **Files Modified / Created**:
  - `src/diagnoser/analyzers/sync_conflict.py`
  - `tests/test_sync_conflict.py`
  - `docs/REVIEW3_ENGINEERING_LOG.md`
- **Test Result**: 124 collected tests: **123 passed, 1 skipped, 0 failed** (Windows).
- **Git Commit**: `57cfd56` (`feat: add OneDrive and Google Drive sync diagnostics`).

### Sprint 3: Diagnosis Engine Integration + Four-Analyzer Correlation + Recommendations
- **Scope**: Refactored `DiagnosisEngine` in `src/diagnoser/engine/diagnosis.py` to orchestrate all four peer analyzers (`ProcessLockAnalyzer`, `PermissionAnalyzer`, `FileAttributeAnalyzer`, `SyncConflictAnalyzer`), implement deterministic priority ranking, preserve secondary findings, represent inspection failures honestly, and integrate the standalone `Recommender`. Added 15 new integration tests in `tests/test_diagnoser.py`.
- **Files Modified / Created**:
  - `src/diagnoser/engine/diagnosis.py`
  - `src/diagnoser/recommendations/recommender.py`
  - `tests/test_diagnoser.py`
  - `docs/REVIEW3_ENGINEERING_LOG.md`
- **Test Result**: 139 collected tests: **138 passed, 1 skipped, 0 failed** (Windows).
- **Outstanding Sprints**:
  - Sprint 4: GUI Wiring + Result Display for Attributes & Sync.
  - Sprint 5: Final Review 3 Verification, Documentation, and Packaging.

---

## 4. Technical Implementation and APIs

### 4.1 Modules and Classes
- **`DiagnosisEngine` (`src/diagnoser/engine/diagnosis.py`)**:
  - Orchestrates execution across all four peer analyzers.
  - Defensive execution wrappers (`_safe_analyze_lock`, `_safe_analyze_perm`, `_safe_analyze_attr`, `_safe_analyze_sync`) isolate analyzer exceptions into structured error results.
  - Correlates sync conflict results with lock results via `correlate_sync_lock`.
  - Determines primary root-cause classification according to deterministic priority order.
  - Generates secondary context notes appended to `result.reason`.
  - Attaches `suggested_action` produced by `Recommender.recommend(result)`.
- **`FileAttributeAnalyzer` (`src/diagnoser/analyzers/file_attributes.py`)**:
  - Extracts attributes via Python's `os.stat().st_file_attributes` on Windows.
  - Native Win32 fallback via `ctypes.windll.kernel32.GetFileAttributesW`.
  - POSIX stat fallback for portable development and testing.
- **`SyncConflictAnalyzer` (`src/diagnoser/analyzers/sync_conflict.py`)**:
  - Bounded sync root discovery for OneDrive and Google Drive for desktop.
  - Safe process inspection via `psutil.process_iter` with defensive exception handling (`NoSuchProcess`, `AccessDenied`, `ZombieProcess`).
  - Detection of cloud placeholder attributes (`FILE_ATTRIBUTE_REPARSE_POINT`, `FILE_ATTRIBUTE_OFFLINE`).
- **`Recommender` (`src/diagnoser/recommendations/recommender.py`)**:
  - Produces advisory, non-destructive recommendations based on `DiagnosisResult` context.

### 4.2 Windows APIs and System Libraries Genuinely Used
1. **Windows Restart Manager (`rstrtmgr.dll`)**:
   - `RmStartSession`: Initializes Restart Manager diagnostic session.
   - `RmRegisterResources`: Registers target file path for handle querying.
   - `RmGetList`: Enumerates processes currently holding active handles on the file.
   - `RmEndSession`: Cleans up session resources.
   - *Reference*: [Restart Manager Portal (Microsoft Learn)](https://learn.microsoft.com/en-us/windows/win32/rstrtmgr/restart-manager-portal)
2. **File Attribute APIs (`kernel32.dll`)**:
   - `GetFileAttributesW`: Retrieves raw Win32 DWORD attribute bitmask.
   - *Reference*: [GetFileAttributesW (Microsoft Learn)](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfileattributesw)
   - *Reference*: [File Attribute Constants (Microsoft Learn)](https://learn.microsoft.com/en-us/windows/win32/fileio/file-attribute-constants)
3. **Volume and Mount Discovery (`kernel32.dll` / `psutil`)**:
   - `GetVolumeInformationW`: Inspects volume label and filesystem name for mounted drives (e.g. DriveFS).
   - *Reference*: [GetVolumeInformationW (Microsoft Learn)](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getvolumeinformationw)
4. **Windows Registry (`winreg`)**:
   - `HKCU\Software\Microsoft\OneDrive\Accounts\*` (`UserFolder`): Discovers personal/business OneDrive paths.
   - `HKCU\Software\Microsoft\OneDrive` (`UserFolder`): Discovers standard OneDrive root.
   - `HKCU\Software\Google\DriveFS` and `HKLM\Software\Google\DriveFS` (`MountPoint`, `DefaultMountPoint`): Discovers Google Drive virtual drive or mirror mount.
5. **Windows Cloud Files API Constants**:
   - `FILE_ATTRIBUTE_REPARSE_POINT` (`0x00000400`)
   - `FILE_ATTRIBUTE_OFFLINE` (`0x00001000`)
   - `FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS` (`0x00400000`)
   - *Reference*: [Cloud Filter API (Microsoft Learn)](https://learn.microsoft.com/en-us/windows/win32/cfapi/build-a-cloud-file-sync-engine)

---

## 5. Test Matrix and Execution Log

### 5.1 Historical Test Baselines
- **Review 2 Baseline**: 72 collected, 71 passed, 0 failed, 1 skipped.
- **Sprint 1 Execution**: 104 collected, 103 passed, 0 failed, 1 skipped.
- **Sprint 2 Execution**: 124 collected, 123 passed, 0 failed, 1 skipped.
- **Sprint 3 Execution**: 139 collected, 138 passed, 0 failed, 1 skipped.
  - Command: `$env:PYTHONDONTWRITEBYTECODE = "1"; .\venv\Scripts\python.exe -B -m pytest -p no:cacheprovider -v`
  - Platform: Windows (win32), Python 3.13.14.

### 5.2 Scenario Verification Matrix

| Scenario / Test Case | Implemented | Automated Test Location | Windows Live Verified | Status |
| :--- | :--- | :--- | :--- | :--- |
| Nonexistent file skips checks | Yes | `tests/test_diagnoser.py::test_nonexistent_file_skips_downstream_checks` | Yes | Verified |
| All 4 peer analyzers invoked | Yes | `tests/test_diagnoser.py::test_all_four_analyzers_invoked_and_results_attached` | Yes | Verified |
| All 4 structured results attached | Yes | `tests/test_diagnoser.py::test_all_four_analyzers_invoked_and_results_attached` | Yes | Verified |
| Genuine non-sync application lock | Yes | `tests/test_diagnoser.py::test_genuine_non_sync_application_lock_returns_file_locked` | Yes | Verified |
| Confirmed OneDrive lock | Yes | `tests/test_diagnoser.py::test_confirmed_onedrive_lock_returns_sync_conflict` | Yes | Verified |
| Confirmed Google Drive lock | Yes | `tests/test_diagnoser.py::test_confirmed_google_drive_lock_returns_sync_conflict` | Yes | Verified |
| Sync folder without lock | Yes | `tests/test_diagnoser.py::test_sync_folder_path_only_does_not_falsely_return_sync_conflict` | Yes | Verified |
| Read-only blocks WRITE and DELETE | Yes | `tests/test_diagnoser.py::test_readonly_attribute_blocks_write_and_delete` | Yes | Verified |
| Read-only does not block READ | Yes | `tests/test_diagnoser.py::test_readonly_attribute_does_not_block_read` | Yes | Verified |
| Separate permission restriction | Yes | `tests/test_diagnoser.py::test_separate_permission_restriction_returns_permission_denied` | Yes | Verified |
| Accessible file OPERATION_ALLOWED | Yes | `tests/test_diagnoser.py::test_readable_file_read_allowed` | Yes | Verified |
| Multiple findings preserve all evidence | Yes | `tests/test_diagnoser.py::test_multiple_simultaneous_findings_preserve_all_evidence` | Yes | Verified |
| Analyzer exception isolation | Yes | `tests/test_diagnoser.py::test_analyzer_exception_isolated_and_converted_to_error_result` | Yes | Verified |
| Honest analyzer error representation | Yes | `tests/test_diagnoser.py::test_critical_analyzer_error_represented_honestly` | Yes | Verified |
| Recommender called and integrated | Yes | `tests/test_diagnoser.py::test_recommender_integrated_and_called_consistently` | Yes | Verified |
| Injected analyzer instances used | Yes | `tests/test_diagnoser.py::test_injected_analyzers_used_exactly` | Yes | Verified |
| Directory targets handled | Yes | `tests/test_diagnoser.py::test_directory_target_handling` | Yes | Verified |
| Live Windows Restart Manager Lock | Yes | `tests/test_diagnoser.py::test_locked_file_detected_windows` | Yes | Verified |
| Live Windows Attribute Inspection | Yes | `tests/test_file_attributes.py::test_live_windows_file_attributes` | Yes | Verified |
| Live Windows Sync Discovery | Yes | `tests/test_sync_conflict.py::test_live_onedrive_roots_discovery` | Yes | Verified |

---

## 6. Known Limitations and Unverified Behavior

1. **Undetected Custom Sync Locations**:
   If a user configures OneDrive or Google Drive to sync to an arbitrary non-standard directory without populating standard registry keys or environment variables, discovery will report `none`.
2. **Third-Party Sync Providers**:
   Third-party cloud sync providers other than OneDrive and Google Drive are explicitly excluded from scope per the approved requirements.
3. **No Private Cloud APIs**:
   The diagnoser does not communicate with Microsoft or Google cloud telemetry servers or evaluate online cloud sync queues. Contention is evaluated strictly via local OS evidence.
4. **NTFS DACL Parsing vs `os.access`**:
   The `PermissionAnalyzer` evaluates permissions using `os.access()` combined with Windows file ownership queries; full NTFS DACL inheritance trees are not parsed.
5. **GUI Wiring Scheduled**:
   The `DiagnosisEngine` coordinates all four peer analyzers, but GUI panels for File Attributes and Cloud Sync remain to be connected in Sprint 4.

---

## 7. Review 3 Demonstration Plan

| Scenario | Expected Diagnostic Output | Status |
| :--- | :--- | :--- |
| **Accessible Normal File** | `OPERATION_ALLOWED`: No locking, attribute, or permission blockers. | Automated & Manual Verified |
| **Nonexistent File** | `FILE_NOT_FOUND`: Structured error instructing user to check path. | Automated & Manual Verified |
| **Active Process Lock** | `FILE_LOCKED`: Holding process name and PID identified via Restart Manager. | Automated & Manual Verified |
| **Read-Only Attribute** | `READ_ONLY`: Detected via `FileAttributeAnalyzer`; recommender advises attribute clearance. | Automated & Manual Verified |
| **Permission Denied** | `PERMISSION_DENIED`: Owner reported; recommender advises NTFS security dialog. | Automated Verified |
| **OneDrive Sync Contention** | `SYNC_CONFLICT`: OneDrive root recognized, client identified, placeholder flags reported. | Automated Verified |
| **Google Drive Virtual Mount** | `SYNC_CONFLICT`: Virtual drive / mount point discovered. | Automated Verified |
| **Multiple Coexisting Findings** | Deterministic priority resolution (`FILE_LOCKED` takes precedence over attributes/sync). | Automated Verified |
| **Analyzer Error / Permission Denied** | Graceful fallback returning structured error result without application crash. | Automated Verified |

---

## 8. Automated GUI Demonstration and Screenshot Plan

The final visual evidence phase is scheduled for execution following the completion of GUI wiring in Sprint 4. The planned demonstration portfolio consists of verified scenarios captured on Windows 11:
1. **Scenario 1 — Baseline Accessible File**: `OPERATION_ALLOWED` with all four panels populated (no lock, permissions granted, standard attributes, non-sync directory).
2. **Scenario 2 — Missing Target File**: `FILE_NOT_FOUND` with clean error notification and user guidance.
3. **Scenario 3 — Real Active Process Lock**: `FILE_LOCKED` displaying locking process name, PID, executable path, and close recommendation.
4. **Scenario 4 — Read-Only Attribute Restriction**: `READ_ONLY` displaying active `READONLY` bit in attribute panel and advisory to uncheck in Properties.
5. **Scenario 5 — Permission Denial**: `PERMISSION_DENIED` displaying unresolved access rights, file owner, and administrator delegation guidance.
6. **Scenario 6 — Cloud Sync Conflict / Association**: `SYNC_CONFLICT` or `potential_contention` displaying detected OneDrive / Google Drive root and daemon status.
7. **Scenario 7 — Multiple Simultaneous Findings**: Primary diagnosis resolved by priority order with secondary evidence visible in supporting panels.

*Note: Visual capture will be performed strictly against real GUI execution in Sprint 5. No simulated screenshots are generated prematurely.*

---

## 9. Final Acceptance Checklist

- [x] Sprint 1: Data Models extended (`FileAttributeResult`, `SyncConflictResult`, `DiagnosisType.SYNC_CONFLICT`).
- [x] Sprint 1: `FileAttributeAnalyzer` implemented and unit tested (12 tests).
- [x] Sprint 1: `Recommender` implemented and unit tested (15 tests).
- [x] Sprint 2: `SyncConflictAnalyzer` implemented for OneDrive & Google Drive.
- [x] Sprint 2: Conservative evidence tiers implemented (`none`, `path_only`, `potential_contention`, `confirmed_lock`).
- [x] Sprint 2: `correlate_sync_lock` helper implemented and verified.
- [x] Sprint 2: 20 unit tests created in `tests/test_sync_conflict.py`.
- [x] Sprint 2: Full regression suite passing (124 collected, 123 passed, 1 skipped).
- [x] Sprint 2: Living Review 3 Engineering Log created (`docs/REVIEW3_ENGINEERING_LOG.md`).
- [x] Sprint 3: `DiagnosisEngine` updated to coordinate all four peer analyzers.
- [x] Sprint 3: Recommender integrated for all diagnostic outcomes.
- [x] Sprint 3: Deterministic priority rules implemented and verified.
- [x] Sprint 3: 15 new integration tests added to `tests/test_diagnoser.py` (total 139 collected: 138 passed, 1 skipped).
- [ ] Sprint 4: GUI updated to display File Attributes and Cloud Sync panels with real data.
- [ ] Sprint 5: Final Review 3 report and presentation materials finalized.

---

## 10. Change Log

### Sprint 1
- **Files**: `src/diagnoser/models.py`, `src/diagnoser/analyzers/file_attributes.py`, `src/diagnoser/recommendations/recommender.py`, `tests/test_models.py`, `tests/test_file_attributes.py`, `tests/test_recommender.py`.
- **Summary**: Implemented file-attribute inspection, result models, context-aware recommendations, and 27 new tests.
- **Tests**: 104 collected, 103 passed, 0 failed, 1 skipped.
- **Commit**: `87be4bc` (`feat: add file attribute analyzer and recommender`).

### Sprint 2
- **Files**: `src/diagnoser/analyzers/sync_conflict.py`, `tests/test_sync_conflict.py`, `docs/REVIEW3_ENGINEERING_LOG.md`.
- **Summary**: Implemented bounded local sync discovery for OneDrive and Google Drive, conservative evidence tiers, lock correlation contract, 20 new tests, and full living engineering log.
- **Tests**: 124 collected, 123 passed, 0 failed, 1 skipped.
- **Commit**: `57cfd56` (`feat: add OneDrive and Google Drive sync diagnostics`).

### Sprint 3
- **Files**: `src/diagnoser/engine/diagnosis.py`, `src/diagnoser/recommendations/recommender.py`, `tests/test_diagnoser.py`, `docs/REVIEW3_ENGINEERING_LOG.md`.
- **Summary**: Integrated all four peer analyzers into `DiagnosisEngine`, implemented deterministic root-cause priority resolution, preserved secondary evidence, integrated standalone `Recommender`, and added 15 integration tests.
- **Tests**: 139 collected, 138 passed, 0 failed, 1 skipped.
- **Commit Target**: `feat: integrate four-analyzer diagnosis engine`.
