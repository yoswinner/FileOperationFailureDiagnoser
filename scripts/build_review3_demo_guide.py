#!/usr/bin/env python3
"""
Build Illustrated Review 3 Demonstration Guide in Word (.docx) and PDF (.pdf).

Generates a beautifully formatted HTML demonstration guide embedding all genuine
GUI screenshots from 'artifacts/review3/final_screenshots/', then uses native
Microsoft Word COM automation to produce:
  - artifacts/review3/Review3_Demo_Guide.docx
  - artifacts/review3/Review3_Demo_Guide.pdf
"""

import os
import subprocess
import sys
import time

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_ARTIFACTS_DIR = os.path.join(_PROJECT_ROOT, "artifacts", "review3")
_SCREENSHOTS_DIR = os.path.join(_ARTIFACTS_DIR, "final_screenshots")
_V2_SCREENSHOTS_DIR = os.path.join(_ARTIFACTS_DIR, "final_screenshots_v2")
_V3_SCREENSHOTS_DIR = os.path.join(_ARTIFACTS_DIR, "final_screenshots_v3")
_HTML_PATH = os.path.join(_ARTIFACTS_DIR, "Review3_Demo_Guide.html")
_DOCX_PATH = os.path.join(_ARTIFACTS_DIR, "Review3_Demo_Guide.docx")
_PDF_PATH = os.path.join(_ARTIFACTS_DIR, "Review3_Demo_Guide.pdf")


def build_html_content() -> str:
    """Generate comprehensive HTML content with embedded screenshots and clean styling."""
    def img_tag(filename: str, caption: str) -> str:
        base_id = filename.removesuffix(".png")
        top_filename = f"{base_id}_top.png"
        bottom_filename = f"{base_id}_bottom.png"

        # Check v3 first, then v2, then fallback base names
        top_path = os.path.join(_V3_SCREENSHOTS_DIR, top_filename)
        bottom_path = os.path.join(_V3_SCREENSHOTS_DIR, bottom_filename)

        if not (os.path.exists(top_path) and os.path.exists(bottom_path)):
            top_path = os.path.join(_V2_SCREENSHOTS_DIR, top_filename)
            bottom_path = os.path.join(_V2_SCREENSHOTS_DIR, bottom_filename)

        if not (os.path.exists(top_path) and os.path.exists(bottom_path)):
            # If base_id was 01a_normal_file_read, check 01_normal_file_read in v2
            fallback_base = base_id.replace("01a_", "01_")
            top_path = os.path.join(_V2_SCREENSHOTS_DIR, f"{fallback_base}_top.png")
            bottom_path = os.path.join(_V2_SCREENSHOTS_DIR, f"{fallback_base}_bottom.png")

        if os.path.exists(top_path) and os.path.exists(bottom_path):
            top_uri = top_path.replace("\\", "/")
            bottom_uri = bottom_path.replace("\\", "/")
            return f"""
            <table class="screenshot-pair-table">
                <tr>
                    <td class="screenshot-cell">
                        <img src="{top_uri}" alt="{caption} - Upper Viewport" class="pair-screenshot" />
                        <p class="pair-caption"><strong>Upper Viewport:</strong> Controls, Status & Process Locks</p>
                    </td>
                    <td class="screenshot-cell">
                        <img src="{bottom_uri}" alt="{caption} - Lower Viewport" class="pair-screenshot" />
                        <p class="pair-caption"><strong>Lower Viewport:</strong> Attributes, Sync & Recommendation</p>
                    </td>
                </tr>
            </table>
            """

        full_path = os.path.join(_SCREENSHOTS_DIR, filename).replace("\\", "/")
        return f"""
        <div class="figure-container">
            <img src="{full_path}" alt="{caption}" class="screenshot" />
            <p class="caption"><strong>Figure:</strong> {caption}</p>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>File Operation Failure Diagnoser — Review 3 Demonstration Guide</title>
<style>
    body {{
        font-family: 'Segoe UI', Calibri, Arial, sans-serif;
        color: #1e293b;
        line-height: 1.5;
        margin: 40px;
    }}
    h1.doc-title {{
        font-size: 26pt;
        color: #0f172a;
        margin-bottom: 4px;
        font-weight: 700;
    }}
    p.doc-subtitle {{
        font-size: 14pt;
        color: #475569;
        margin-top: 0;
        margin-bottom: 24px;
        border-bottom: 2px solid #cbd5e1;
        padding-bottom: 12px;
    }}
    .meta-box {{
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-left: 4px solid #3b82f6;
        padding: 12px 16px;
        margin-bottom: 28px;
        font-size: 10pt;
    }}
    .meta-box table {{
        width: 100%;
        border-collapse: collapse;
    }}
    .meta-box td {{
        padding: 4px 8px;
        vertical-align: top;
    }}
    h2 {{
        font-size: 17pt;
        color: #0f172a;
        border-bottom: 1px solid #e2e8f0;
        padding-bottom: 6px;
        margin-top: 32px;
        margin-bottom: 12px;
    }}
    h3 {{
        font-size: 13pt;
        color: #2563eb;
        margin-top: 24px;
        margin-bottom: 8px;
    }}
    p, li {{
        font-size: 10.5pt;
        color: #334155;
    }}
    ul {{
        margin-top: 6px;
        margin-bottom: 12px;
        padding-left: 24px;
    }}
    li {{
        margin-bottom: 4px;
    }}
    table.data-table {{
        width: 100%;
        border-collapse: collapse;
        margin: 16px 0;
        font-size: 9.5pt;
    }}
    table.data-table th {{
        background-color: #f1f5f9;
        color: #0f172a;
        font-weight: 600;
        text-align: left;
        padding: 8px 10px;
        border: 1px solid #cbd5e1;
    }}
    table.data-table td {{
        padding: 8px 10px;
        border: 1px solid #cbd5e1;
        vertical-align: top;
    }}
    table.data-table tr:nth-child(even) {{
        background-color: #f8fafc;
    }}
    .callout {{
        background-color: #eff6ff;
        border-left: 4px solid #2563eb;
        padding: 10px 14px;
        margin: 12px 0;
        font-size: 10pt;
    }}
    .callout-title {{
        font-weight: bold;
        color: #1e40af;
        margin-bottom: 4px;
    }}
    table.screenshot-pair-table {{
        width: 100%;
        border-collapse: collapse;
        margin: 8px 0 14px 0;
        table-layout: fixed;
        page-break-inside: avoid;
    }}
    td.screenshot-cell {{
        width: 50%;
        vertical-align: top;
        padding: 4px 6px;
        border: none;
        text-align: center;
    }}
    img.pair-screenshot {{
        width: 100%;
        max-width: 330px;
        height: auto;
        border: 1px solid #cbd5e1;
        border-radius: 4px;
        display: block;
        margin: 0 auto;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.08);
    }}
    p.pair-caption {{
        font-size: 8.5pt;
        color: #475569;
        margin-top: 4px;
        margin-bottom: 2px;
        line-height: 1.25;
        font-style: italic;
    }}
    .figure-container {{
        text-align: center;
        margin: 12px 0 18px 0;
        page-break-inside: avoid;
    }}
    img.screenshot {{
        width: 480px;
        max-width: 95%;
        height: auto;
        border: 1px solid #cbd5e1;
        border-radius: 4px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.08);
    }}
    p.caption {{
        font-size: 8.5pt;
        color: #64748b;
        font-style: italic;
        margin-top: 4px;
    }}
    code {{
        font-family: Consolas, 'Courier New', monospace;
        font-size: 9.5pt;
        background-color: #f1f5f9;
        padding: 2px 5px;
        border-radius: 3px;
        color: #0f172a;
    }}
    pre {{
        background-color: #0f172a;
        color: #f8fafc;
        padding: 12px;
        border-radius: 4px;
        font-family: Consolas, monospace;
        font-size: 9.5pt;
        overflow-x: auto;
    }}
</style>
</head>
<body>

<h1 class="doc-title">File Operation Failure Diagnoser</h1>
<p class="doc-subtitle">Review 3 — Teacher Demonstration Guide & Student Presentation Manual</p>

<div class="meta-box">
    <table>
        <tr>
            <td><strong>Project Title:</strong> File Operation Failure Diagnoser</td>
            <td><strong>Evaluation:</strong> Review 3 (Final Capstone Evaluation)</td>
        </tr>
        <tr>
            <td><strong>Platform:</strong> Microsoft Windows 11 Pro 64-bit</td>
            <td><strong>Runtime:</strong> Python {sys.version.split()[0]} (venv) & Tkinter 8.6 Desktop GUI</td>
        </tr>
        <tr>
            <td><strong>Recommended Presentation Duration:</strong> 5–8 Minutes</td>
            <td><strong>Generated Timestamp:</strong> {time.strftime('%Y-%m-%d %H:%M:%S')}</td>
        </tr>
    </table>
</div>

<h2>1. Project Overview & Architecture</h2>
<p>
The <strong>File Operation Failure Diagnoser</strong> is an automated, non-invasive systems utility designed to diagnose file access failures on Microsoft Windows. When an application encounters errors such as <code>ERROR_ACCESS_DENIED</code> (Win32 Error 5) or <code>ERROR_SHARING_VIOLATION</code> (Win32 Error 32), the Diagnoser investigates the root cause across four independent subsystems, deterministically correlates findings, and advises actionable recovery steps without mutating system state.
</p>

<h3>The Four Peer Analyzers</h3>
<table class="data-table">
    <thead>
        <tr>
            <th>Analyzer Subsystem</th>
            <th>Underlying Windows API / OS Mechanism</th>
            <th>Primary Telemetry Captured</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><strong>Process Lock Analyzer</strong></td>
            <td>Windows Restart Manager (<code>rstrtmgr.dll</code>)</td>
            <td>Active locking processes, PIDs, application types, executable paths.</td>
        </tr>
        <tr>
            <td><strong>Permission Analyzer</strong></td>
            <td><code>os.access()</code> + Win32 <code>advapi32.dll</code> Security APIs</td>
            <td>Current user access rights, file owner, effective permission bitmask.</td>
        </tr>
        <tr>
            <td><strong>File Attribute Analyzer</strong></td>
            <td><code>kernel32.GetFileAttributesW</code></td>
            <td>Win32 attribute bitmasks (<code>READONLY</code>, <code>HIDDEN</code>, <code>SYSTEM</code>, <code>ARCHIVE</code>, <code>REPARSE_POINT</code>, <code>OFFLINE</code>).</td>
        </tr>
        <tr>
            <td><strong>Cloud Sync Analyzer</strong></td>
            <td>Bounded Local Discovery (Registry + Environment)</td>
            <td>Detection of Microsoft OneDrive and Google Drive roots, daemon state, and sync lock correlation.</td>
        </tr>
    </tbody>
</table>

<div class="callout">
    <div class="callout-title">Architectural Guarantee: Operation Semantics</div>
    The diagnoser evaluates access semantics for the requested operation (<code>READ</code>, <code>WRITE</code>, <code>EXECUTE</code>, <code>DELETE</code>). For example, a <code>READ_ONLY</code> attribute flag prevents <code>WRITE</code> and <code>DELETE</code>, but explicitly allows <code>READ</code> and <code>EXECUTE</code>. The tool never executes, writes, or deletes the target file.
</div>

<h2>2. Environment Setup & Launch Commands</h2>
<p>To conduct a seamless live demonstration, execute the following commands from PowerShell in the workspace root:</p>

<div class="callout">
    <div class="callout-title">Terminal 1 — Launch the Desktop Application</div>
    <pre>.\\venv\\Scripts\\python.exe -m diagnoser.gui.app</pre>
</div>

<div class="callout">
    <div class="callout-title">Terminal 1 — Prepare Special Attributes (Optional Pre-Flight)</div>
    <pre>powershell -ExecutionPolicy Bypass -File scripts/prepare_teacher_demo_fixtures.ps1</pre>
    <p>Applies Read-Only, Hidden, and System attributes to managed demonstration fixtures in <code>artifacts/review3/demo_fixtures/teacher_demo/</code>.</p>
</div>

<div class="callout">
    <div class="callout-title">Terminal 2 — Start Lock Helper (For Lock Demonstration)</div>
    <pre>.\\venv\\Scripts\\python.exe scripts/hold_demo_file_open.py</pre>
    <p>Holds an open handle on <code>05_locked_file.txt</code> and displays its PID. Press <code>Ctrl+C</code> in Terminal 2 when finished.</p>
</div>

<div class="callout">
    <div class="callout-title">Terminal 1 — Clean Up & Restore Baseline Attributes (Post-Demonstration)</div>
    <pre>powershell -ExecutionPolicy Bypass -File scripts/restore_teacher_demo_fixtures.ps1</pre>
</div>

<h2>3. Step-by-Step Live Walkthrough & Screenshot Atlas</h2>

<h3>Scenario 1A — Baseline Accessible File (READ)</h3>
<ul>
    <li><strong>Target Fixture:</strong> <code>artifacts/review3/demo_fixtures/teacher_demo/01_normal_file.txt</code></li>
    <li><strong>Requested Operation:</strong> <code>READ</code></li>
    <li><strong>Expected Primary Diagnosis:</strong> <code>OPERATION_ALLOWED</code></li>
    <li><strong>Evidence Panels to Point To:</strong> Green status badge, empty lock treeview, granted read/write/exec/delete bits, Archive bitmask (0x0020), "No provider association detected".</li>
    <li><strong>Explanation to Teacher:</strong> <em>"Notice how all four peer analyzers execute concurrently. None encountered a contention condition, so the engine cleanly concludes that read access is allowed."</em></li>
</ul>
{img_tag("01a_normal_file_read.png", "Scenario 1A — Baseline Accessible File (READ -> OPERATION_ALLOWED)")}

<h3>Scenario 1B — Baseline Accessible File (WRITE)</h3>
<ul>
    <li><strong>Target Fixture:</strong> <code>artifacts/review3/demo_fixtures/teacher_demo/01_normal_file.txt</code></li>
    <li><strong>Requested Operation:</strong> <code>WRITE</code></li>
    <li><strong>Expected Primary Diagnosis:</strong> <code>OPERATION_ALLOWED</code></li>
    <li><strong>Evidence Panels to Point To:</strong> Green status badge, WRITE permission permitted, Archive attribute (0x0020), and recommendation confirming file is ready.</li>
    <li><strong>Explanation to Teacher:</strong> <em>"Evaluating WRITE on an unrestricted file returns OPERATION_ALLOWED. Crucially, the diagnoser assesses write accessibility safely without modifying or writing to the target file."</em></li>
</ul>
{img_tag("01b_normal_file_write.png", "Scenario 1B — Baseline Accessible File (WRITE -> OPERATION_ALLOWED)")}

<h3>Scenario 2 — Nonexistent File Target</h3>
<ul>
    <li><strong>Target Fixture:</strong> Nonexistent path (e.g. <code>C:\\missing_file_xyz.txt</code>)</li>
    <li><strong>Requested Operation:</strong> <code>READ</code></li>
    <li><strong>Expected Primary Diagnosis:</strong> <code>FILE_NOT_FOUND</code></li>
    <li><strong>Evidence Panels to Point To:</strong> Amber status badge. All four evidence cards display "Checks skipped: Target file does not exist."</li>
    <li><strong>Explanation to Teacher:</strong> <em>"Early exit prevents cascading false errors. Downstream checks are honestly skipped rather than fabricating blank results."</em></li>
</ul>
{img_tag("02_file_not_found.png", "Scenario 2 — Nonexistent File Target (FILE_NOT_FOUND with Honest Skipped Checks)")}

<h3>Scenario 3 — Active Process Lock Detection (WRITE)</h3>
<ul>
    <li><strong>Preparation:</strong> In Terminal 2, start <code>python scripts/hold_demo_file_open.py</code>. Note the PID.</li>
    <li><strong>Target Fixture:</strong> <code>artifacts/review3/demo_fixtures/teacher_demo/05_locked_file.txt</code></li>
    <li><strong>Requested Operation:</strong> <code>WRITE</code></li>
    <li><strong>Expected Primary Diagnosis:</strong> <code>FILE_LOCKED</code></li>
    <li><strong>Evidence Panels to Point To:</strong> Lock Treeview displaying Process Name (<code>python.exe</code>), PID, and Executable Path.</li>
    <li><strong>Explanation to Teacher:</strong> <em>"Our Process Lock Analyzer communicates directly with the Windows Restart Manager API, identifying the exact process holding an open handle."</em></li>
</ul>
{img_tag("03_process_locked_write.png", "Scenario 3 — Active Process Lock (WRITE -> FILE_LOCKED with Process Telemetry)")}

<h3>Scenario 4 — Read-Only Attribute Semantics (WRITE vs. READ Contrast)</h3>
<ul>
    <li><strong>Target Fixture:</strong> <code>artifacts/review3/demo_fixtures/teacher_demo/02_read_only_file.txt</code></li>
    <li><strong>Step 4A (WRITE):</strong> Diagnosis: <code>READ_ONLY</code>. File Attributes card shows <code>READONLY</code> bit set (0x0021). Effect: "Blocks write and delete operations."</li>
    <li><strong>Step 4B (READ):</strong> Change operation to <code>READ</code>. Diagnosis: <code>OPERATION_ALLOWED</code>. Effect: "Read-only does NOT block READ."</li>
    <li><strong>Explanation to Teacher:</strong> <em>"This is a crucial architectural distinction: a read-only file is completely readable! The engine evaluates operation semantics rather than treating Read-Only as a blanket failure."</em></li>
</ul>
{img_tag("04a_read_only_write.png", "Scenario 4A — Read-Only Attribute on WRITE (READ_ONLY)")}
{img_tag("04b_read_only_read.png", "Scenario 4B — Same Read-Only File on READ (OPERATION_ALLOWED Contrast)")}

<h3>Scenario 5 — File Attributes Evidence (Hidden & Archive)</h3>
<ul>
    <li><strong>Target Fixture:</strong> <code>artifacts/review3/demo_fixtures/teacher_demo/03_hidden_archive_file.txt</code></li>
    <li><strong>Requested Operation:</strong> <code>READ</code></li>
    <li><strong>Expected Primary Diagnosis:</strong> <code>OPERATION_ALLOWED</code></li>
    <li><strong>Evidence Panels to Point To:</strong> Raw Bitmask <code>0x0022</code> (<code>HIDDEN | ARCHIVE</code>). Effect: "Attributes do not prevent reading."</li>
    <li><strong>Explanation to Teacher:</strong> <em>"Demonstrates robust Win32 bitmask parsing without producing false blocking alarms for hidden files."</em></li>
</ul>
{img_tag("06_file_attributes_hidden_archive.png", "Scenario 5 — File Attributes Evidence (Hidden & Archive -> OPERATION_ALLOWED)")}

<h3>Scenario 6 — System Flag Bitmask Detection (0x0004)</h3>
<ul>
    <li><strong>Target Fixture:</strong> <code>artifacts/review3/demo_fixtures/teacher_demo/04_system_attribute_file.txt</code></li>
    <li><strong>Requested Operation:</strong> <code>READ</code></li>
    <li><strong>Expected Primary Diagnosis:</strong> <code>OPERATION_ALLOWED</code></li>
    <li><strong>Evidence Panels to Point To:</strong> File Attributes card displaying Raw Bitmask <code>0x0024</code> (<code>SYSTEM | ARCHIVE</code>).</li>
    <li><strong>Explanation to Teacher:</strong> <em>"The analyzer accurately decodes the Win32 FILE_ATTRIBUTE_SYSTEM flag while confirming read access is permitted."</em></li>
</ul>
{img_tag("13_system_attribute_evidence.png", "Scenario 6 — System Attribute Bitmask Detection (0x0024)")}

<h3>Scenario 7 — Operation Coverage: DELETE Semantics</h3>
<ul>
    <li><strong>Step 7A (Normal File):</strong> Target <code>07_delete_check_file.txt</code> on <code>DELETE</code> -> <code>OPERATION_ALLOWED</code>. File remains on disk.</li>
    <li><strong>Step 7B (Read-Only File):</strong> Target <code>02_read_only_file.txt</code> on <code>DELETE</code> -> <code>READ_ONLY</code>. Diagnoses that Read-Only blocks deletion.</li>
    <li><strong>Explanation to Teacher:</strong> <em>"Our application is strictly diagnostic. It checks whether DELETE would succeed without performing destructive deletions."</em></li>
</ul>
{img_tag("11_operation_delete_allowed.png", "Scenario 7A — DELETE on Normal File (Allowed, File Intact)")}
{img_tag("12_operation_delete_readonly.png", "Scenario 7B — DELETE on Read-Only File (Blocked by READ_ONLY)")}

<h3>Scenario 8 — Operation Coverage: EXECUTE Semantics</h3>
<ul>
    <li><strong>Target Fixture:</strong> <code>artifacts/review3/demo_fixtures/teacher_demo/08_execute_check.cmd</code></li>
    <li><strong>Requested Operation:</strong> <code>EXECUTE</code></li>
    <li><strong>Expected Primary Diagnosis:</strong> <code>OPERATION_ALLOWED</code></li>
    <li><strong>Explanation to Teacher:</strong> <em>"Evaluates execute rights statically via os.access(X_OK) and owner rights. It never spawns or executes arbitrary code."</em></li>
</ul>
{img_tag("10_operation_execute.png", "Scenario 8 — Harmless Command Script on EXECUTE (OPERATION_ALLOWED)")}

<h3>Scenario 9 — Cloud Synchronization Boundary Detection</h3>
<ul>
    <li><strong>Target Fixture:</strong> <code>artifacts/review3/demo_fixtures/teacher_demo/01_normal_file.txt</code></li>
    <li><strong>Requested Operation:</strong> <code>READ</code></li>
    <li><strong>Evidence Panels to Point To:</strong> Cloud Sync card displaying Provider: <code>None</code>, Evidence Level: <code>none</code>, "No provider association detected."</li>
    <li><strong>Explanation to Teacher:</strong> <em>"Sync discovery is bounded to local roots for Microsoft OneDrive and Google Drive. Because this file is outside cloud roots, it honestly reports no provider association rather than guessing."</em></li>
</ul>
{img_tag("07_cloud_sync_negative.png", "Scenario 9 — Cloud Sync Boundary Evidence (Negative Finding Verified)")}

<h3>Scenario 10 — Multiple Simultaneous Findings & Priority Resolution</h3>
<ul>
    <li><strong>Setup:</strong> Hold <code>05_locked_file.txt</code> open in Terminal 2, and apply ReadOnly attribute.</li>
    <li><strong>Requested Operation:</strong> <code>WRITE</code></li>
    <li><strong>Expected Primary Diagnosis:</strong> <code>FILE_LOCKED</code> (Primary Root Cause)</li>
    <li><strong>Evidence Panels to Point To:</strong> Primary badge displays <code>FILE_LOCKED</code>. File Attributes card displays Read-Only = Yes as secondary evidence.</li>
    <li><strong>Explanation to Teacher:</strong> <em>"Deterministic priority resolution: active process locks take precedence over attributes, while preserving the read-only flag as secondary telemetry."</em></li>
</ul>
{img_tag("08_multiple_findings_lock_and_readonly.png", "Scenario 10 — Multiple Simultaneous Findings (FILE_LOCKED Primary, Read-Only Secondary)")}

<h3>Scenario 11 — Invalid Target Type (Directory Handling)</h3>
<ul>
    <li><strong>Target Path:</strong> Select any directory folder (e.g. <code>teacher_demo</code>).</li>
    <li><strong>Requested Operation:</strong> <code>READ</code></li>
    <li><strong>Expected Primary Diagnosis:</strong> <code>UNKNOWN_ERROR</code></li>
    <li><strong>Evidence Panels to Point To:</strong> Status badge shows <code>UNKNOWN_ERROR</code>. Reason: "Permission inspection error: Target is a directory, not a regular file."</li>
    <li><strong>Explanation to Teacher:</strong> <em>"Directories produce structured diagnostic error messages rather than unhandled application crashes."</em></li>
</ul>
{img_tag("09_inspection_error_directory.png", "Scenario 11 — Directory Target Produces Structured Diagnostic Error")}

<h3>Scenario 12 — Re-Diagnosis & Zero Stale Data Leakage</h3>
<ul>
    <li><strong>Action:</strong> Diagnose locked file, then immediately re-diagnose normal file.</li>
    <li><strong>Observation:</strong> Process tree clears instantly, badge reverts to green <code>OPERATION_ALLOWED</code>.</li>
    <li><strong>Explanation to Teacher:</strong> <em>"The _reset_panels() architecture guarantees zero telemetry leakage across repeated diagnoses."</em></li>
</ul>
{img_tag("14_reset_stale_clearing.png", "Scenario 12 — Sequential Re-Diagnosis Verifies Zero Stale Data Leakage")}

<h2>4. Key Limitations to Explain Accurately</h2>
<ul>
    <li><strong>NTFS DACL vs. Windows Restart Manager:</strong> If an explicit Deny-Read ACE is set on an NTFS file (<code>icacls /deny %USERNAME%:(R)</code>), Windows Restart Manager (<code>RmGetList</code>) fails with Win32 Error 5 (<code>ERROR_ACCESS_DENIED</code>) because the API itself lacks query access. The engine honestly reports <code>UNKNOWN_ERROR</code> ("Lock inspection error: RmGetList failed with error code 5") rather than fabricating a successful lock check.</li>
    <li><strong>Windows CRT <code>_access()</code> Semantics:</strong> Python's standard <code>os.access(W_OK)</code> on Windows delegates to the MSVC C-Runtime <code>_access()</code> function. By Microsoft OS design, <code>_access()</code> only inspects the DOS <code>FILE_ATTRIBUTE_READONLY</code> flag and does not evaluate NTFS DACLs.</li>
    <li><strong>Cloud Synchronization Scope:</strong> Supported providers are strictly limited to Microsoft OneDrive and Google Drive. Files outside sync roots report <code>none</code>, and potential contention is not called a confirmed lock without active daemon evidence.</li>
</ul>

<h2>5. Ready-to-Use Presentation Checklist</h2>
<table class="data-table">
    <thead>
        <tr>
            <th>Step</th>
            <th>Action</th>
            <th>Command / Fixture</th>
            <th>Verification Check</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td>1</td>
            <td>Launch GUI</td>
            <td><code>.\\venv\\Scripts\\python.exe -m diagnoser.gui.app</code></td>
            <td>Dark-themed Tkinter GUI opens cleanly.</td>
        </tr>
        <tr>
            <td>2</td>
            <td>Prepare Fixtures</td>
            <td><code>powershell -File scripts/prepare_teacher_demo_fixtures.ps1</code></td>
            <td>Attributes applied to demo fixtures.</td>
        </tr>
        <tr>
            <td>3</td>
            <td>Scenario 1 (Normal)</td>
            <td>Select <code>01_normal_file.txt</code> -> READ</td>
            <td>Status: <code>OPERATION_ALLOWED</code>.</td>
        </tr>
        <tr>
            <td>4</td>
            <td>Scenario 2 (Missing)</td>
            <td>Type <code>missing.txt</code> -> READ</td>
            <td>Status: <code>FILE_NOT_FOUND</code>.</td>
        </tr>
        <tr>
            <td>5</td>
            <td>Scenario 3 (Lock)</td>
            <td>Terminal 2: <code>python scripts/hold_demo_file_open.py</code> -> WRITE</td>
            <td>Status: <code>FILE_LOCKED</code> + PID shown.</td>
        </tr>
        <tr>
            <td>6</td>
            <td>Scenario 4 (Read-Only)</td>
            <td>Select <code>02_read_only_file.txt</code> -> WRITE then READ</td>
            <td>WRITE: <code>READ_ONLY</code>; READ: <code>OPERATION_ALLOWED</code>.</td>
        </tr>
        <tr>
            <td>7</td>
            <td>Scenario 7 (DELETE)</td>
            <td>Select <code>07_delete_check_file.txt</code> -> DELETE</td>
            <td>Status: <code>OPERATION_ALLOWED</code> (File intact).</td>
        </tr>
        <tr>
            <td>8</td>
            <td>Scenario 10 (Priority)</td>
            <td>Select locked + read-only fixture -> WRITE</td>
            <td>Status: <code>FILE_LOCKED</code> (Primary priority).</td>
        </tr>
        <tr>
            <td>9</td>
            <td>Scenario 12 (Reset)</td>
            <td>Re-diagnose <code>01_normal_file.txt</code></td>
            <td>Process tree clears completely.</td>
        </tr>
        <tr>
            <td>10</td>
            <td>Cleanup</td>
            <td><code>powershell -File scripts/restore_teacher_demo_fixtures.ps1</code></td>
            <td>Attributes restored to normal baseline.</td>
        </tr>
    </tbody>
</table>

</body>
</html>
"""


def main():
    print("=" * 65)
    print(" Generating Illustrated Review 3 Demonstration Guide")
    print("=" * 65)

    # 1. Write HTML file
    print("Writing HTML source: Review3_Demo_Guide.html...")
    html_content = build_html_content()
    with open(_HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"  -> Saved HTML: {_HTML_PATH} ({os.path.getsize(_HTML_PATH):,} bytes)")

    # 2. Use PowerShell to drive Word COM to convert HTML to DOCX and PDF
    print("\nInvoking Microsoft Word COM to render DOCX and export PDF...")
    ps_script_path = os.path.join(_ARTIFACTS_DIR, "convert_to_word.ps1")
    with open(ps_script_path, "w", encoding="utf-8") as f:
        f.write(f"""
$ErrorActionPreference = "Stop"
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0

try {{
    $htmlPath = [System.IO.Path]::GetFullPath('{_HTML_PATH}')
    $docxPath = [System.IO.Path]::GetFullPath('{_DOCX_PATH}')
    $pdfPath = [System.IO.Path]::GetFullPath('{_PDF_PATH}')

    $doc = $word.Documents.Open($htmlPath)

    # Set page margins to 0.6 inch to optimize layout
    $doc.PageSetup.TopMargin = $word.InchesToPoints(0.6)
    $doc.PageSetup.BottomMargin = $word.InchesToPoints(0.6)
    $doc.PageSetup.LeftMargin = $word.InchesToPoints(0.6)
    $doc.PageSetup.RightMargin = $word.InchesToPoints(0.6)

    # Ensure table rows never split across page breaks
    foreach ($t in $doc.Tables) {{
        try {{
            $t.Rows.AllowBreakAcrossPages = 0
        }} catch {{}}
    }}

    # Ensure headings stay with their content
    foreach ($p in $doc.Paragraphs) {{
        if ($p.OutlineLevel -ge 1 -and $p.OutlineLevel -le 4) {{
            $p.Format.KeepWithNext = $true
        }}
    }}

    # Save as DOCX (16 = wdFormatXMLDocument)
    $doc.SaveAs([ref]$docxPath, [ref]16)
    Write-Host "[OK] Saved Word Document: $docxPath"

    # Save as PDF (17 = wdFormatPDF)
    try {{
        $doc.SaveAs([ref]$pdfPath, [ref]17)
        Write-Host "[OK] Exported PDF Document: $pdfPath"
    }} catch {{
        Write-Warning "PDF export error: $_"
    }}

    $doc.Close()
}} finally {{
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}}
""")

    p = subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-File", ps_script_path],
        capture_output=True,
        text=True,
    )
    print("Word COM Output:\n" + p.stdout)
    if p.stderr:
        print("Word COM Warnings/Errors:\n" + p.stderr)

    if os.path.exists(ps_script_path):
        os.remove(ps_script_path)

    if os.path.exists(_DOCX_PATH):
        print(f"[SUCCESS] Word Document created: {_DOCX_PATH} ({os.path.getsize(_DOCX_PATH):,} bytes)")
    else:
        print("[FAIL] Word Document was not created.")

    if os.path.exists(_PDF_PATH):
        print(f"[SUCCESS] PDF Document created: {_PDF_PATH} ({os.path.getsize(_PDF_PATH):,} bytes)")
    else:
        print("[FAIL] PDF Document was not created.")


if __name__ == "__main__":
    main()
