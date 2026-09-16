from __future__ import annotations

from datetime import datetime
from importlib.resources import files
import locale
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    pystray = None
    Image = None
    ImageDraw = None
    ImageFont = None

if TYPE_CHECKING:
    from pystray import Icon

if sys.platform == "win32":
    import winreg

from .reader import CodexUsage, UsageWindow, read_latest_usage


REFRESH_MS = 10 * 60 * 1000
DEFAULT_OPACITY = 75
SHORTCUT_NAME = "Codex Usage Widget.lnk"
APP_COMMAND = "codex-usage-widget"
ICON_FILE_NAME = "codex-usage-widget.ico"
POWERSHELL_EXE = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"

TRANSLATIONS = {
    "zh-Hant": {
        "title": "Codex 剩餘用量",
        "subtitle": "雙軌時間窗口控管",
        "refresh": "刷新",
        "reconnect": "重新連線",
        "close": "關閉",
        "show": "顯示面板",
        "hide_hint": "雙擊面板縮到系統匣",
        "starting": "啟動中",
        "refreshed": "已刷新",
        "reconnecting": "重新連線中...",
        "reconnected": "重新連線完成",
        "error": "錯誤",
        "unknown": "未知",
        "no_credits": "無額外點數",
        "credits": "額外點數",
        "source": "來源",
        "auto_refresh": "每 10 分鐘自動更新",
        "no_data": "無資料",
        "not_provided": "未提供",
        "reset_unknown": "RESET UNKNOWN",
        "opacity": "透明度",
        "language_tooltip": "切換語言",
        "theme_tooltip": "切換深色/淺色主題",
        "opacity_tooltip": "調整面板透明度",
    },
    "en": {
        "title": "Codex Usage",
        "subtitle": "Dual window usage controls",
        "refresh": "Refresh",
        "reconnect": "Reconnect",
        "close": "Close",
        "show": "Show panel",
        "hide_hint": "Double-click panel to tray",
        "starting": "Starting",
        "refreshed": "Refreshed",
        "reconnecting": "Reconnecting...",
        "reconnected": "Reconnected",
        "error": "Error",
        "unknown": "Unknown",
        "no_credits": "No extra credits",
        "credits": "Credits",
        "source": "Source",
        "auto_refresh": "Auto refresh every 10 minutes",
        "no_data": "NO DATA",
        "not_provided": "Not provided",
        "reset_unknown": "RESET UNKNOWN",
        "opacity": "Opacity",
        "language_tooltip": "Switch language",
        "theme_tooltip": "Switch dark/light theme",
        "opacity_tooltip": "Adjust panel opacity",
    },
}

THEMES = {
    "light": {
        "bg": "#DDF9F6",
        "panel": "#F7FFFE",
        "button": "#C8F0EC",
        "button_active": "#B2E7E1",
        "shadow": "#B7DFDB",
        "accent": "#0ABAB5",
        "secondary": "#FF6F91",
        "line": "#87D8D2",
        "text": "#103B3A",
        "muted": "#4A6F6C",
        "bar_bg": "#E5F8F6",
        "warn": "#B76E00",
    },
    "dark": {
        "bg": "#272822",
        "panel": "#1E1F1C",
        "button": "#34352F",
        "button_active": "#49483E",
        "shadow": "#11120F",
        "accent": "#66D9EF",
        "secondary": "#F92672",
        "line": "#75715E",
        "text": "#F8F8F2",
        "muted": "#A6E22E",
        "bar_bg": "#3E3D32",
        "warn": "#FD971F",
    },
}


class Tooltip:
    def __init__(self, widget: tk.Widget, text_getter: object) -> None:
        self.widget = widget
        self.text_getter = text_getter
        self.tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, _event: object | None = None) -> None:
        if self.tip is not None:
            return
        text = self.text_getter() if callable(self.text_getter) else str(self.text_getter)
        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(
            self.tip,
            text=text,
            bg="#111111",
            fg="#ffffff",
            padx=8,
            pady=4,
            font=("Microsoft JhengHei UI", 8),
        ).pack()

    def hide(self, _event: object | None = None) -> None:
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None


class UsageWidget(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.language = self._detect_language()
        self.theme_name = self._detect_theme()
        self.palette = THEMES[self.theme_name]
        self.opacity = tk.DoubleVar(value=DEFAULT_OPACITY)

        self.title(self._t("title"))
        self.attributes("-topmost", True)
        self.attributes("-alpha", DEFAULT_OPACITY / 100)
        self.resizable(False, False)
        self.configure(bg=self.palette["bg"])
        self.geometry("400x344+24+24")
        self.protocol("WM_DELETE_WINDOW", self.close_app)
        self._refresh_job: str | None = None
        self._last_usage: CodexUsage | None = None
        self._status_key = "starting"
        self._status_time: datetime | None = None
        self._error_name = ""
        self._buttons: list[tk.Button] = []
        self.tray_icon: Icon | None = None

        self.controls = tk.Frame(self, bg=self.palette["bg"])
        self.controls.pack(fill="x", padx=14, pady=(12, 2))
        self.language_button = self._icon_button(self.controls, self._language_icon(), self.toggle_language)
        self.language_button.pack(side="left")
        Tooltip(self.language_button, lambda: self._t("language_tooltip"))
        self.theme_button = self._icon_button(self.controls, self._theme_icon(), self.toggle_theme)
        self.theme_button.pack(side="left", padx=(8, 12))
        Tooltip(self.theme_button, lambda: self._t("theme_tooltip"))

        self.opacity_label = tk.Label(
            self.controls,
            text=self._opacity_text(),
            bg=self.palette["bg"],
            fg=self.palette["muted"],
            font=("Microsoft JhengHei UI", 9, "bold"),
        )
        self.opacity_label.pack(side="left", padx=(0, 8))
        self.opacity_slider = ttk.Scale(
            self.controls,
            from_=0,
            to=100,
            orient="horizontal",
            variable=self.opacity,
            command=self.set_opacity,
            length=130,
        )
        self.opacity_slider.pack(side="left", fill="x", expand=True)
        Tooltip(self.opacity_slider, lambda: self._t("opacity_tooltip"))

        self.canvas = tk.Canvas(self, width=400, height=238, bg=self.palette["bg"], bd=0, highlightthickness=0)
        self.canvas.pack(fill="both")
        self.canvas.bind("<Double-Button-1>", self.hide_to_tray)

        self.buttons_frame = tk.Frame(self, bg=self.palette["bg"])
        self.buttons_frame.pack(fill="x", padx=14, pady=(4, 14))
        self.refresh_button = self._button(self.buttons_frame, self._t("refresh"), self.refresh_now)
        self.refresh_button.pack(side="left", expand=True, fill="x", padx=(0, 6))
        self.reconnect_button = self._button(self.buttons_frame, self._t("reconnect"), self.reconnect)
        self.reconnect_button.pack(side="left", expand=True, fill="x", padx=6)
        self.close_button = self._button(self.buttons_frame, self._t("close"), self.close_app)
        self.close_button.pack(side="left", expand=True, fill="x", padx=(6, 0))

        self._ensure_desktop_shortcut()
        self._setup_tray_icon()
        self.refresh_now()

    def _detect_language(self) -> str:
        lang = (locale.getlocale()[0] or locale.getdefaultlocale()[0] or "").lower()
        if lang in {"zh_tw", "zh_hk", "zh_mo", "zh_hant"} or "hant" in lang:
            return "zh-Hant"
        if lang.startswith("en"):
            return "en"
        return "zh-Hant"

    def _detect_theme(self) -> str:
        if sys.platform != "win32":
            return "light"
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            ) as key:
                apps_use_light_theme = winreg.QueryValueEx(key, "AppsUseLightTheme")[0]
        except OSError:
            return "light"
        return "light" if apps_use_light_theme else "dark"

    def _t(self, key: str) -> str:
        return TRANSLATIONS[self.language][key]

    def _button(self, parent: tk.Widget, text: str, command: object) -> tk.Button:
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=self.palette["button"],
            fg=self.palette["text"],
            activebackground=self.palette["button_active"],
            activeforeground=self.palette["accent"],
            relief="flat",
            bd=0,
            padx=8,
            pady=8,
            font=("Microsoft JhengHei UI", 9, "bold"),
            highlightthickness=1,
            highlightbackground=self.palette["accent"],
            highlightcolor=self.palette["accent"],
            cursor="hand2",
        )
        self._buttons.append(button)
        return button

    def _icon_button(self, parent: tk.Widget, text: str, command: object) -> tk.Button:
        button = self._button(parent, text, command)
        button.configure(width=3, padx=0, pady=5, font=("Microsoft JhengHei UI", 10, "bold"))
        return button

    def _language_icon(self) -> str:
        return "A" if self.language == "zh-Hant" else "文"

    def _theme_icon(self) -> str:
        return "☾" if self.theme_name == "light" else "☀"

    def _opacity_text(self) -> str:
        return f"{self._t('opacity')} {int(round(self.opacity.get()))}%"

    def toggle_language(self) -> None:
        self.language = "en" if self.language == "zh-Hant" else "zh-Hant"
        self.title(self._t("title"))
        self.language_button.configure(text=self._language_icon())
        self.refresh_button.configure(text=self._t("refresh"))
        self.reconnect_button.configure(text=self._t("reconnect"))
        self.close_button.configure(text=self._t("close"))
        self.opacity_label.configure(text=self._opacity_text())
        self._refresh_tray_menu()
        self._draw()

    def toggle_theme(self) -> None:
        self.theme_name = "dark" if self.theme_name == "light" else "light"
        self.palette = THEMES[self.theme_name]
        self.theme_button.configure(text=self._theme_icon())
        self._apply_theme()
        self._draw()
        self._update_tray_icon()

    def set_opacity(self, _value: object | None = None) -> None:
        opacity = int(round(self.opacity.get()))
        self.attributes("-alpha", max(0, min(100, opacity)) / 100)
        self.opacity_label.configure(text=self._opacity_text())

    def _apply_theme(self) -> None:
        self.configure(bg=self.palette["bg"])
        self.controls.configure(bg=self.palette["bg"])
        self.buttons_frame.configure(bg=self.palette["bg"])
        self.canvas.configure(bg=self.palette["bg"])
        self.opacity_label.configure(bg=self.palette["bg"], fg=self.palette["muted"])
        for button in self._buttons:
            button.configure(
                bg=self.palette["button"],
                fg=self.palette["text"],
                activebackground=self.palette["button_active"],
                activeforeground=self.palette["accent"],
                highlightbackground=self.palette["accent"],
                highlightcolor=self.palette["accent"],
            )

    def refresh_now(self) -> None:
        self._cancel_scheduled_refresh()
        self._read_and_render("refreshed")
        self._schedule_refresh()

    def reconnect(self) -> None:
        self._cancel_scheduled_refresh()
        self._status_key = "reconnecting"
        self._status_time = None
        self._draw()
        self.after(100, lambda: (self._read_and_render("reconnected"), self._schedule_refresh()))

    def hide_to_tray(self, _event: object | None = None) -> None:
        self.withdraw()
        self._update_tray_icon()
        if self.tray_icon is not None:
            self.tray_icon.visible = True

    def show_panel(self, _icon: object | None = None, _item: object | None = None) -> None:
        self.after(0, self._show_panel_on_tk_thread)

    def _show_panel_on_tk_thread(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()
        self.attributes("-topmost", True)
        self._update_tray_icon()

    def close_app(self, _icon: object | None = None, _item: object | None = None) -> None:
        self.after(0, self._close_app_on_tk_thread)

    def _close_app_on_tk_thread(self) -> None:
        self._cancel_scheduled_refresh()
        if self.tray_icon is not None:
            self.tray_icon.visible = False
            self.tray_icon.stop()
            self.tray_icon = None
        self.destroy()

    def _read_and_render(self, success_key: str) -> None:
        try:
            self._last_usage = read_latest_usage()
        except Exception as exc:
            self._status_key = "error"
            self._status_time = None
            self._error_name = type(exc).__name__
            self._last_usage = None
        else:
            self._status_key = success_key
            self._status_time = datetime.now()
        self._draw()
        self._update_tray_icon()

    def _draw(self) -> None:
        self.canvas.delete("all")
        self._draw_header()

        if self._last_usage is None:
            self._draw_empty_card(18, 54, 190, 166, "5H")
            self._draw_empty_card(210, 54, 382, 166, "7DAY")
            plan_line = "PLAN --  |  CREDIT --"
            source_line = f"{self._t('source').upper()} --"
        else:
            self._draw_usage_card(18, 54, 190, 166, "5H", self._last_usage.primary, self.palette["accent"])
            self._draw_usage_card(210, 54, 382, 166, "7DAY", self._last_usage.secondary, self.palette["secondary"])
            plan = self._last_usage.plan_type or self._t("unknown")
            credits = self._t("no_credits") if not self._last_usage.has_credits else f"{self._t('credits')} {self._last_usage.credit_balance}"
            plan_line = f"PLAN {plan.upper()}  |  {credits}"
            source_line = f"{self._t('source').upper()} {self._last_usage.source}"

        self.canvas.create_text(18, 187, anchor="w", text=plan_line, fill=self.palette["muted"], font=("Microsoft JhengHei UI", 9))
        self.canvas.create_text(18, 205, anchor="w", text=source_line, fill=self.palette["muted"], font=("Consolas", 9))
        self.canvas.create_text(18, 223, anchor="w", text=self._status_line(), fill=self.palette["text"], font=("Microsoft JhengHei UI", 9, "bold"))
        self.canvas.create_text(382, 223, anchor="e", text=self._t("hide_hint"), fill=self.palette["line"], font=("Microsoft JhengHei UI", 8))

    def _status_line(self) -> str:
        if self._status_key == "error":
            status = f"{self._t('error')}: {self._error_name}"
        elif self._status_time is not None:
            status = f"{self._t(self._status_key)} {self._status_time:%H:%M:%S}"
        else:
            status = self._t(self._status_key)
        return f"{status}  |  {self._t('auto_refresh')}"

    def _draw_header(self) -> None:
        self.canvas.create_text(22, 16, anchor="w", text="CODEX USAGE", fill=self.palette["accent"], font=("Consolas", 13, "bold"))
        self.canvas.create_text(22, 36, anchor="w", text=self._t("subtitle"), fill=self.palette["text"], font=("Microsoft JhengHei UI", 10))
        self.canvas.create_line(150, 25, 382, 25, fill=self.palette["line"], width=1)
        self.canvas.create_line(292, 25, 382, 25, fill=self.palette["secondary"], width=2)

    def _draw_empty_card(self, x1: int, y1: int, x2: int, y2: int, title: str) -> None:
        self._draw_card_shell(x1, y1, x2, y2, title, self.palette["warn"])
        self.canvas.create_text((x1 + x2) // 2, y1 + 66, text=self._t("no_data"), fill=self.palette["warn"], font=("Consolas", 16, "bold"))

    def _draw_usage_card(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        title: str,
        window: UsageWindow | None,
        accent: str,
    ) -> None:
        self._draw_card_shell(x1, y1, x2, y2, title, accent)
        if window is None:
            self.canvas.create_text((x1 + x2) // 2, y1 + 66, text=self._t("not_provided"), fill=self.palette["warn"], font=("Microsoft JhengHei UI", 14, "bold"))
            return

        percent = window.remaining_percent
        used = window.used_percent
        self.canvas.create_text(x1 + 18, y1 + 50, anchor="w", text=f"{percent:.0f}%", fill=self.palette["text"], font=("Consolas", 28, "bold"))
        self.canvas.create_text(x2 - 18, y1 + 55, anchor="e", text=f"USED {used:.0f}%", fill=self.palette["muted"], font=("Consolas", 8))
        bar_x1, bar_y1, bar_x2, bar_y2 = x1 + 18, y1 + 82, x2 - 18, y1 + 94
        self.canvas.create_rectangle(bar_x1, bar_y1, bar_x2, bar_y2, outline=self.palette["line"], fill=self.palette["bar_bg"])
        fill_x = bar_x1 + int((bar_x2 - bar_x1) * max(0.0, min(100.0, percent)) / 100)
        self.canvas.create_rectangle(bar_x1, bar_y1, fill_x, bar_y2, outline="", fill=accent)
        reset = f"RESET {window.reset_at:%m-%d %H:%M}" if window.reset_at else self._t("reset_unknown")
        self.canvas.create_text(x1 + 18, y1 + 112, anchor="w", text=reset, fill=self.palette["text"], font=("Consolas", 9, "bold"))

    def _draw_card_shell(self, x1: int, y1: int, x2: int, y2: int, title: str, accent: str) -> None:
        self.canvas.create_rectangle(x1 + 4, y1 + 4, x2 + 4, y2 + 4, outline="", fill=self.palette["shadow"])
        self.canvas.create_rectangle(x1, y1, x2, y2, outline=accent, width=2, fill=self.palette["panel"])
        self.canvas.create_line(x1, y1 + 22, x1 + 44, y1 + 22, fill=accent, width=3)
        self.canvas.create_line(x2 - 44, y2 - 22, x2, y2 - 22, fill=accent, width=3)
        self.canvas.create_text(x1 + 18, y1 + 22, anchor="w", text=title, fill=accent, font=("Consolas", 13, "bold"))

    def _ensure_desktop_shortcut(self) -> None:
        if sys.platform != "win32":
            return
        desktop = self._desktop_dir()
        target, arguments = self._shortcut_launch_command()
        if desktop is None or target is None:
            return
        shortcut = desktop / SHORTCUT_NAME
        icon = self._shortcut_icon_path() or target
        script = """
param([string]$ShortcutPath, [string]$TargetPath, [string]$LaunchArguments, [string]$WorkingDirectory, [string]$IconPath)
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($ShortcutPath)
$shortcut.TargetPath = $TargetPath
$shortcut.Arguments = $LaunchArguments
$shortcut.WorkingDirectory = $WorkingDirectory
$shortcut.IconLocation = $IconPath
$shortcut.Description = 'Launch Codex Usage Widget'
$shortcut.Save()
"""
        script_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8") as handle:
                handle.write(script)
                script_path = Path(handle.name)
            subprocess.run(
                [
                    POWERSHELL_EXE,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script_path),
                    "-ShortcutPath",
                    str(shortcut),
                    "-TargetPath",
                    str(target),
                    "-LaunchArguments",
                    arguments,
                    "-WorkingDirectory",
                    str(Path.home()),
                    "-IconPath",
                    str(icon),
                ],
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                timeout=8,
            )
        except OSError:
            return
        finally:
            if script_path is not None:
                try:
                    script_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def _desktop_dir(self) -> Path | None:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
            ) as key:
                value = winreg.QueryValueEx(key, "Desktop")[0]
        except OSError:
            value = r"%USERPROFILE%\Desktop"
        expanded = Path(str(value).replace("%USERPROFILE%", str(Path.home())))
        return expanded if expanded.exists() else None

    def _shortcut_icon_path(self) -> Path | None:
        try:
            icon = files("codex_usage_widget") / "assets" / ICON_FILE_NAME
        except (FileNotFoundError, ModuleNotFoundError):
            return None
        icon_path = Path(str(icon))
        return icon_path if icon_path.exists() else None

    def _shortcut_launch_command(self) -> tuple[Path | None, str]:
        pythonw = self._pythonw_path()
        if pythonw is not None:
            return pythonw, "-m codex_usage_widget"
        command = shutil.which(APP_COMMAND)
        if command:
            return Path(command), ""
        candidate = Path(sys.argv[0])
        return (candidate, "") if candidate.exists() else (None, "")

    def _pythonw_path(self) -> Path | None:
        executable = Path(sys.executable)
        candidates = [executable.with_name("pythonw.exe")]
        package_file = Path(__file__).resolve()
        parents = list(package_file.parents)
        if len(parents) >= 4:
            candidates.append(parents[3] / "Scripts" / "pythonw.exe")
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None
    def _setup_tray_icon(self) -> None:
        if pystray is None or Image is None:
            return
        self.tray_icon = pystray.Icon(
            "codex-usage-widget",
            icon=self._create_tray_image(),
            title=self._tray_title(),
            menu=self._tray_menu(),
        )
        try:
            self.tray_icon.run_detached()
            self.tray_icon.visible = True
        except NotImplementedError:
            self.tray_icon = None

    def _tray_menu(self) -> object:
        return pystray.Menu(
            pystray.MenuItem(lambda _item: self._t("show"), self.show_panel, default=True),
            pystray.MenuItem(lambda _item: self._t("refresh"), lambda _icon, _item: self.after(0, self.refresh_now)),
            pystray.MenuItem(lambda _item: self._t("close"), self.close_app),
        )

    def _refresh_tray_menu(self) -> None:
        if self.tray_icon is not None:
            self.tray_icon.menu = self._tray_menu()
            self.tray_icon.update_menu()
            self._update_tray_icon()

    def _update_tray_icon(self) -> None:
        if self.tray_icon is None:
            return
        self.tray_icon.icon = self._create_tray_image()
        self.tray_icon.title = self._tray_title()
        self.tray_icon.update_menu()

    def _tray_title(self) -> str:
        if self._last_usage is None:
            return "Codex: --%"
        primary = self._format_tray_window("5H", self._last_usage.primary)
        secondary = self._format_tray_window("7DAY", self._last_usage.secondary)
        return f"Codex {primary} | {secondary}"

    def _format_tray_window(self, label: str, window: UsageWindow | None) -> str:
        if window is None:
            return f"{label} --%"
        return f"{label} {window.remaining_percent:.0f}%"

    def _create_tray_image(self) -> object:
        if Image is None or ImageDraw is None:
            return None
        remaining = self._last_usage.primary.remaining_percent if self._last_usage and self._last_usage.primary else 0
        text = f"{remaining:.0f}"
        bg = self.palette["panel"]
        accent = self.palette["accent"]
        image = Image.new("RGBA", (64, 64), bg)
        draw = ImageDraw.Draw(image)
        draw.rectangle((1, 1, 62, 62), outline=accent, width=4)
        draw.rectangle((5, 5, 58, 58), outline=self.palette["line"], width=1)
        font = self._fit_tray_font(draw, text)
        try:
            box = draw.textbbox((0, 0), text, font=font)
            width = box[2] - box[0]
            height = box[3] - box[1]
            x_offset = box[0]
            y_offset = box[1]
        except AttributeError:
            width, height = draw.textsize(text, font=font)
            x_offset = 0
            y_offset = 0
        x = (64 - width) / 2 - x_offset
        y = (64 - height) / 2 - y_offset - 1
        draw.text(
            (x, y),
            text,
            fill=self.palette["text"],
            font=font,
            stroke_width=2,
            stroke_fill=bg,
        )
        return image

    def _fit_tray_font(self, draw: object, text: str) -> object:
        for size in range(48, 19, -2):
            font = self._tray_font(size)
            try:
                box = draw.textbbox((0, 0), text, font=font, stroke_width=2)
                width = box[2] - box[0]
                height = box[3] - box[1]
            except AttributeError:
                width, height = draw.textsize(text, font=font)
            if width <= 52 and height <= 48:
                return font
        return self._tray_font(20)

    def _tray_font(self, size: int) -> object:
        if ImageFont is None:
            return None
        candidates = [
            Path("C:/Windows/Fonts/consolab.ttf"),
            Path("C:/Windows/Fonts/consola.ttf"),
            Path("C:/Windows/Fonts/arial.ttf"),
        ]
        for path in candidates:
            if path.exists():
                return ImageFont.truetype(str(path), size=size)
        return ImageFont.load_default()

    def _schedule_refresh(self) -> None:
        self._refresh_job = self.after(REFRESH_MS, self.refresh_now)

    def _cancel_scheduled_refresh(self) -> None:
        if self._refresh_job is not None:
            self.after_cancel(self._refresh_job)
            self._refresh_job = None


def main() -> None:
    UsageWidget().mainloop()












