"""
Main Window — Tkinter Desktop GUI for the File Operation Failure Diagnoser.

This module provides the complete presentation layer connecting all four
diagnostic analyzers (Process Locks, Permissions, File Attributes, Cloud Sync)
and the Recommender to the Tkinter desktop GUI.

Architecture:
    USER  →  MainWindow  →  DiagnosisEngine  →  4 Analyzers  →  Results  →  GUI

Safety:
    Pure presentation layer. Never mutates files, terminates processes, or
    modifies permissions/attributes. Consumes structured DiagnosisResult objects.
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from diagnoser.engine.diagnosis import DiagnosisEngine
from diagnoser.models import (
    DiagnosisResult,
    DiagnosisType,
    FileAttributeResult,
    FileOperation,
    LockDetectionResult,
    PermissionCheckResult,
    SyncConflictResult,
)


# ======================================================================
# Colour palette and display dictionaries
# ======================================================================

_COLOURS = {
    "bg":               "#1e1e2e",      # main background
    "bg_card":          "#2a2a3d",      # card/panel background
    "bg_card_alt":      "#33334d",      # alternate card shade
    "bg_entry":         "#3a3a52",      # text entry background
    "fg":               "#d4d4e8",      # default foreground text
    "fg_dim":           "#8888aa",      # dimmed/secondary text
    "fg_heading":       "#e8e8f0",      # headings
    "accent":           "#7c6ff7",      # primary accent (purple)
    "accent_hover":     "#6a5ce0",      # button hover
    "green":            "#4ec98b",      # success / allowed
    "red":              "#e05566",      # error / locked / denied
    "orange":           "#e8a54b",      # warning / read-only / sync / not found
    "grey":             "#7a7a9a",      # neutral / unknown / skipped
    "border":           "#3d3d57",      # card borders
}

_BADGE_CONFIG = {
    DiagnosisType.OPERATION_ALLOWED:   ("✓  OPERATION ALLOWED", _COLOURS["green"]),
    DiagnosisType.FILE_LOCKED:         ("✕  FILE LOCKED", _COLOURS["red"]),
    DiagnosisType.PERMISSION_DENIED:   ("✕  PERMISSION DENIED", _COLOURS["red"]),
    DiagnosisType.READ_ONLY:           ("⚠  READ ONLY", _COLOURS["orange"]),
    DiagnosisType.SYNC_CONFLICT:       ("⚠  SYNC CONFLICT", _COLOURS["orange"]),
    DiagnosisType.FILE_NOT_FOUND:      ("⚠  FILE NOT FOUND", _COLOURS["orange"]),
    DiagnosisType.UNKNOWN_ERROR:       ("?  UNKNOWN ERROR", _COLOURS["grey"]),
}

_BADGE_COLOURS = {
    DiagnosisType.OPERATION_ALLOWED:   _COLOURS["green"],
    DiagnosisType.FILE_LOCKED:         _COLOURS["red"],
    DiagnosisType.PERMISSION_DENIED:   _COLOURS["red"],
    DiagnosisType.READ_ONLY:           _COLOURS["orange"],
    DiagnosisType.SYNC_CONFLICT:       _COLOURS["orange"],
    DiagnosisType.FILE_NOT_FOUND:      _COLOURS["orange"],
    DiagnosisType.UNKNOWN_ERROR:       _COLOURS["grey"],
}

SYNC_EVIDENCE_LABELS = {
    "none": "No provider association detected",
    "path_only": "Sync-folder association detected",
    "potential_contention": "Potential contention; active lock not confirmed",
    "confirmed_lock": "Confirmed sync-client lock",
}

SYNC_PROVIDER_NAMES = {
    "onedrive": "Microsoft OneDrive",
    "google_drive": "Google Drive",
}


# ======================================================================
# MainWindow
# ======================================================================

class MainWindow:
    """Tkinter main application window.

    Provides file selection, operation selection, a Diagnose button,
    and structured presentation panels for:
      1. Overall Status & Diagnosis
      2. Process List & File Locks
      3. Permission & Ownership Verification
      4. File Attributes Analysis
      5. Cloud Synchronization Telemetry
      6. Context-Aware Recommendations

    Usage:
        window = MainWindow()
        window.run()
    """

    _WINDOW_TITLE = "File Operation Failure Diagnoser"
    _MIN_WIDTH = 920
    _MIN_HEIGHT = 840

    def __init__(
        self,
        engine: Optional[DiagnosisEngine] = None,
        root: Optional[tk.Tk] = None,
    ):
        """Initialise the GUI window.

        Args:
            engine: Optional DiagnosisEngine override for dependency injection.
            root: Optional tk.Tk root window for testing or custom embedding.
        """
        self._engine = engine if engine is not None else DiagnosisEngine()

        # ── Root window ─────────────────────────────────────────────
        self._root = root if root is not None else tk.Tk()
        self._root.title(self._WINDOW_TITLE)
        self._root.configure(bg=_COLOURS["bg"])
        self._root.minsize(self._MIN_WIDTH, self._MIN_HEIGHT)
        self._root.geometry(f"{self._MIN_WIDTH}x{self._MIN_HEIGHT}")

        # Try to set the window icon (non-critical if it fails)
        try:
            self._root.iconbitmap(default="")
        except tk.TclError:
            pass

        # ── ttk theme overrides ─────────────────────────────────────
        self._style = ttk.Style(self._root)
        self._configure_styles()

        # ── Build the UI ────────────────────────────────────────────
        self._build_ui()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def run(self):
        """Start the Tkinter event loop."""
        self._root.mainloop()

    # ------------------------------------------------------------------
    # Style configuration
    # ------------------------------------------------------------------

    def _configure_styles(self):
        """Apply dark-theme styling to ttk widgets."""
        s = self._style
        s.theme_use("clam")

        # Frames
        s.configure("Card.TFrame", background=_COLOURS["bg_card"])
        s.configure("CardAlt.TFrame", background=_COLOURS["bg_card_alt"])

        # Labels
        s.configure(
            "TLabel",
            background=_COLOURS["bg"],
            foreground=_COLOURS["fg"],
            font=("Segoe UI", 10),
        )
        s.configure(
            "Card.TLabel",
            background=_COLOURS["bg_card"],
            foreground=_COLOURS["fg"],
            font=("Segoe UI", 10),
        )
        s.configure(
            "Heading.TLabel",
            background=_COLOURS["bg"],
            foreground=_COLOURS["fg_heading"],
            font=("Segoe UI", 11, "bold"),
        )
        s.configure(
            "CardHeading.TLabel",
            background=_COLOURS["bg_card"],
            foreground=_COLOURS["fg_heading"],
            font=("Segoe UI", 11, "bold"),
        )
        s.configure(
            "Title.TLabel",
            background=_COLOURS["bg"],
            foreground=_COLOURS["fg_heading"],
            font=("Segoe UI", 18, "bold"),
        )
        s.configure(
            "Subtitle.TLabel",
            background=_COLOURS["bg"],
            foreground=_COLOURS["fg_dim"],
            font=("Segoe UI", 10),
        )
        s.configure(
            "Dim.TLabel",
            background=_COLOURS["bg_card"],
            foreground=_COLOURS["fg_dim"],
            font=("Segoe UI", 9),
        )
        s.configure(
            "Badge.TLabel",
            background=_COLOURS["grey"],
            foreground="#ffffff",
            font=("Segoe UI", 11, "bold"),
            padding=(10, 4),
        )
        s.configure(
            "PermBit.TLabel",
            background=_COLOURS["bg_card"],
            foreground=_COLOURS["fg"],
            font=("Segoe UI", 9),
        )

        # Combobox
        s.configure(
            "TCombobox",
            fieldbackground=_COLOURS["bg_entry"],
            background=_COLOURS["bg_entry"],
            foreground=_COLOURS["fg"],
            arrowcolor=_COLOURS["fg"],
            selectbackground=_COLOURS["accent"],
            selectforeground="#ffffff",
        )
        self._root.option_add("*TCombobox*Listbox.background", _COLOURS["bg_entry"])
        self._root.option_add("*TCombobox*Listbox.foreground", _COLOURS["fg"])
        self._root.option_add("*TCombobox*Listbox.selectBackground", _COLOURS["accent"])
        self._root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

        # Treeview
        s.configure(
            "Treeview",
            background=_COLOURS["bg_card"],
            foreground=_COLOURS["fg"],
            fieldbackground=_COLOURS["bg_card"],
            font=("Segoe UI", 9),
            rowheight=26,
        )
        s.configure(
            "Treeview.Heading",
            background=_COLOURS["bg_card_alt"],
            foreground=_COLOURS["fg_heading"],
            font=("Segoe UI", 9, "bold"),
        )
        s.map(
            "Treeview",
            background=[("selected", _COLOURS["accent"])],
            foreground=[("selected", "#ffffff")],
        )

        # Button
        s.configure(
            "Accent.TButton",
            background=_COLOURS["accent"],
            foreground="#ffffff",
            font=("Segoe UI", 11, "bold"),
            padding=(20, 8),
        )
        s.map(
            "Accent.TButton",
            background=[
                ("active", _COLOURS["accent_hover"]),
                ("pressed", _COLOURS["accent_hover"]),
            ],
        )
        s.configure(
            "Browse.TButton",
            background=_COLOURS["bg_card_alt"],
            foreground=_COLOURS["fg"],
            font=("Segoe UI", 9),
            padding=(10, 4),
        )
        s.map(
            "Browse.TButton",
            background=[("active", _COLOURS["accent"])],
            foreground=[("active", "#ffffff")],
        )

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        """Construct all interface components."""
        # Scrollable container
        canvas = tk.Canvas(
            self._root, bg=_COLOURS["bg"], highlightthickness=0,
        )
        self._canvas = canvas
        scrollbar = ttk.Scrollbar(
            self._root, orient="vertical", command=canvas.yview,
        )
        self._scroll_frame = ttk.Frame(canvas, style="TFrame")
        self._style.configure("TFrame", background=_COLOURS["bg"])

        self._scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        self._canvas_window = canvas.create_window(
            (0, 0), window=self._scroll_frame, anchor="nw",
        )
        canvas.configure(yscrollcommand=scrollbar.set)

        def _sync_frame_width(event):
            canvas.itemconfigure(self._canvas_window, width=event.width)
        canvas.bind("<Configure>", _sync_frame_width)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Bind mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))

        container = self._scroll_frame

        # ── 1. Header ───────────────────────────────────────────────
        self._build_header(container)

        # ── 2. File Input ───────────────────────────────────────────
        self._build_file_input(container)

        # ── 3. Operation Selection ──────────────────────────────────
        self._build_operation_selector(container)

        # ── 4. Diagnose Button ──────────────────────────────────────
        self._build_diagnose_button(container)

        # ── 5. Status Panel ─────────────────────────────────────────
        self._build_status_panel(container)

        # ── 6. Row 1: Process List + Permissions (side by side) ─────
        self._build_process_and_permission_row(container)

        # ── 7. Row 2: File Attributes + Cloud Sync (side by side) ───
        self._build_attributes_and_sync_row(container)

        # ── 8. Recommendation Panel ─────────────────────────────────
        self._build_recommendation_panel(container)

        # ── Footer padding ──────────────────────────────────────────
        ttk.Frame(container, height=24).pack(fill="x")

    # ── Header ──────────────────────────────────────────────────────

    def _build_header(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill="x", padx=24, pady=(20, 4))

        ttk.Label(
            frame,
            text="File Operation Failure Diagnoser",
            style="Title.TLabel",
        ).pack(anchor="w")

        ttk.Label(
            frame,
            text="Comprehensive OS-level diagnostics for file sharing, permissions, attributes, and cloud synchronization.",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 0))

    # ── File Input ──────────────────────────────────────────────────

    def _build_file_input(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill="x", padx=24, pady=(12, 4))

        ttk.Label(frame, text="FILE", style="Heading.TLabel").pack(
            anchor="w", pady=(0, 4),
        )

        row = ttk.Frame(frame)
        row.pack(fill="x")

        self._file_var = tk.StringVar()
        self._file_entry = tk.Entry(
            row,
            textvariable=self._file_var,
            bg=_COLOURS["bg_entry"],
            fg=_COLOURS["fg"],
            insertbackground=_COLOURS["fg"],
            font=("Segoe UI", 10),
            relief="flat",
            highlightthickness=1,
            highlightcolor=_COLOURS["accent"],
            highlightbackground=_COLOURS["border"],
        )
        self._file_entry.pack(side="left", fill="x", expand=True, ipady=6)

        browse_btn = ttk.Button(
            row, text="Browse", style="Browse.TButton",
            command=self._browse_file,
        )
        browse_btn.pack(side="left", padx=(8, 0))

    # ── Operation Selection ─────────────────────────────────────────

    def _build_operation_selector(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill="x", padx=24, pady=(12, 4))

        ttk.Label(frame, text="OPERATION", style="Heading.TLabel").pack(
            anchor="w", pady=(0, 4),
        )

        self._operations = list(FileOperation)
        display_names = [op.value.upper() for op in self._operations]

        self._op_var = tk.StringVar(value=display_names[0])
        self._op_combo = ttk.Combobox(
            frame,
            textvariable=self._op_var,
            values=display_names,
            state="readonly",
            font=("Segoe UI", 10),
            width=20,
        )
        self._op_combo.pack(anchor="w", ipady=4)

    # ── Diagnose Button ─────────────────────────────────────────────

    def _build_diagnose_button(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill="x", padx=24, pady=(16, 4))

        btn = ttk.Button(
            frame,
            text="  Diagnose File  ",
            style="Accent.TButton",
            command=self._run_diagnosis,
        )
        btn.pack(anchor="center")

    # ── Status Panel ────────────────────────────────────────────────

    def _build_status_panel(self, parent):
        outer = ttk.Frame(parent)
        outer.pack(fill="x", padx=24, pady=(16, 4))

        ttk.Label(outer, text="STATUS", style="Heading.TLabel").pack(
            anchor="w", pady=(0, 6),
        )

        card = ttk.Frame(outer, style="Card.TFrame", padding=16)
        card.pack(fill="x")

        self._status_badge = ttk.Label(
            card, text="●  WAITING FOR INPUT", style="Badge.TLabel",
        )
        self._status_badge.pack(anchor="w", pady=(0, 10))

        info = ttk.Frame(card, style="Card.TFrame")
        info.pack(fill="x")

        self._status_file_lbl = self._kv_row(info, "File:", "—", label_width=14, wraplength=760)
        self._status_op_lbl = self._kv_row(info, "Operation:", "—", label_width=14, wraplength=760)
        self._status_reason_lbl = self._kv_row(info, "Reason:", "Select a file and operation, then click Diagnose File.", label_width=14, wraplength=760)

    # ── Details Row 1 (Process List + Permissions) ──────────────────

    def _build_process_and_permission_row(self, parent):
        outer = ttk.Frame(parent)
        outer.pack(fill="x", padx=24, pady=(16, 4))
        outer.columnconfigure(0, weight=1)
        outer.columnconfigure(1, weight=1)

        self._build_process_panel(outer, row=0, col=0)
        self._build_permission_panel(outer, row=0, col=1)

    def _build_process_panel(self, parent, row, col):
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=col, sticky="nsew", padx=(0, 8))

        ttk.Label(frame, text="PROCESS LIST", style="Heading.TLabel").pack(
            anchor="w", pady=(0, 6),
        )

        card = ttk.Frame(frame, style="Card.TFrame", padding=12)
        card.pack(fill="both", expand=True)

        columns = ("process", "pid", "executable")
        self._proc_tree = ttk.Treeview(
            card, columns=columns, show="headings", height=4,
        )
        self._proc_tree.heading("process", text="Process")
        self._proc_tree.heading("pid", text="PID")
        self._proc_tree.heading("executable", text="Executable Path")

        self._proc_tree.column("process", width=110, minwidth=80)
        self._proc_tree.column("pid", width=60, minwidth=50)
        self._proc_tree.column("executable", width=200, minwidth=100)

        self._proc_tree.pack(fill="both", expand=True)

        self._proc_placeholder = ttk.Label(
            card,
            text="No diagnosis performed yet.",
            style="Dim.TLabel",
        )
        self._proc_placeholder.pack(anchor="w", pady=(6, 0))

    def _build_permission_panel(self, parent, row, col):
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=col, sticky="nsew", padx=(8, 0))

        ttk.Label(frame, text="PERMISSIONS", style="Heading.TLabel").pack(
            anchor="w", pady=(0, 6),
        )

        card = ttk.Frame(frame, style="Card.TFrame", padding=12)
        card.pack(fill="both", expand=True)

        self._perm_owner_lbl = self._kv_row(card, "Owner:", "—", label_width=14)
        self._perm_user_lbl = self._kv_row(card, "Current User:", "—", label_width=14)
        self._perm_method_lbl = self._kv_row(card, "Detection:", "—", label_width=14)

        sep = ttk.Frame(card, style="Card.TFrame", height=1)
        sep.pack(fill="x", pady=(6, 6))

        self._perm_bits_frame = ttk.Frame(card, style="Card.TFrame")
        self._perm_bits_frame.pack(fill="x")

        self._perm_placeholder = ttk.Label(
            card,
            text="No diagnosis performed yet.",
            style="Dim.TLabel",
        )
        self._perm_placeholder.pack(anchor="w", pady=(4, 0))

    # ── Details Row 2 (File Attributes + Cloud Sync) ────────────────

    def _build_attributes_and_sync_row(self, parent):
        outer = ttk.Frame(parent)
        outer.pack(fill="x", padx=24, pady=(16, 4))
        outer.columnconfigure(0, weight=1)
        outer.columnconfigure(1, weight=1)

        self._build_attribute_panel(outer, row=0, col=0)
        self._build_sync_panel(outer, row=0, col=1)

    def _build_attribute_panel(self, parent, row, col):
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=col, sticky="nsew", padx=(0, 8))

        ttk.Label(frame, text="FILE ATTRIBUTES", style="Heading.TLabel").pack(
            anchor="w", pady=(0, 6),
        )

        card = ttk.Frame(frame, style="Card.TFrame", padding=12)
        card.pack(fill="both", expand=True)

        self._attr_raw_lbl = self._kv_row(card, "Raw Bitmask:", "—", label_width=14)
        self._attr_method_lbl = self._kv_row(card, "Detection:", "—", label_width=14)
        self._attr_effect_lbl = self._kv_row(card, "Effect on Op:", "—", label_width=14)

        sep = ttk.Frame(card, style="Card.TFrame", height=1)
        sep.pack(fill="x", pady=(6, 6))

        self._attr_bits_frame = ttk.Frame(card, style="Card.TFrame")
        self._attr_bits_frame.pack(fill="x")

        self._attr_placeholder = ttk.Label(
            card,
            text="No diagnosis performed yet.",
            style="Dim.TLabel",
        )
        self._attr_placeholder.pack(anchor="w", pady=(6, 0))

    def _build_sync_panel(self, parent, row, col):
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=col, sticky="nsew", padx=(8, 0))

        ttk.Label(frame, text="CLOUD SYNCHRONIZATION", style="Heading.TLabel").pack(
            anchor="w", pady=(0, 6),
        )

        card = ttk.Frame(frame, style="Card.TFrame", padding=12)
        card.pack(fill="both", expand=True)

        self._sync_provider_lbl = self._kv_row(card, "Provider:", "—", label_width=15)
        self._sync_root_lbl = self._kv_row(card, "Sync Root:", "—", label_width=15)
        self._sync_client_lbl = self._kv_row(card, "Client Daemon:", "—", label_width=15)
        self._sync_evidence_lbl = self._kv_row(card, "Evidence Level:", "—", label_width=15)
        self._sync_details_lbl = self._kv_row(card, "Details:", "—", label_width=15)

        self._sync_placeholder = ttk.Label(
            card,
            text="No diagnosis performed yet.",
            style="Dim.TLabel",
        )
        self._sync_placeholder.pack(anchor="w", pady=(6, 0))

    # ── Recommendation Panel ────────────────────────────────────────

    def _build_recommendation_panel(self, parent):
        outer = ttk.Frame(parent)
        outer.pack(fill="x", padx=24, pady=(16, 4))

        ttk.Label(outer, text="RECOMMENDATION", style="Heading.TLabel").pack(
            anchor="w", pady=(0, 6),
        )

        card = ttk.Frame(outer, style="Card.TFrame", padding=16)
        card.pack(fill="x")

        self._rec_label = ttk.Label(
            card,
            text="No recommendation available.",
            style="Card.TLabel",
            wraplength=800,
        )
        self._rec_label.pack(anchor="w")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _kv_row(parent, label_text, value_text, label_width=14, wraplength=420):
        """Create a 'Key: Value' row with top alignment and return the value label."""
        row = ttk.Frame(parent, style="Card.TFrame")
        row.pack(fill="x", pady=2)

        lbl_style = "Card.TLabel"
        ttk.Label(
            row, text=label_text, style=lbl_style,
            font=("Segoe UI", 9, "bold"),
            width=label_width,
        ).pack(side="left", anchor="nw")

        val = ttk.Label(
            row, text=value_text, style=lbl_style,
            wraplength=wraplength, justify="left",
            font=("Segoe UI", 9),
        )
        val.pack(side="left", fill="x", expand=True, anchor="nw")
        return val

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _browse_file(self):
        """Open a native file-selection dialog."""
        path = filedialog.askopenfilename(
            title="Select a file to diagnose",
        )
        if path:
            self._file_var.set(path)

    def _reset_panels(self):
        """Reset all result panels to their initial neutral state."""
        # Status panel
        self._status_badge.configure(
            text="●  WAITING FOR INPUT",
            background=_COLOURS["grey"],
        )
        self._status_file_lbl.configure(text="—")
        self._status_op_lbl.configure(text="—")
        self._status_reason_lbl.configure(
            text="Select a file and operation, then click Diagnose File.",
        )

        # Process list
        for item in self._proc_tree.get_children():
            self._proc_tree.delete(item)
        self._proc_placeholder.configure(text="No diagnosis performed yet.")

        # Permissions
        self._perm_owner_lbl.configure(text="—")
        self._perm_user_lbl.configure(text="—")
        self._perm_method_lbl.configure(text="—")
        for child in self._perm_bits_frame.winfo_children():
            child.destroy()
        self._perm_placeholder.configure(text="No diagnosis performed yet.")

        # File attributes
        self._attr_raw_lbl.configure(text="—")
        self._attr_method_lbl.configure(text="—")
        self._attr_effect_lbl.configure(text="—")
        for child in self._attr_bits_frame.winfo_children():
            child.destroy()
        self._attr_placeholder.configure(text="No diagnosis performed yet.")

        # Cloud sync
        self._sync_provider_lbl.configure(text="—")
        self._sync_root_lbl.configure(text="—")
        self._sync_client_lbl.configure(text="—")
        self._sync_evidence_lbl.configure(text="—")
        self._sync_details_lbl.configure(text="—")
        self._sync_placeholder.configure(text="No diagnosis performed yet.")

        # Recommendation
        self._rec_label.configure(text="No recommendation available.")

    def _run_diagnosis(self):
        """Execute the diagnosis pipeline and populate all telemetry panels."""
        file_path = self._file_var.get().strip()

        # Input validation
        if not file_path:
            messagebox.showwarning(
                "No File Selected",
                "Please select a file before running a diagnosis.",
            )
            return

        selected_op_str = self._op_var.get().strip().lower()
        operation = None
        for op in FileOperation:
            if op.value == selected_op_str:
                operation = op
                break

        if operation is None:
            messagebox.showerror(
                "Invalid Operation",
                f"Unrecognised operation: {self._op_var.get()}",
            )
            return

        # Reliable reset before starting analysis
        self._reset_panels()
        self._status_badge.configure(
            text="●  ANALYZING...",
            background=_COLOURS["accent"],
        )
        self._status_file_lbl.configure(text=file_path)
        self._status_op_lbl.configure(text=operation.value.upper())
        self._status_reason_lbl.configure(text="Running diagnostic analyzers...")
        try:
            self._root.update_idletasks()
        except tk.TclError:
            pass

        # Execute diagnosis engine
        try:
            result = self._engine.diagnose(file_path, operation)
        except Exception as exc:
            self._status_badge.configure(
                text="?  DIAGNOSIS ERROR",
                background=_COLOURS["red"],
            )
            self._status_file_lbl.configure(text=file_path)
            self._status_op_lbl.configure(text=operation.value.upper())
            self._status_reason_lbl.configure(
                text=f"Diagnosis failed due to an unexpected error: {exc}",
            )
            self._rec_label.configure(
                text="Resolve the reported error before attempting to diagnose again.",
            )
            messagebox.showerror(
                "Diagnosis Error",
                f"Unable to diagnose the file.\n\n{exc}",
            )
            return

        # Populate all panels from the DiagnosisResult
        self._update_status(result)
        self._update_process_list(result)
        self._update_permissions(result)
        self._update_attributes(result)
        self._update_sync(result)
        self._update_recommendation(result)

    # ------------------------------------------------------------------
    # Panel updaters
    # ------------------------------------------------------------------

    def _update_status(self, result: DiagnosisResult):
        """Populate the Status Panel from a DiagnosisResult."""
        diag = result.diagnosis
        badge_text, badge_colour = _BADGE_CONFIG.get(
            diag,
            (diag.name.replace("_", " "), _COLOURS["grey"]),
        )

        self._status_badge.configure(
            text=badge_text,
            background=badge_colour,
        )
        self._status_file_lbl.configure(text=result.file_path)
        self._status_op_lbl.configure(text=result.operation.upper())
        self._status_reason_lbl.configure(
            text=result.reason if result.reason else "—",
        )

    def _update_process_list(self, result: DiagnosisResult):
        """Populate the Process List from a DiagnosisResult."""
        for item in self._proc_tree.get_children():
            self._proc_tree.delete(item)

        if result.diagnosis == DiagnosisType.FILE_NOT_FOUND:
            self._proc_placeholder.configure(
                text="File does not exist on disk — lock analysis skipped.",
            )
            return

        lock = result.lock_result
        if lock is None:
            self._proc_placeholder.configure(
                text="Lock check was not performed.",
            )
            return

        if lock.error and lock.detection_method == "error":
            self._proc_placeholder.configure(
                text=f"⚠ Lock check error: {lock.error}",
            )
            return

        if lock.processes:
            self._proc_placeholder.configure(text="")
            for proc in lock.processes:
                self._proc_tree.insert(
                    "",
                    "end",
                    values=(
                        proc.process_name or "(unknown)",
                        proc.pid if proc.pid is not None else "—",
                        proc.executable_path or "—",
                    ),
                )
        elif lock.error:
            self._proc_placeholder.configure(text=f"⚠ {lock.error}")
        else:
            self._proc_placeholder.configure(
                text="✓ No active process locks detected.",
            )

    def _update_permissions(self, result: DiagnosisResult):
        """Populate the Permissions Panel from a DiagnosisResult."""
        for child in self._perm_bits_frame.winfo_children():
            child.destroy()

        if result.diagnosis == DiagnosisType.FILE_NOT_FOUND:
            self._perm_owner_lbl.configure(text="—")
            self._perm_user_lbl.configure(text="—")
            self._perm_method_lbl.configure(text="—")
            self._perm_placeholder.configure(
                text="File does not exist on disk — permission check skipped.",
            )
            return

        perm = result.permission_result
        if perm is None:
            self._perm_owner_lbl.configure(text="—")
            self._perm_user_lbl.configure(text="—")
            self._perm_method_lbl.configure(text="—")
            self._perm_placeholder.configure(
                text="Permission check was not performed.",
            )
            return

        self._perm_owner_lbl.configure(
            text=perm.owner if perm.owner else "(not determined)",
        )
        self._perm_user_lbl.configure(
            text=perm.current_user if perm.current_user else "(unknown)",
        )

        method_text = perm.detection_method or "—"
        if "windows_acl" in method_text or "os_access" in method_text:
            method_text += " (os.access / Win32 owner; full NTFS DACL not evaluated)"
        self._perm_method_lbl.configure(text=method_text)

        if perm.error:
            self._perm_placeholder.configure(text=f"⚠ {perm.error}")
        else:
            self._perm_placeholder.configure(text="")

        if perm.permission_bits:
            for name, allowed in sorted(perm.permission_bits.items()):
                bit_row = ttk.Frame(
                    self._perm_bits_frame, style="Card.TFrame",
                )
                bit_row.pack(fill="x", pady=1)

                if allowed is True:
                    indicator = "✓"
                    colour = _COLOURS["green"]
                    status_text = "Allowed"
                elif allowed is False:
                    indicator = "✗"
                    colour = _COLOURS["red"]
                    status_text = "Denied"
                else:
                    indicator = "?"
                    colour = _COLOURS["grey"]
                    status_text = "Unknown / Unverified"

                ttk.Label(
                    bit_row,
                    text=f"  {indicator}  {name.upper()}",
                    style="PermBit.TLabel",
                    foreground=colour,
                    width=20,
                ).pack(side="left")

                ttk.Label(
                    bit_row,
                    text=status_text,
                    style="PermBit.TLabel",
                    foreground=colour,
                ).pack(side="left")

    def _update_attributes(self, result: DiagnosisResult):
        """Populate the File Attributes panel from a DiagnosisResult."""
        for child in self._attr_bits_frame.winfo_children():
            child.destroy()

        if result.diagnosis == DiagnosisType.FILE_NOT_FOUND:
            self._attr_raw_lbl.configure(text="—")
            self._attr_method_lbl.configure(text="—")
            self._attr_effect_lbl.configure(text="—")
            self._attr_placeholder.configure(
                text="File does not exist on disk — attribute check skipped.",
            )
            return

        attr = result.attribute_result
        if attr is None:
            self._attr_raw_lbl.configure(text="—")
            self._attr_method_lbl.configure(text="—")
            self._attr_effect_lbl.configure(text="—")
            self._attr_placeholder.configure(
                text="Attribute check was not performed.",
            )
            return

        # Raw bitmask
        if attr.raw_attributes is not None:
            self._attr_raw_lbl.configure(text=f"0x{attr.raw_attributes:04X} ({attr.raw_attributes})")
        else:
            self._attr_raw_lbl.configure(text="—")

        # Detection method
        self._attr_method_lbl.configure(text=attr.detection_method or "—")

        # Operational effect
        op_str = (result.operation or "").lower()
        if attr.error and attr.detection_method == "error":
            self._attr_effect_lbl.configure(
                text=f"Inspection failed ({attr.error}); attribute restrictions undetermined.",
            )
        elif attr.is_readonly is True:
            if op_str in ("write", "delete"):
                self._attr_effect_lbl.configure(
                    text=f"Read-only attribute is set; prevents {op_str.upper()} operations.",
                )
            else:
                self._attr_effect_lbl.configure(
                    text=f"Read-only attribute is set, but does not block {op_str.upper()} operations.",
                )
        elif attr.is_readonly is False:
            self._attr_effect_lbl.configure(
                text=f"No attribute restrictions blocking {op_str.upper()} operation.",
            )
        else:
            self._attr_effect_lbl.configure(
                text="Attribute status is unknown or unavailable on this platform.",
            )

        if attr.error:
            self._attr_placeholder.configure(text=f"⚠ {attr.error}")
        else:
            self._attr_placeholder.configure(text="")

        # 6 attribute flags
        flag_defs = [
            ("Read-only", attr.is_readonly),
            ("Hidden", attr.is_hidden),
            ("System", attr.is_system),
            ("Archive", attr.is_archive),
            ("Reparse Point", attr.is_reparse_point),
            ("Offline", attr.is_offline),
        ]

        for i, (flag_name, flag_val) in enumerate(flag_defs):
            row_idx = i // 2
            col_idx = i % 2

            cell = ttk.Frame(self._attr_bits_frame, style="Card.TFrame")
            cell.grid(
                row=row_idx,
                column=col_idx,
                sticky="w",
                padx=(0 if col_idx == 0 else 16, 8),
                pady=2,
            )

            if flag_val is True:
                symbol = "●"
                val_text = "Yes"
                val_colour = _COLOURS["orange"] if flag_name == "Read-only" else _COLOURS["accent"]
            elif flag_val is False:
                symbol = "○"
                val_text = "No"
                val_colour = _COLOURS["fg_dim"]
            else:
                symbol = "?"
                val_text = "Unknown / Unavailable"
                val_colour = _COLOURS["grey"]

            ttk.Label(
                cell,
                text=f"{flag_name}:",
                style="Card.TLabel",
                font=("Segoe UI", 9, "bold"),
                width=13,
            ).pack(side="left")

            ttk.Label(
                cell,
                text=f"{symbol}  {val_text}",
                style="Card.TLabel",
                foreground=val_colour,
                font=("Segoe UI", 9),
            ).pack(side="left")

    def _update_sync(self, result: DiagnosisResult):
        """Populate the Cloud Synchronization panel from a DiagnosisResult."""
        if result.diagnosis == DiagnosisType.FILE_NOT_FOUND:
            self._sync_provider_lbl.configure(text="—")
            self._sync_root_lbl.configure(text="—")
            self._sync_client_lbl.configure(text="—")
            self._sync_evidence_lbl.configure(text="—")
            self._sync_details_lbl.configure(text="—")
            self._sync_placeholder.configure(
                text="File does not exist on disk — sync check skipped.",
            )
            return

        sync = result.sync_result
        if sync is None:
            self._sync_provider_lbl.configure(text="—")
            self._sync_root_lbl.configure(text="—")
            self._sync_client_lbl.configure(text="—")
            self._sync_evidence_lbl.configure(text="—")
            self._sync_details_lbl.configure(text="—")
            self._sync_placeholder.configure(
                text="Sync check was not performed.",
            )
            return

        # Provider (strictly OneDrive and Google Drive)
        prov_key = (sync.provider or "").lower()
        prov_display = SYNC_PROVIDER_NAMES.get(
            prov_key,
            "No provider identified" if not prov_key else sync.provider,
        )
        self._sync_provider_lbl.configure(text=prov_display)

        # Sync root
        self._sync_root_lbl.configure(text=sync.sync_root if sync.sync_root else "—")

        # Client daemon
        if sync.is_synced:
            client_status = (
                "Running (active background process)"
                if sync.client_running
                else "Not running / Not detected"
            )
        else:
            if prov_key:
                client_status = "Running" if sync.client_running else "Not running"
            else:
                client_status = "— (no sync provider associated)"
        self._sync_client_lbl.configure(text=client_status)

        # Evidence level
        ev_label = SYNC_EVIDENCE_LABELS.get(
            sync.evidence_level,
            sync.evidence_level or "None",
        )
        self._sync_evidence_lbl.configure(text=ev_label)

        # Details
        details_text = sync.details or "—"
        if sync.locking_process:
            p = sync.locking_process
            details_text += f" (Locker: {p.process_name or '(unknown)'}, PID {p.pid})"
        self._sync_details_lbl.configure(text=details_text)

        if sync.error:
            self._sync_placeholder.configure(text=f"⚠ {sync.error}")
        else:
            self._sync_placeholder.configure(text="")

    def _update_recommendation(self, result: DiagnosisResult):
        """Populate the Recommendation Panel from a DiagnosisResult."""
        action = result.suggested_action
        if action:
            self._rec_label.configure(text=action)
        else:
            if result.diagnosis == DiagnosisType.OPERATION_ALLOWED:
                self._rec_label.configure(
                    text="✓ No issues detected — the requested operation is permitted.",
                )
            else:
                self._rec_label.configure(
                    text="No recommendation available.",
                )
