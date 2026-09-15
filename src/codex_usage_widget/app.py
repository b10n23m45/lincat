from __future__ import annotations

from datetime import datetime
import tkinter as tk

from .reader import CodexUsage, UsageWindow, read_latest_usage


REFRESH_MS = 10 * 60 * 1000
BG = "#05070d"
PANEL = "#0b1220"
CYAN = "#00e5ff"
PINK = "#ff2bd6"
TEXT = "#e8fbff"
MUTED = "#7f9aaa"
WARN = "#ffbf3c"


class UsageWidget(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Codex 剩餘用量")
        self.attributes("-topmost", True)
        self.resizable(False, False)
        self.configure(bg=BG)
        self.geometry("400x300+24+24")
        self._refresh_job: str | None = None
        self._last_usage: CodexUsage | None = None
        self._status = "啟動中"

        self.canvas = tk.Canvas(self, width=400, height=238, bg=BG, bd=0, highlightthickness=0)
        self.canvas.pack(fill="both")

        buttons = tk.Frame(self, bg=BG)
        buttons.pack(fill="x", padx=14, pady=(4, 14))
        self._button(buttons, "刷新", self.refresh_now).pack(side="left", expand=True, fill="x", padx=(0, 6))
        self._button(buttons, "重新連線", self.reconnect).pack(side="left", expand=True, fill="x", padx=6)
        self._button(buttons, "關閉", self.destroy).pack(side="left", expand=True, fill="x", padx=(6, 0))

        self.refresh_now()

    def _button(self, parent: tk.Widget, text: str, command: object) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg="#101827",
            fg=TEXT,
            activebackground="#16263a",
            activeforeground=CYAN,
            relief="flat",
            bd=0,
            padx=8,
            pady=8,
            font=("Microsoft JhengHei UI", 9, "bold"),
            highlightthickness=1,
            highlightbackground=CYAN,
            highlightcolor=CYAN,
            cursor="hand2",
        )

    def refresh_now(self) -> None:
        self._cancel_scheduled_refresh()
        self._read_and_render("已刷新")
        self._schedule_refresh()

    def reconnect(self) -> None:
        self._cancel_scheduled_refresh()
        self._status = "重新連線中..."
        self._draw()
        self.after(100, lambda: (self._read_and_render("重新連線完成"), self._schedule_refresh()))

    def _read_and_render(self, success_message: str) -> None:
        try:
            self._last_usage = read_latest_usage()
        except Exception as exc:
            self._status = f"錯誤：{type(exc).__name__}"
            self._last_usage = None
        else:
            self._status = f"{success_message} {datetime.now():%H:%M:%S}"
        self._draw()

    def _draw(self) -> None:
        self.canvas.delete("all")
        self._draw_header()

        if self._last_usage is None:
            self._draw_empty_card(18, 54, 190, 166, "5H")
            self._draw_empty_card(210, 54, 382, 166, "7DAY")
            plan_line = "PLAN --  |  CREDIT --"
            source_line = "SOURCE --"
        else:
            self._draw_usage_card(18, 54, 190, 166, "5H", self._last_usage.primary, CYAN)
            self._draw_usage_card(210, 54, 382, 166, "7DAY", self._last_usage.secondary, PINK)
            plan = self._last_usage.plan_type or "未知"
            credits = "無額外點數" if not self._last_usage.has_credits else f"額外點數 {self._last_usage.credit_balance}"
            plan_line = f"PLAN {plan.upper()}  |  {credits}"
            source_line = f"SOURCE {self._last_usage.source}"

        self.canvas.create_text(18, 190, anchor="w", text=plan_line, fill=MUTED, font=("Microsoft JhengHei UI", 9))
        self.canvas.create_text(18, 209, anchor="w", text=source_line, fill=MUTED, font=("Consolas", 9))
        self.canvas.create_text(18, 228, anchor="w", text=f"{self._status}  |  每 10 分鐘自動更新", fill=TEXT, font=("Microsoft JhengHei UI", 9, "bold"))

    def _draw_header(self) -> None:
        self.canvas.create_text(22, 16, anchor="w", text="CODEX USAGE", fill=CYAN, font=("Consolas", 13, "bold"))
        self.canvas.create_text(22, 36, anchor="w", text="雙軌時間窗口控管", fill=TEXT, font=("Microsoft JhengHei UI", 10))
        self.canvas.create_line(150, 25, 382, 25, fill="#17384a", width=1)
        self.canvas.create_line(292, 25, 382, 25, fill=PINK, width=2)

    def _draw_empty_card(self, x1: int, y1: int, x2: int, y2: int, title: str) -> None:
        self._draw_card_shell(x1, y1, x2, y2, title, WARN)
        self.canvas.create_text((x1 + x2) // 2, y1 + 66, text="NO DATA", fill=WARN, font=("Consolas", 16, "bold"))

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
            self.canvas.create_text((x1 + x2) // 2, y1 + 66, text="未提供", fill=WARN, font=("Microsoft JhengHei UI", 14, "bold"))
            return

        percent = window.remaining_percent
        used = window.used_percent
        self.canvas.create_text(x1 + 18, y1 + 50, anchor="w", text=f"{percent:.0f}%", fill=TEXT, font=("Consolas", 28, "bold"))
        self.canvas.create_text(x2 - 18, y1 + 55, anchor="e", text=f"USED {used:.0f}%", fill=MUTED, font=("Consolas", 8))
        bar_x1, bar_y1, bar_x2, bar_y2 = x1 + 18, y1 + 82, x2 - 18, y1 + 94
        self.canvas.create_rectangle(bar_x1, bar_y1, bar_x2, bar_y2, outline="#233244", fill="#09111c")
        fill_x = bar_x1 + int((bar_x2 - bar_x1) * max(0.0, min(100.0, percent)) / 100)
        self.canvas.create_rectangle(bar_x1, bar_y1, fill_x, bar_y2, outline="", fill=accent)
        reset = f"RESET {window.reset_at:%m-%d %H:%M}" if window.reset_at else "RESET UNKNOWN"
        self.canvas.create_text(x1 + 18, y1 + 112, anchor="w", text=reset, fill=TEXT, font=("Consolas", 9, "bold"))

    def _draw_card_shell(self, x1: int, y1: int, x2: int, y2: int, title: str, accent: str) -> None:
        self.canvas.create_rectangle(x1 + 4, y1 + 4, x2 + 4, y2 + 4, outline="", fill="#030409")
        self.canvas.create_rectangle(x1, y1, x2, y2, outline=accent, width=2, fill=PANEL)
        self.canvas.create_line(x1, y1 + 22, x1 + 44, y1 + 22, fill=accent, width=3)
        self.canvas.create_line(x2 - 44, y2 - 22, x2, y2 - 22, fill=accent, width=3)
        self.canvas.create_text(x1 + 18, y1 + 22, anchor="w", text=title, fill=accent, font=("Consolas", 13, "bold"))

    def _schedule_refresh(self) -> None:
        self._refresh_job = self.after(REFRESH_MS, self.refresh_now)

    def _cancel_scheduled_refresh(self) -> None:
        if self._refresh_job is not None:
            self.after_cancel(self._refresh_job)
            self._refresh_job = None


def main() -> None:
    UsageWidget().mainloop()