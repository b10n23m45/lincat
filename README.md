# Codex Usage Widget

一個 Windows 置頂小工具，用繁體中文或英文顯示 Codex 剩餘用量，支援系統匣縮放、專屬桌面捷徑、主題切換與透明度調整。

小工具會優先讀取 `CODEX_USAGE_READ_API_URL` 指定的 app-server read API。端點需回傳 JSON，格式可以是頂層 `rate_limits`，或事件格式 `payload.rate_limits`。如果沒有設定 read API，會 fallback 讀取 `%USERPROFILE%\.codex\sessions` 裡最新的 `payload.rate_limits`。

## 顯示內容

- `5H`：5 小時窗口，顯示剩餘百分比、已用百分比與重置時間。
- `7DAY`：每週上限，顯示剩餘百分比、已用百分比與重置時間。
- 多國語言：支援繁體中文與英文，預設跟隨系統語言；非繁中或英文系統會使用英文。
- 主題：支援 Tiffany Blue 淺色主題與 Monokai 深色主題，預設跟隨 Windows 系統 App 深淺色設定。
- 透明度：使用面板上方 slider 調整 0% 到 100%，預設 75%。
- 系統匣圖示：用主要剩餘用量，也就是 `5H` 剩餘百分比，繪製大字動態圖示。
- 系統匣 tooltip：顯示 `5H` 與 `7DAY` 剩餘用量。
- 面板雙擊：縮到系統匣。
- 系統匣預設動作：顯示置頂面板；Windows 上可用點擊/雙擊觸發，其他平台依系統匣實作而定。
- 按鈕：語言圖示、主題圖示、`刷新` / `Refresh`、`重新連線` / `Reconnect`、`關閉` / `Close`。
- 自動更新頻率：每 10 分鐘一次。
- 桌面捷徑：Windows 上第一次啟動時會自動建立使用專屬圖示的 `Codex Usage Widget.lnk`；捷徑使用 `pythonw.exe -m codex_usage_widget`，只顯示 UI，不會開啟 PowerShell/console 視窗。

## 專屬圖示

專案包含專屬圖示資產：

- `assets/codex-usage-widget-icon.png`：高解析 PNG 設計稿。
- `assets/codex-usage-widget.ico`：Windows `.ico` 檔。
- `src/codex_usage_widget/assets/`：打包進 `uv tool` 的圖示資產。

桌面捷徑會自動使用安裝環境中的 `codex-usage-widget.ico`。

## 安裝成 uv tool

```powershell
cd C:\Users\b10n2\codex-usage-widget
uv tool install --reinstall .
```

安裝後可直接啟動；第一次啟動會在桌面建立捷徑：

```powershell
codex-usage-widget
```

如果 PowerShell 找不到 `codex-usage-widget`，請確認 UV tool bin 目錄已在 `PATH` 裡：

```powershell
uv tool dir --bin
```

## 更新或解除安裝

本機程式碼有修改後，重新安裝：

```powershell
cd C:\Users\b10n2\codex-usage-widget
uv tool install --reinstall .
```

如果重新安裝時出現 `存取被拒`，通常是小工具還在背景執行；先關閉系統匣裡的 Codex Usage Widget，再重新執行安裝。

解除安裝：

```powershell
uv tool uninstall codex-usage-widget
```

## 開發模式啟動

```powershell
cd C:\Users\b10n2\codex-usage-widget
.\run-widget.ps1
```

`run-widget.ps1` 使用 `uv run --no-project --python 3.13 --with pystray --with pillow`，Python runtime 與套件由 UV 管理，不需要專案內虛擬環境。

## 使用 Read API

```powershell
$env:CODEX_USAGE_READ_API_URL = "http://127.0.0.1:<port>/<read-endpoint>"
codex-usage-widget
```

## 驗證

不開視窗驗證資料：

```powershell
$env:PYTHONPATH = "C:\Users\b10n2\codex-usage-widget\src"
uv run --no-project --python 3.13 --with pystray --with pillow python -c "from codex_usage_widget.reader import read_latest_usage; print(read_latest_usage())"
```

提交前建議驗證：

```powershell
uv run --no-project --python 3.13 python -m py_compile src\codex_usage_widget\app.py src\codex_usage_widget\reader.py src\codex_usage_widget\__main__.py src\codex_usage_widget\__init__.py
uv build
uv tool install --reinstall .
```
