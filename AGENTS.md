# 專案規範

## 使用 UV 管理 Python 環境

專案需要使用 Python 時：

- 一律使用 UV 建置 Python 環境，不要使用其他工具。
- 一律將 Python 安裝到 UV 的全域環境中，不要安裝到專案內。
- 若未指明，請使用 Python 3.13。
- 必要時使用 `uv init` 初始化專案。
- 使用 `uv add` / `uv remove` 管理套件。
- 使用 `uv run` 執行 Python 腳本檔。

## Codex Usage Widget 專案現況

專案位置：`C:\Users\b10n2\codex-usage-widget`

GitHub remote：`https://github.com/b10n23m45/lincat.git`

目前實作結果：

- Windows 置頂 Tkinter 小工具，顯示 Codex `5H` 與 `7DAY` 用量。
- 優先讀取 `CODEX_USAGE_READ_API_URL`，失敗時 fallback 到 `%USERPROFILE%\.codex\sessions`。
- 支援繁體中文與英文，預設跟隨系統語言；非繁中或英文系統使用英文。
- 支援 Tiffany Blue 淺色主題與 Monokai 深色主題，預設跟隨 Windows App 深淺色設定。
- 支援面板透明度 0% 到 100%，預設 75%。
- 面板上方以圖示按鈕切換語言與主題，透明度用 slider 控制。
- 支援雙擊面板縮到系統匣。
- 系統匣圖示以大字顯示主要 `5H` 剩餘百分比，避免縮小後難以辨識。
- 已包裝成 `uv tool`，安裝後命令為 `codex-usage-widget`。

重要檔案：

- `src/codex_usage_widget/app.py`：Tkinter UI、語系、主題、透明度、系統匣、動態 tray icon。
- `src/codex_usage_widget/reader.py`：Read API 與本機 Codex session 解析。
- `pyproject.toml`：依賴與 `[project.scripts]`，目前 script 是 `codex-usage-widget = "codex_usage_widget:main"`。
- `run-widget.ps1`：開發模式啟動腳本。
- `README.md`：使用者安裝與操作說明。

常用命令：

```powershell
cd C:\Users\b10n2\codex-usage-widget
uv tool install --reinstall .
codex-usage-widget
```

驗證命令：

```powershell
uv run --no-project --python 3.13 python -m py_compile src\codex_usage_widget\app.py src\codex_usage_widget\reader.py src\codex_usage_widget\__main__.py src\codex_usage_widget\__init__.py
uv build
uv tool install --reinstall .
uv tool list
Get-Command codex-usage-widget
```

維護注意事項：

- 修改 UI 字串時，同步更新 `TRANSLATIONS` 裡的 `zh-Hant` 與 `en`。
- 修改配色時，維持 `THEMES` 裡 light = Tiffany Blue、dark = Monokai 的定位。
- `pystray` callback 可能不在 Tk thread，涉及 UI 的操作要透過 `self.after(...)` 回到 Tk thread。
- 系統匣圖示需優先可讀性，不要塞回小 `%` 或進度條造成縮小後難辨識。
- 測試 GUI 可能短暫開窗；測完要明確 destroy。
- 執行 `uv build` 或編譯測試後，清理 `dist/` 與 `__pycache__/`，除非使用者明確要保留。
- 之前曾建立暫時 worktree：`C:\Users\b10n2\codex-usage-widget-worktree`。除非使用者要求，預設操作主專案路徑。


