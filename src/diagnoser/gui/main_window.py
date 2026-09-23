"""
Main Window — Tkinter Desktop GUI for the File Operation Failure Diagnoser.

This module provides the first functional GUI prototype.  It is a pure
presentation layer on top of the existing DiagnosisEngine.  It never
calls Windows APIs or performs OS-level analysis directly.

Architecture:
    USER  →  MainWindow  →  DiagnosisEngine  →  Analyzers  →  Results  →  GUI

Launch:
    python -m diagnoser.gui.app
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from diagnoser.engine.diagnosis import DiagnosisEngine
from diagnoser.models import DiagnosisType, FileOperation


# ======================================================================
# Colour palette
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
    "orange":           "#e8a54b",      # warning / read-only / not found
    "grey":             "#7a7a9a",      # unknown / coming soon
    "border":           "#3d3d57",      # card borders
}

_BADGE_COLOURS = {
    DiagnosisType.OPERATION_ALLOWED:   _COLOURS["green"],
    DiagnosisType.FILE_LOCKED:         _COLOURS["red"],
    DiagnosisType.PERMISSION_DENIED:   _COLOURS["red"],
    DiagnosisType.READ_ONLY:           _COLOURS["orange"],
    DiagnosisType.FILE_NOT_FOUND:      _COLOURS["orange"],
    DiagnosisType.UNKNOWN_ERROR:       _COLOURS["grey"],
}


# ======================================================================
# MainWindow
# ======================================================================

class MainWindow:
    """Tkinter main application window.

    Provides file selection, operation selection, a Diagnose button,
    and result panels for status, processes, permissions,
    recommendations, and future-feature placeholders.

    Usage:
        window = MainWindow()
        window.run()
    """

    _WINDOW_TITLE = "File Operation Failure Diagnoser"
    _MIN_WIDTH = 860
    _MIN_HEIGHT = 780

    def __init__(self):
        self._engine = DiagnosisEngine()

        # ── Root window ─────────────────────────────────────────────
        self._root = tk.Tk()
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
            "ComingSoon.TLabel",
            background=_COLOURS["bg_card"],
            foreground=_COLOURS["orange"],
            font=("Segoe UI", 9, "bold"),
        )
        s.configure(
            "PermBit.TLabel",
            background=_COLOURS["bg_card"],
            foreground=_COLOURS["fg"],
            font=("Segoe UI", 10),
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
        scrollbar = ttk.Scrollbar(
            self._root, orient="vertical", command=canvas.yview,
        )
        self._scroll_frame = ttk.Frame(canvas, style="TFrame")
        self._scroll_frame.configure(style="TFrame")
        self._style.configure("TFrame", background=_COLOURS["bg"])

        self._scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        self._canvas_window = canvas.create_window(
            (0, 0), window=self._scroll_frame, anchor="nw",
        )
        canvas.configure(yscrollcommand=scrollbar.set)

        # Stretch the inner frame to fill the canvas width so children centre naturally
        def _sync_frame_width(event):
            canvas.itemconfigure(self._canvas_window, width=event.width)
        canvas.bind("<Configure>", _sync_frame_width)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Bind mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        # Linux scroll
        canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))

        container = self._scroll_frame

        # ── Header ──────────────────────────────────────────────────
        self._build_header(container)

        # ── File Input ──────────────────────────────────────────────
        self._build_file_input(container)

        # ── Operation Selection ─────────────────────────────────────
        self._build_operation_selector(container)

        # ── Diagnose Button ─────────────────────────────────────────
        self._build_diagnose_button(container)

        # ── Status Panel ────────────────────────────────────────────
        self._build_status_panel(container)

        # ── Process List + Permissions (side by side) ───────────────
        self._build_details_row(container)

        # ── Recommendation Panel ────────────────────────────────────
        self._build_recommendation_panel(container)

        # ── Future Features ─────────────────────────────────────────
        self._build_future_features(container)

        # ── Footer padding ──────────────────────────────────────────
        ttk.Frame(container, height=20).pack(fill="x")

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
            text="Diagnose why a file operation may fail.",
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

        # Populate from the real FileOperation enum
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

        # Badge (diagnosis type)
        self._status_badge = ttk.Label(
            card, text="WAITING FOR INPUT", style="Badge.TLabel",
        )
        self._status_badge.pack(anchor="w", pady=(0, 10))

        # Info grid: File, Operation, Reason
        info = ttk.Frame(card, style="Card.TFrame")
        info.pack(fill="x")

        self._status_file_lbl = self._kv_row(info, "File:", "—")
        self._status_op_lbl = self._kv_row(info, "Operation:", "—")
        self._status_reason_lbl = self._kv_row(info, "Reason:", "Select a file and operation, then click Diagnose File.")

    # ── Details Row (Process List + Permissions) ────────────────────

    def _build_details_row(self, parent):
        outer = ttk.Frame(parent)
        outer.pack(fill="x", padx=24, pady=(16, 4))

        # Use grid for side-by-side layout
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

        # Treeview for process list
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

        self._perm_card = card

        # Owner / User / Detection method
        self._perm_owner_lbl = self._kv_row(card, "Owner:", "—", card_style=True)
        self._perm_user_lbl = self._kv_row(card, "Current User:", "—", card_style=True)
        self._perm_method_lbl = self._kv_row(card, "Detection:", "—", card_style=True)

        # Permission bits
        sep = ttk.Frame(card, style="Card.TFrame", height=1)
        sep.pack(fill="x", pady=(8, 8))

        self._perm_bits_frame = ttk.Frame(card, style="Card.TFrame")
        self._perm_bits_frame.pack(fill="x")

        self._perm_placeholder = ttk.Label(
            card,
            text="No diagnosis performed yet.",
            style="Dim.TLabel",
        )
        self._perm_placeholder.pack(anchor="w", pady=(4, 0))

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
            wraplength=750,
        )
        self._rec_label.pack(anchor="w")

    # ── Future Features ─────────────────────────────────────────────

    def _build_future_features(self, parent):
        outer = ttk.Frame(parent)
        outer.pack(fill="x", padx=24, pady=(16, 4))

        ttk.Label(outer, text="FUTURE FEATURES", style="Heading.TLabel").pack(
            anchor="w", pady=(0, 6),
        )

        card = ttk.Frame(outer, style="Card.TFrame", padding=16)
        card.pack(fill="x")

        # File Attribute Analysis
        self._future_item(
            card,
            icon="🔒",
            title="File Attribute Analysis",
            description="Read-only, hidden, system, and archive attribute detection.",
        )

        ttk.Frame(card, style="Card.TFrame", height=12).pack(fill="x")

        # Cloud Sync Detection
        self._future_item(
            card,
            icon="☁",
            title="Cloud Sync Detection",
            description="OneDrive / Google Drive / Dropbox activity detection.",
        )

    def _future_item(self, parent, icon, title, description):
        """Render a single future-feature placeholder row."""
        row = ttk.Frame(parent, style="Card.TFrame")
        row.pack(fill="x")

        ttk.Label(
            row,
            text=f"{icon}  {title}",
            style="Card.TLabel",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")

        ttk.Label(
            row, text="COMING SOON", style="ComingSoon.TLabel",
        ).pack(side="right")

        desc_row = ttk.Frame(parent, style="Card.TFrame")
        desc_row.pack(fill="x")
        ttk.Label(
            desc_row, text=description, style="Dim.TLabel",
        ).pack(anchor="w", padx=(28, 0), pady=(2, 0))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _kv_row(parent, label_text, value_text, card_style=False):
        """Create a 'Key: Value' row and return the value label."""
        row = ttk.Frame(
            parent,
            style="Card.TFrame" if card_style else "Card.TFrame",
        )
        row.pack(fill="x", pady=2)

        lbl_style = "Card.TLabel"
        ttk.Label(
            row, text=label_text, style=lbl_style,
            font=("Segoe UI", 10, "bold"),
            width=14,
        ).pack(side="left")

        val = ttk.Label(
            row, text=value_text, style=lbl_style,
            wraplength=500, justify="left",
        )
        val.pack(side="left", fill="x", expand=True)
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

    def _run_diagnosis(self):
        """Execute the diagnosis pipeline and update all panels."""
        file_path = self._file_var.get().strip()

        # ── Input validation ────────────────────────────────────────
        if not file_path:
            messagebox.showwarning(
                "No File Selected",
                "Please select a file before running a diagnosis.",
            )
            return

        # ── Map the selected operation to the FileOperation enum ────
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

        # ── Run the existing DiagnosisEngine ────────────────────────
        try:
            result = self._engine.diagnose(file_path, operation)
        except Exception as exc:
            messagebox.showerror(
                "Diagnosis Error",
                f"Unable to diagnose the file.\n\n{exc}",
            )
            return

        # ── Populate all panels from the DiagnosisResult ────────────
        self._update_status(result)
        self._update_process_list(result)
        self._update_permissions(result)
        self._update_recommendation(result)

    # ------------------------------------------------------------------
    # Panel updaters
    # ------------------------------------------------------------------

    def _update_status(self, result):
        """Populate the Status Panel from a DiagnosisResult."""
        diag = result.diagnosis
        badge_text = diag.name.replace("_", " ")
        badge_colour = _BADGE_COLOURS.get(diag, _COLOURS["grey"])

        self._status_badge.configure(
            text=badge_text,
            background=badge_colour,
        )
        self._status_file_lbl.configure(text=result.file_path)
        self._status_op_lbl.configure(text=result.operation.upper())
        self._status_reason_lbl.configure(
            text=result.reason if result.reason else "—",
        )

    def _update_process_list(self, result):
        """Populate the Process List from a DiagnosisResult."""
        # Clear existing rows
        for item in self._proc_tree.get_children():
            self._proc_tree.delete(item)

        lock = result.lock_result
        if lock is not None and lock.processes:
            self._proc_placeholder.configure(text="")
            for proc in lock.processes:
                self._proc_tree.insert("", "end", values=(
                    proc.process_name or "(unknown)",
                    proc.pid,
                    proc.executable_path or "—",
                ))
        elif lock is not None and lock.error:
            self._proc_placeholder.configure(text=lock.error)
        elif lock is not None:
            self._proc_placeholder.configure(
                text="No locking process detected.",
            )
        else:
            self._proc_placeholder.configure(
                text="Lock check was not performed.",
            )

    def _update_permissions(self, result):
        """Populate the Permissions Panel from a DiagnosisResult."""
        perm = result.permission_result

        # Clear old permission bits
        for child in self._perm_bits_frame.winfo_children():
            child.destroy()

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
        self._perm_method_lbl.configure(
            text=perm.detection_method if perm.detection_method else "—",
        )

        if perm.error:
            self._perm_placeholder.configure(text=perm.error)
        else:
            self._perm_placeholder.configure(text="")

        # Permission bits (read, write, execute)
        if perm.permission_bits:
            for name, allowed in sorted(perm.permission_bits.items()):
                bit_row = ttk.Frame(
                    self._perm_bits_frame, style="Card.TFrame",
                )
                bit_row.pack(fill="x", pady=1)

                indicator = "✓" if allowed else "✗"
                colour = _COLOURS["green"] if allowed else _COLOURS["red"]
                status_text = "Allowed" if allowed else "Denied"

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

    def _update_recommendation(self, result):
        """Populate the Recommendation Panel from a DiagnosisResult."""
        action = result.suggested_action
        if action:
            self._rec_label.configure(text=action)
        else:
            if result.diagnosis == DiagnosisType.OPERATION_ALLOWED:
                self._rec_label.configure(
                    text="No issues detected — the operation is permitted.",
                )
            else:
                self._rec_label.configure(
                    text="No recommendation available.",
                )
