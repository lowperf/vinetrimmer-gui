import json
import os
import queue
import signal
import shlex
import subprocess
import sys
import threading
from datetime import datetime
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox, filedialog


DEFAULT_OPTION = "default"
SETTINGS_FILE = "vinetrimmer_command_gui_settings.json"
NETFLIX_LANGUAGE_OPTIONS = [
    "all", "af", "ar", "ar-SA", "bg", "bn", "ca", "cs", "da", "de", "el",
    "en", "en-GB", "en-US", "es", "es-419", "es-ES", "et", "eu", "fa",
    "fi", "fil", "fr", "fr-CA", "fr-FR", "gl", "he", "hi", "hr", "hu",
    "id", "is", "it", "ja", "ko", "lt", "lv", "ms", "nb", "nl", "pl",
    "pt", "pt-BR", "pt-PT", "ro", "ru", "sk", "sl", "sr", "sv", "ta",
    "te", "th", "tr", "uk", "vi", "zh", "zh-Hans", "zh-Hant"
]


class ScrollableFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        canvas = self.canvas
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.scrollable = ttk.Frame(canvas)

        self.scrollable.bind(
            "<Configure>",
            lambda event: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        window_id = canvas.create_window((0, 0), window=self.scrollable, anchor="nw")

        def resize_inner(event):
            canvas.itemconfig(window_id, width=event.width)

        canvas.bind("<Configure>", resize_inner)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def scroll_mousewheel(self, event):
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")
        else:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"


class VinetrimmerCommandGUI(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Vinetrimmer Command GUI")
        self.geometry("1220x620")
        self.minsize(1080, 720)

        self.base_command_var = tk.StringVar(value="poetry run vt dl")
        self.platform_var = tk.StringVar(value="github.com/lowperf")
        self.link_id_var = tk.StringVar(value="")
        self.output_folder_var = tk.StringVar(value=os.getcwd())
        self.filename_var = tk.StringVar(value="vinetrimmer_command")

        self.profile_var = tk.StringVar(value="")
        self.drm_playready_var = tk.BooleanVar(value=False)
        self.hydrate_var = tk.BooleanVar(value=False)
        self.quality_var = tk.StringVar(value="best")
        self.vcodec_var = tk.StringVar(value=DEFAULT_OPTION)
        self.acodec_var = tk.StringVar(value=DEFAULT_OPTION)
        self.vbitrate_var = tk.StringVar(value="")
        self.abitrate_var = tk.StringVar(value="")
        self.audio_boost_var = tk.StringVar(value="none")
        self.channels_var = tk.StringVar(value=DEFAULT_OPTION)
        self.adub_var = tk.StringVar(value=DEFAULT_OPTION)
        self.chdub_var = tk.StringVar(value=DEFAULT_OPTION)
        self.range_var = tk.StringVar(value=DEFAULT_OPTION)
        self.wanted_var = tk.StringVar(value="")
        self.sd_var = tk.StringVar(value="")
        self.scc_var = tk.StringVar(value="")
        self.ssdh_var = tk.StringVar(value="")
        self.sfc_var = tk.StringVar(value="")
        self.delay_var = tk.StringVar(value="")

        self.atmos_var = tk.BooleanVar(value=False)
        self.audio_only_var = tk.BooleanVar(value=False)
        self.subs_only_var = tk.BooleanVar(value=False)
        self.chapters_only_var = tk.BooleanVar(value=False)
        self.no_subs_var = tk.BooleanVar(value=False)
        self.no_audio_var = tk.BooleanVar(value=False)
        self.no_video_var = tk.BooleanVar(value=False)
        self.no_chapters_var = tk.BooleanVar(value=False)
        self.audio_description_var = tk.BooleanVar(value=False)
        self.list_var = tk.BooleanVar(value=False)
        self.selected_var = tk.BooleanVar(value=False)
        self.no_mux_var = tk.BooleanVar(value=False)
        self.mux_var = tk.BooleanVar(value=False)
        self.worst_var = tk.BooleanVar(value=False)
        self.no_forced_var = tk.BooleanVar(value=False)
        self.language_options = NETFLIX_LANGUAGE_OPTIONS
        self.audio_language_vars = {
            language: tk.BooleanVar(value=(language == ""))
            for language in self.language_options
        }
        self.subtitle_language_vars = {
            language: tk.BooleanVar(value=(language == ""))
            for language in self.language_options
        }

        self.is_running = False
        self.process = None
        self.output_thread = None
        self.stop_thread = None
        self.log_queue = queue.Queue()
        self.log_poll_job = None
        self.stop_requested = False

        self.load_settings()
        self._build_ui()
        self._bind_auto_preview()
        self.generate_preview()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self):
        root = ttk.Frame(self, padding=16)
        root.pack(fill="both", expand=True)

        ttk.Label(root, text="Vinetrimmer Command GUI", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(
            root,
            text="",
            foreground="#555555"
        ).pack(anchor="w", pady=(1, 1))

        main = ttk.Frame(root)
        main.pack(fill="both", expand=True)

        left_panel = ttk.Frame(main)
        left_panel.pack(side="left", fill="both", expand=True)

        right_panel = ttk.Frame(main)
        right_panel.pack(side="right", fill="both", expand=True, padx=(14, 0))

        scroll = ScrollableFrame(left_panel)
        self.form_scroll = scroll
        scroll.pack(fill="both", expand=True)
        form = scroll.scrollable

        self._build_basic_section(form)
        self._build_video_audio_section(form)
        self._build_language_subtitle_section(form)
        self._build_track_mode_section(form)
        self._build_save_section(form)
        self._bind_form_scroll_mousewheel(form)
        self._build_preview_logs(right_panel)

        self.status_var = tk.StringVar(value="Status: siap")
        ttk.Label(root, textvariable=self.status_var, foreground="#555555").pack(anchor="w", pady=(10, 0))

    def _build_basic_section(self, parent):
        frame = ttk.LabelFrame(parent, text="Command Dasar dan Sumber")
        frame.pack(fill="x", pady=(0, 10))

        self._label(frame, "Platform", 0)
        ttk.Combobox(
            frame,
            textvariable=self.platform_var,
            values=["netflix", "HBOMax", "amazon", "appletvplus", "DisneyPlus", "CanalPlus", "HULU", "itunes", "NOW", "paramountplus", "peacock", "Skyshowtime", "TimVision"],
            state="readonly"
        ).grid(row=0, column=1, sticky="ew", padx=10, pady=7)

        self._label(frame, "Link / ID", 1)
        ttk.Entry(frame, textvariable=self.link_id_var).grid(row=1, column=1, sticky="ew", padx=10, pady=7)

        self._label(frame, "Profile (-p)", 2)
        ttk.Entry(frame, textvariable=self.profile_var).grid(row=2, column=1, sticky="ew", padx=10, pady=7)

        option_frame = ttk.LabelFrame(frame, text="Opsi DRM dan Hydrate")
        option_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=10, pady=(7, 10))

        ttk.Checkbutton(
            option_frame,
            text="Aktifkan DRM PlayReady (-drm playready)",
            variable=self.drm_playready_var
        ).pack(anchor="w", padx=10, pady=(8, 4))

        ttk.Checkbutton(
            option_frame,
            text="Aktifkan Hydrate (--hydrate)",
            variable=self.hydrate_var
        ).pack(anchor="w", padx=10, pady=(4, 8))

        frame.columnconfigure(1, weight=1)

    def _build_video_audio_section(self, parent):
        frame = ttk.LabelFrame(parent, text="Video dan Audio")
        frame.pack(fill="x", pady=(0, 10))

        self._label(frame, "Quality (-q)", 0)
        ttk.Combobox(frame, textvariable=self.quality_var, values=["best", "360", "480", "720", "1080", "1440", "2160"], state="readonly").grid(row=0, column=1, sticky="ew", padx=10, pady=7)

        self._label(frame, "Video codec (-v)", 1)
        ttk.Combobox(frame, textvariable=self.vcodec_var, values=[DEFAULT_OPTION, "h264", "h265", "av1", "vp9"], state="readonly").grid(row=1, column=1, sticky="ew", padx=10, pady=7)

        self._label(frame, "Audio codec (-a)", 2)
        ttk.Combobox(frame, textvariable=self.acodec_var, values=[DEFAULT_OPTION, "aac", "eac3", "ac3", "opus"], state="readonly").grid(row=2, column=1, sticky="ew", padx=10, pady=7)

        self._label(frame, "Video bitrate (-vb)", 3)
        ttk.Entry(frame, textvariable=self.vbitrate_var).grid(row=3, column=1, sticky="ew", padx=10, pady=7)

        self._label(frame, "Audio bitrate (-ab)", 4)
        ttk.Entry(frame, textvariable=self.abitrate_var).grid(row=4, column=1, sticky="ew", padx=10, pady=7)

        self._label(frame, "Audio boost (-abo)", 5)
        ttk.Combobox(frame, textvariable=self.audio_boost_var, values=["none", "normal", "medium", "high"], state="readonly").grid(row=5, column=1, sticky="ew", padx=10, pady=7)

        ttk.Checkbutton(frame, text="Prefer Atmos Audio (-aa / --atmos)", variable=self.atmos_var).grid(row=6, column=0, columnspan=2, sticky="w", padx=10, pady=7)

        self._label(frame, "Audio channels (-ch)", 7)
        ttk.Combobox(frame, textvariable=self.channels_var, values=[DEFAULT_OPTION, "2.0", "5.1", "7.1"], state="readonly").grid(row=7, column=1, sticky="ew", padx=10, pady=7)

        self._label(frame, "Dubbed audio codec (-adub)", 8)
        ttk.Combobox(frame, textvariable=self.adub_var, values=[DEFAULT_OPTION, "aac", "eac3", "ac3", "opus"], state="readonly").grid(row=8, column=1, sticky="ew", padx=10, pady=7)

        self._label(frame, "Dubbed channels (-chdub)", 9)
        ttk.Combobox(frame, textvariable=self.chdub_var, values=[DEFAULT_OPTION, "2.0", "5.1", "7.1"], state="readonly").grid(row=9, column=1, sticky="ew", padx=10, pady=7)

        self._label(frame, "Color range (-r)", 10)
        ttk.Combobox(frame, textvariable=self.range_var, values=[DEFAULT_OPTION, "SDR", "HDR10", "DV"], state="readonly").grid(row=10, column=1, sticky="ew", padx=10, pady=7)

        self._label(frame, "Wanted episode (-w)", 11)
        ttk.Entry(frame, textvariable=self.wanted_var).grid(row=11, column=1, sticky="ew", padx=10, pady=7)

        self._label(frame, "Delay (--delay)", 12)
        ttk.Entry(frame, textvariable=self.delay_var).grid(row=12, column=1, sticky="ew", padx=10, pady=7)

        frame.columnconfigure(1, weight=1)

    def _build_language_subtitle_section(self, parent):
        frame = ttk.LabelFrame(parent, text="Bahasa, Subtitle, dan Filter Subtitle")
        frame.pack(fill="x", pady=(0, 10))

        ttk.Label(frame, text="Audio language (-al)").grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(8, 2))
        self._build_language_toggles(frame, self.audio_language_vars, 1)

        ttk.Label(frame, text="Subtitle language (-sl)").grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 2))
        self._build_language_toggles(frame, self.subtitle_language_vars, 3)

        self._label(frame, "Default subtitle (--sd)", 4)
        ttk.Entry(frame, textvariable=self.sd_var).grid(row=4, column=1, sticky="ew", padx=10, pady=7)

        self._label(frame, "CC subtitle (--scc)", 5)
        ttk.Entry(frame, textvariable=self.scc_var).grid(row=5, column=1, sticky="ew", padx=10, pady=7)

        self._label(frame, "SDH subtitle (--ssdh)", 6)
        ttk.Entry(frame, textvariable=self.ssdh_var).grid(row=6, column=1, sticky="ew", padx=10, pady=7)

        self._label(frame, "Forced subtitle (--sfc)", 7)
        ttk.Entry(frame, textvariable=self.sfc_var).grid(row=7, column=1, sticky="ew", padx=10, pady=7)

        frame.columnconfigure(1, weight=1)

    def _build_language_toggles(self, parent, variables, row):
        toggle_frame = ttk.Frame(parent)
        toggle_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 6))

        columns = 6
        for index, language in enumerate(self.language_options):
            ttk.Checkbutton(
                toggle_frame,
                text=language,
                variable=variables[language]
            ).grid(row=index // columns, column=index % columns, sticky="w", padx=(0, 12), pady=2)

    def _build_track_mode_section(self, parent):
        frame = ttk.LabelFrame(parent, text="Mode Track dan Output")
        frame.pack(fill="x", pady=(0, 10))

        options = [
            ("Audio only (-A)", self.audio_only_var),
            ("Subs only (-S)", self.subs_only_var),
            ("Chapters only (-C)", self.chapters_only_var),
            ("No subtitles (-ns)", self.no_subs_var),
            ("No audio (-na)", self.no_audio_var),
            ("No video (-nv)", self.no_video_var),
            ("No chapters (-nc)", self.no_chapters_var),
            ("Audio description (-ad)", self.audio_description_var),
            ("List available tracks (--list)", self.list_var),
            ("List selected tracks (--selected)", self.selected_var),
            ("No mux (-nm)", self.no_mux_var),
            ("Force mux (--mux)", self.mux_var),
            ("Worst quality (--worst)", self.worst_var),
            ("No forced subtitles (-nf)", self.no_forced_var),
        ]

        for index, (text, variable) in enumerate(options):
            row = index // 2
            col = index % 2
            ttk.Checkbutton(frame, text=text, variable=variable).grid(row=row, column=col, sticky="w", padx=10, pady=6)

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

    def _build_save_section(self, parent):
        frame = ttk.LabelFrame(parent, text="Penyimpanan")
        frame.pack(fill="x", pady=(0, 10))

        self._label(frame, "Folder output", 0)
        folder_row = ttk.Frame(frame)
        folder_row.grid(row=0, column=1, sticky="ew", padx=10, pady=7)
        ttk.Entry(folder_row, textvariable=self.output_folder_var).pack(side="left", fill="x", expand=True)
        ttk.Button(folder_row, text="Pilih", command=self.choose_folder).pack(side="left", padx=(8, 0))

        self._label(frame, "Nama file", 1)
        ttk.Entry(frame, textvariable=self.filename_var).grid(row=1, column=1, sticky="ew", padx=10, pady=7)

        frame.columnconfigure(1, weight=1)

    def _build_preview_logs(self, parent):
        terminal_font = (self._terminal_font_family(), 10)

        preview_frame = ttk.LabelFrame(parent, text="Preview Command")
        preview_frame.pack(fill="both", expand=True, pady=(0, 12))

        self.preview_text = tk.Text(preview_frame, wrap="word", font=terminal_font, height=6)
        self.preview_text.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)

        preview_scroll = ttk.Scrollbar(preview_frame, orient="vertical", command=self.preview_text.yview)
        preview_scroll.pack(side="right", fill="y", padx=(0, 10), pady=10)
        self.preview_text.configure(yscrollcommand=preview_scroll.set)

        run_row = ttk.Frame(parent)
        run_row.pack(fill="x", pady=(0, 12))

        ttk.Button(run_row, text="Copy Command", command=self.copy_command).pack(side="left")

        self.run_button = ttk.Button(run_row, text="Run Command", command=self.run_command)
        self.run_button.pack(side="left", padx=(8, 0))

        self.stop_button = ttk.Button(run_row, text="Stop", command=self.stop_command, state="disabled")
        self.stop_button.pack(side="left", padx=(8, 0))

        ttk.Button(run_row, text="Save Logs", command=self.save_logs).pack(side="left", padx=(8, 0))
        ttk.Button(run_row, text="Clear Logs", command=self.clear_logs).pack(side="left", padx=(8, 0))
        ttk.Button(run_row, text="Open Downloads", command=self.open_downloads_folder).pack(side="left", padx=(8, 0))
        ttk.Button(run_row, text="Reset", command=self.reset_form).pack(side="left", padx=(8, 0))

        logs_frame = ttk.LabelFrame(parent, text="Logs Command")
        logs_frame.pack(fill="both", expand=True)

        self.logs_text = tk.Text(
            logs_frame,
            wrap="word",
            font=terminal_font,
            height=30,
            background="#0c0c0c",
            foreground="#cccccc",
            insertbackground="#ffffff",
            selectbackground="#264f78",
            selectforeground="#ffffff",
            relief="flat",
            borderwidth=0
        )
        self.logs_text.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        self._configure_log_tags()

        logs_scroll = ttk.Scrollbar(logs_frame, orient="vertical", command=self.logs_text.yview)
        logs_scroll.pack(side="right", fill="y", padx=(0, 10), pady=10)
        self.logs_text.configure(yscrollcommand=logs_scroll.set)

    def _terminal_font_family(self):
        available_fonts = {font.lower() for font in tkfont.families(self)}
        for font in ("Cascadia Mono", "Cascadia Code", "Consolas"):
            if font.lower() in available_fonts:
                return font
        return "TkFixedFont"

    def _configure_log_tags(self):
        self.logs_text.tag_configure("timestamp", foreground="#6a9955")
        self.logs_text.tag_configure("normal", foreground="#cccccc")
        self.logs_text.tag_configure("command", foreground="#4fc1ff")
        self.logs_text.tag_configure("working_dir", foreground="#c586c0")
        self.logs_text.tag_configure("success", foreground="#b5cea8")
        self.logs_text.tag_configure("warning", foreground="#dcdcaa")
        self.logs_text.tag_configure("error", foreground="#f44747")
        self.logs_text.tag_configure("stop", foreground="#ce9178")

    def _label(self, parent, text, row):
        ttk.Label(parent, text=text).grid(row=row, column=0, sticky="w", padx=10, pady=7)

    def _bind_form_scroll_mousewheel(self, widget):
        widget.bind("<MouseWheel>", self._scroll_form_mousewheel)
        widget.bind("<Button-4>", self._scroll_form_mousewheel)
        widget.bind("<Button-5>", self._scroll_form_mousewheel)

        for child in widget.winfo_children():
            self._bind_form_scroll_mousewheel(child)

    def _scroll_form_mousewheel(self, event):
        return self.form_scroll.scroll_mousewheel(event)

    def _bind_auto_preview(self):
        variables = [
            self.platform_var, self.link_id_var, self.profile_var,
            self.drm_playready_var, self.hydrate_var, self.quality_var,
            self.vcodec_var, self.acodec_var, self.vbitrate_var, self.abitrate_var,
            self.audio_boost_var, self.channels_var, self.adub_var, self.chdub_var,
            self.range_var, self.wanted_var, self.sd_var, self.scc_var,
            self.ssdh_var, self.sfc_var, self.delay_var, self.atmos_var,
            self.audio_only_var, self.subs_only_var, self.chapters_only_var,
            self.no_subs_var, self.no_audio_var, self.no_video_var,
            self.no_chapters_var, self.audio_description_var, self.list_var,
            self.selected_var, self.no_mux_var, self.mux_var, self.worst_var,
            self.no_forced_var
        ]
        variables.extend(self.audio_language_vars.values())
        variables.extend(self.subtitle_language_vars.values())

        for variable in variables:
            variable.trace_add("write", self._schedule_preview_update)

    def _schedule_preview_update(self, *_args):
        if hasattr(self, "preview_text"):
            self.after_idle(self.generate_preview)

    def choose_folder(self):
        folder = filedialog.askdirectory(title="Pilih folder output")
        if folder:
            self.output_folder_var.set(folder)

    def add_option(self, parts, flag, value):
        value = str(value).strip()
        if value == DEFAULT_OPTION:
            return
        if value:
            parts.extend([flag, value])

    def add_bool(self, parts, flag, enabled):
        if enabled:
            parts.append(flag)

    def selected_languages(self, variables):
        return ",".join(
            language
            for language in self.language_options
            if variables[language].get()
        )

    def build_command(self):
        args = self.build_command_args()
        if os.name == "nt":
            return subprocess.list2cmdline(args)
        return shlex.join(args)

    def build_command_args(self):
        parts = shlex.split(self.base_command_var.get().strip(), posix=False)

        self.add_option(parts, "-p", self.profile_var.get())
        if self.quality_var.get() != "best":
            self.add_option(parts, "-q", self.quality_var.get())
        self.add_option(parts, "-v", self.vcodec_var.get())
        self.add_option(parts, "-a", self.acodec_var.get())
        self.add_option(parts, "-vb", self.vbitrate_var.get())
        self.add_option(parts, "-ab", self.abitrate_var.get())

        if self.audio_boost_var.get() != "none":
            self.add_option(parts, "-abo", self.audio_boost_var.get())

        self.add_bool(parts, "-aa", self.atmos_var.get())
        self.add_option(parts, "-ch", self.channels_var.get())
        self.add_option(parts, "-adub", self.adub_var.get())
        self.add_option(parts, "-chdub", self.chdub_var.get())
        self.add_option(parts, "-r", self.range_var.get())
        self.add_option(parts, "-w", self.wanted_var.get())
        self.add_option(parts, "-al", self.selected_languages(self.audio_language_vars))
        self.add_option(parts, "-sl", self.selected_languages(self.subtitle_language_vars))
        self.add_option(parts, "--sd", self.sd_var.get())
        self.add_option(parts, "--scc", self.scc_var.get())
        self.add_option(parts, "--ssdh", self.ssdh_var.get())
        self.add_option(parts, "--sfc", self.sfc_var.get())
        self.add_option(parts, "--delay", self.delay_var.get())

        self.add_bool(parts, "-A", self.audio_only_var.get())
        self.add_bool(parts, "-S", self.subs_only_var.get())
        self.add_bool(parts, "-C", self.chapters_only_var.get())
        self.add_bool(parts, "-ns", self.no_subs_var.get())
        self.add_bool(parts, "-na", self.no_audio_var.get())
        self.add_bool(parts, "-nv", self.no_video_var.get())
        self.add_bool(parts, "-nc", self.no_chapters_var.get())
        self.add_bool(parts, "-ad", self.audio_description_var.get())
        self.add_bool(parts, "--list", self.list_var.get())
        self.add_bool(parts, "--selected", self.selected_var.get())
        self.add_bool(parts, "-nm", self.no_mux_var.get())
        self.add_bool(parts, "--mux", self.mux_var.get())
        self.add_bool(parts, "--worst", self.worst_var.get())
        self.add_bool(parts, "-nf", self.no_forced_var.get())

        platform = self.platform_var.get().strip()
        if platform:
            parts.append(platform)

        link_id = self.link_id_var.get().strip()
        if link_id:
            parts.append(link_id)

        if self.drm_playready_var.get():
            parts.extend(["-drm", "playready"])
        if self.hydrate_var.get():
            parts.append("--hydrate")

        return parts

    def get_config(self):
        values = {
            "base_command": self.base_command_var.get(),
            "profile": self.profile_var.get(),
            "drm_playready": self.drm_playready_var.get(),
            "hydrate": self.hydrate_var.get(),
            "quality": self.quality_var.get(),
            "vcodec": self.vcodec_var.get(),
            "acodec": self.acodec_var.get(),
            "vbitrate": self.vbitrate_var.get(),
            "abitrate": self.abitrate_var.get(),
            "audio_boost": self.audio_boost_var.get(),
            "atmos": self.atmos_var.get(),
            "channels": self.channels_var.get(),
            "adub": self.adub_var.get(),
            "chdub": self.chdub_var.get(),
            "range": self.range_var.get(),
            "wanted": self.wanted_var.get(),
            "alang": self.selected_languages(self.audio_language_vars),
            "slang": self.selected_languages(self.subtitle_language_vars),
            "sd": self.sd_var.get(),
            "scc": self.scc_var.get(),
            "ssdh": self.ssdh_var.get(),
            "sfc": self.sfc_var.get(),
            "delay": self.delay_var.get(),
            "audio_only": self.audio_only_var.get(),
            "subs_only": self.subs_only_var.get(),
            "chapters_only": self.chapters_only_var.get(),
            "no_subs": self.no_subs_var.get(),
            "no_audio": self.no_audio_var.get(),
            "no_video": self.no_video_var.get(),
            "no_chapters": self.no_chapters_var.get(),
            "audio_description": self.audio_description_var.get(),
            "list": self.list_var.get(),
            "selected": self.selected_var.get(),
            "no_mux": self.no_mux_var.get(),
            "mux": self.mux_var.get(),
            "worst": self.worst_var.get(),
            "no_forced": self.no_forced_var.get(),
            "platform": self.platform_var.get(),
            "link_or_id": self.link_id_var.get(),
        }
        return {
            "purpose": "run_command",
            "generated_command": self.build_command(),
            "values": values,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    def get_settings(self):
        return {
            "platform": self.platform_var.get(),
            "link_or_id": self.link_id_var.get(),
            "profile": self.profile_var.get(),
            "drm_playready": self.drm_playready_var.get(),
            "hydrate": self.hydrate_var.get(),
            "quality": self.quality_var.get(),
            "vcodec": self.vcodec_var.get(),
            "acodec": self.acodec_var.get(),
            "vbitrate": self.vbitrate_var.get(),
            "abitrate": self.abitrate_var.get(),
            "audio_boost": self.audio_boost_var.get(),
            "channels": self.channels_var.get(),
            "adub": self.adub_var.get(),
            "chdub": self.chdub_var.get(),
            "range": self.range_var.get(),
            "wanted": self.wanted_var.get(),
            "sd": self.sd_var.get(),
            "scc": self.scc_var.get(),
            "ssdh": self.ssdh_var.get(),
            "sfc": self.sfc_var.get(),
            "delay": self.delay_var.get(),
            "atmos": self.atmos_var.get(),
            "audio_only": self.audio_only_var.get(),
            "subs_only": self.subs_only_var.get(),
            "chapters_only": self.chapters_only_var.get(),
            "no_subs": self.no_subs_var.get(),
            "no_audio": self.no_audio_var.get(),
            "no_video": self.no_video_var.get(),
            "no_chapters": self.no_chapters_var.get(),
            "audio_description": self.audio_description_var.get(),
            "list": self.list_var.get(),
            "selected": self.selected_var.get(),
            "no_mux": self.no_mux_var.get(),
            "mux": self.mux_var.get(),
            "worst": self.worst_var.get(),
            "no_forced": self.no_forced_var.get(),
            "audio_languages": [
                language for language, variable in self.audio_language_vars.items()
                if variable.get()
            ],
            "subtitle_languages": [
                language for language, variable in self.subtitle_language_vars.items()
                if variable.get()
            ],
        }

    def load_settings(self):
        settings_path = os.path.join(os.getcwd(), SETTINGS_FILE)
        if not os.path.isfile(settings_path):
            return

        try:
            with open(settings_path, "r", encoding="utf-8") as file:
                settings = json.load(file)
        except (OSError, json.JSONDecodeError):
            return

        string_vars = {
            "platform": self.platform_var,
            "link_or_id": self.link_id_var,
            "profile": self.profile_var,
            "quality": self.quality_var,
            "vcodec": self.vcodec_var,
            "acodec": self.acodec_var,
            "vbitrate": self.vbitrate_var,
            "abitrate": self.abitrate_var,
            "audio_boost": self.audio_boost_var,
            "channels": self.channels_var,
            "adub": self.adub_var,
            "chdub": self.chdub_var,
            "range": self.range_var,
            "wanted": self.wanted_var,
            "sd": self.sd_var,
            "scc": self.scc_var,
            "ssdh": self.ssdh_var,
            "sfc": self.sfc_var,
            "delay": self.delay_var,
        }
        for key, variable in string_vars.items():
            if key in settings:
                variable.set(str(settings[key]))

        bool_vars = {
            "drm_playready": self.drm_playready_var,
            "hydrate": self.hydrate_var,
            "atmos": self.atmos_var,
            "audio_only": self.audio_only_var,
            "subs_only": self.subs_only_var,
            "chapters_only": self.chapters_only_var,
            "no_subs": self.no_subs_var,
            "no_audio": self.no_audio_var,
            "no_video": self.no_video_var,
            "no_chapters": self.no_chapters_var,
            "audio_description": self.audio_description_var,
            "list": self.list_var,
            "selected": self.selected_var,
            "no_mux": self.no_mux_var,
            "mux": self.mux_var,
            "worst": self.worst_var,
            "no_forced": self.no_forced_var,
        }
        for key, variable in bool_vars.items():
            if key in settings:
                variable.set(bool(settings[key]))

        audio_languages = set(settings.get("audio_languages", []))
        subtitle_languages = set(settings.get("subtitle_languages", []))
        if "audio_languages" in settings:
            for language, variable in self.audio_language_vars.items():
                variable.set(language in audio_languages)
        if "subtitle_languages" in settings:
            for language, variable in self.subtitle_language_vars.items():
                variable.set(language in subtitle_languages)

    def save_settings(self):
        settings_path = os.path.join(os.getcwd(), SETTINGS_FILE)
        try:
            with open(settings_path, "w", encoding="utf-8") as file:
                json.dump(self.get_settings(), file, indent=4, ensure_ascii=False)
        except OSError:
            pass

    def validate_int_field(self, value, name):
        value = str(value).strip()
        if value and not value.isdigit():
            raise ValueError(f"{name} harus berupa angka.")

    def validate(self):
        if not self.platform_var.get().strip():
            raise ValueError("Platform belum dipilih.")

        if not self.link_id_var.get().strip():
            raise ValueError("Link / ID belum diisi.")

        if not self.filename_var.get().strip():
            raise ValueError("Nama file belum diisi.")

        if not os.path.isdir(self.output_folder_var.get().strip()):
            raise ValueError("Folder output tidak valid.")

        self.validate_int_field(self.vbitrate_var.get(), "Video bitrate")
        self.validate_int_field(self.abitrate_var.get(), "Audio bitrate")
        self.validate_int_field(self.delay_var.get(), "Delay")

    def generate_preview(self):
        config = self.get_config()

        text = (
            f"{config['generated_command']}\n"
        )

        self.preview_text.delete("1.0", tk.END)
        self.preview_text.insert("1.0", text)
        self.status_var.set("Status: preview diperbarui")

    def copy_command(self):
        try:
            self.validate()
        except ValueError as exc:
            messagebox.showwarning("Data Tidak Valid", str(exc))
            return

        command = self.build_command()
        self.clipboard_clear()
        self.clipboard_append(command)
        self.status_var.set("Status: command disalin")
        messagebox.showinfo("Berhasil", "Command berhasil disalin ke clipboard.")

    def append_log(self, text):
        timestamp = datetime.now().strftime("%H:%M:%S")
        tag = self.get_log_tag(text)
        self.logs_text.insert(tk.END, f"[{timestamp}] ", ("timestamp",))
        self.logs_text.insert(tk.END, f"{text}\n", (tag,))
        self.logs_text.see(tk.END)

    def get_log_tag(self, text):
        lowered = text.lower()

        if "gagal" in lowered or "error" in lowered or "exception" in lowered:
            return "error"

        if "warning" in lowered or "peringatan" in lowered:
            return "warning"

        if text.startswith("Command:"):
            return "command"

        if text.startswith("Working directory:"):
            return "working_dir"

        if "exit code: 0" in lowered or "selesai" in lowered or "berhasil" in lowered:
            return "success"

        if "stop" in lowered or "dihentikan" in lowered:
            return "stop"

        return "normal"

    def run_command(self):
        try:
            self.validate()
        except ValueError as exc:
            messagebox.showwarning("Data Tidak Valid", str(exc))
            return

        if self.is_running:
            messagebox.showinfo("Masih Berjalan", "Command masih berjalan.")
            return

        self.generate_preview()
        self.is_running = True
        self.stop_requested = False
        self.run_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status_var.set("Status: command berjalan")

        self.append_log("Menjalankan command asli.")
        self.append_log(f"Command: {self.build_command()}")
        self.append_log(f"Working directory: {self.output_folder_var.get().strip()}")

        try:
            popen_kwargs = {
                "cwd": self.output_folder_var.get().strip(),
                "stdout": subprocess.PIPE,
                "stderr": subprocess.STDOUT,
                "stdin": subprocess.DEVNULL,
                "text": True,
                "encoding": "utf-8",
                "errors": "replace",
                "bufsize": 1
            }

            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                popen_kwargs["creationflags"] = (
                    subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
                )
                popen_kwargs["startupinfo"] = startupinfo
            else:
                popen_kwargs["start_new_session"] = True

            self.process = subprocess.Popen(
                self.build_command_args(),
                **popen_kwargs
            )
        except OSError as exc:
            self.is_running = False
            self.process = None
            self.run_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
            self.status_var.set("Status: command gagal dijalankan")
            self.append_log(f"Gagal menjalankan command: {exc}")
            messagebox.showerror("Gagal Menjalankan Command", str(exc))
            return

        self.output_thread = threading.Thread(
            target=self.read_process_output,
            args=(self.process,),
            daemon=True
        )
        self.output_thread.start()
        self.poll_process_logs()

    def read_process_output(self, process):
        try:
            if process and process.stdout:
                for line in process.stdout:
                    self.log_queue.put(("log", line.rstrip()))

            return_code = process.wait() if process else -1
            self.log_queue.put(("done", return_code))
        except Exception as exc:
            self.log_queue.put(("error", str(exc)))

    def poll_process_logs(self):
        while not self.log_queue.empty():
            kind, value = self.log_queue.get_nowait()

            if kind == "log" and value:
                self.append_log(value)
            elif kind == "error":
                self.append_log(f"Error membaca output proses: {value}")
                self.finish_process("Status: command error")
            elif kind == "done":
                self.append_log(f"Exit code: {value}")
                if self.stop_requested:
                    self.finish_process("Status: command dihentikan")
                else:
                    self.finish_process("Status: command selesai")

        if self.is_running:
            self.log_poll_job = self.after(150, self.poll_process_logs)

    def finish_process(self, status):
        self.is_running = False
        self.process = None
        self.run_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.status_var.set(status)
        self.log_poll_job = None

    def stop_command(self):
        if not self.is_running:
            return

        if self.process and self.process.poll() is None:
            self.stop_requested = True
            self.stop_button.configure(state="disabled")
            self.status_var.set("Status: menghentikan command")
            self.append_log("Permintaan stop dikirim ke command dan proses turunannya.")
            self.stop_thread = threading.Thread(
                target=self.stop_process_tree,
                args=(self.process,),
                daemon=True
            )
            self.stop_thread.start()
            return

        self.finish_process("Status: command dihentikan")

    def stop_process_tree(self, process):
        try:
            if os.name == "nt":
                result = subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace"
                )
                output = result.stdout.strip()
                if output:
                    self.log_queue.put(("log", output))
            else:
                os.killpg(process.pid, signal.SIGTERM)
        except Exception as exc:
            self.log_queue.put(("log", f"Gagal menghentikan process tree: {exc}"))
            try:
                process.kill()
            except Exception as kill_exc:
                self.log_queue.put(("log", f"Gagal memaksa stop proses utama: {kill_exc}"))

    def on_close(self):
        self.save_settings()

        if self.process and self.process.poll() is None:
            self.stop_requested = True
            self.stop_process_tree(self.process)

        if self.log_poll_job is not None:
            try:
                self.after_cancel(self.log_poll_job)
            except tk.TclError:
                pass
            self.log_poll_job = None

        self.destroy()

    def clear_logs(self):
        self.logs_text.delete("1.0", tk.END)
        self.status_var.set("Status: logs dibersihkan")

    def open_downloads_folder(self):
        downloads_folder = os.path.join(os.getcwd(), "downloads")
        os.makedirs(downloads_folder, exist_ok=True)

        try:
            if os.name == "nt":
                os.startfile(downloads_folder)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", downloads_folder])
            else:
                subprocess.Popen(["xdg-open", downloads_folder])
            self.status_var.set(f"Status: membuka folder {downloads_folder}")
        except Exception as exc:
            messagebox.showerror("Gagal Membuka Folder", str(exc))

    def save_logs(self):
        logs = self.logs_text.get("1.0", tk.END).strip()

        if not logs:
            messagebox.showwarning("Logs Kosong", "Belum ada logs yang bisa disimpan.")
            return

        if not os.path.isdir(self.output_folder_var.get().strip()):
            messagebox.showwarning("Folder Tidak Valid", "Folder output tidak valid.")
            return

        file_path = os.path.join(self.output_folder_var.get().strip(), f"{self.filename_var.get().strip()}_logs.txt")

        content = (
            "VINETRIMMER COMMAND LOGS\n\n"
            f"Generated Command:\n{self.build_command()}\n\n"
            "Logs:\n"
            f"{logs}\n"
        )

        with open(file_path, "w", encoding="utf-8") as file:
            file.write(content)

        self.status_var.set(f"Status: logs disimpan di {file_path}")
        messagebox.showinfo("Berhasil", f"Logs berhasil disimpan:\n{file_path}")

    def reset_form(self):
        if self.is_running:
            self.stop_command()

        self.base_command_var.set("poetry run vt dl")
        self.platform_var.set("netflix")
        self.link_id_var.set("")
        self.output_folder_var.set(os.getcwd())
        self.filename_var.set("vinetrimmer_command")
        self.profile_var.set("")
        self.drm_playready_var.set(True)
        self.hydrate_var.set(True)
        self.quality_var.set("best")
        self.vcodec_var.set(DEFAULT_OPTION)
        self.acodec_var.set(DEFAULT_OPTION)
        self.vbitrate_var.set("")
        self.abitrate_var.set("")
        self.audio_boost_var.set("none")
        self.atmos_var.set(False)
        self.channels_var.set(DEFAULT_OPTION)
        self.adub_var.set(DEFAULT_OPTION)
        self.chdub_var.set(DEFAULT_OPTION)
        self.range_var.set(DEFAULT_OPTION)
        self.wanted_var.set("")
        for language, variable in self.audio_language_vars.items():
            variable.set(False)
        for language, variable in self.subtitle_language_vars.items():
            variable.set(False)
        self.sd_var.set("")
        self.scc_var.set("")
        self.ssdh_var.set("")
        self.sfc_var.set("")
        self.delay_var.set("")

        for variable in [
            self.audio_only_var, self.subs_only_var, self.chapters_only_var,
            self.no_subs_var, self.no_audio_var, self.no_video_var,
            self.no_chapters_var, self.audio_description_var, self.list_var,
            self.selected_var, self.no_mux_var, self.mux_var, self.worst_var,
            self.no_forced_var
        ]:
            variable.set(False)

        self.clear_logs()
        self.generate_preview()
        self.status_var.set("Status: form direset")


if __name__ == "__main__":
    app = VinetrimmerCommandGUI()
    app.mainloop()
