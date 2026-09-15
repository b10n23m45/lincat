# Codex Usage Widget

一個 Windows 置頂小工具，用中文顯示 Codex 剩餘用量，並支援系統匣縮放。

小工具會優先讀取 `CODEX_USAGE_READ_API_URL` 指定的 app-server read API。端點需回傳 JSON，格式可以是頂層 `rate_limits`，或事件格式 `payload.rate_limits`。如果沒有設定 read API，會 fallback 讀取 `%USERPROFILE%\.codex\sessions` 裡最新的 `payload.rate_limits`。

## 顯示內容

- `5H`：5 小時窗口，顯示剩餘百分比、已用百分比與重置時間。
- `7DAY`：每週上限，顯示剩餘百分比、已用百分比與重置時間。
- 系統匣圖示：用主要剩餘用量，也就是 `5H` 剩餘百分比，繪製動態圖示。
- 系統匣 tooltip：顯示 `5H` 與 `7DAY` 剩餘用量。
- 面板雙擊：縮到系統匣。
- 系統匣預設動作：顯示置頂面板；Windows 上可用點擊/雙擊觸發，其他平台依系統匣實作而定。
- 按鈕：`刷新`、`重新連線`、`關閉`。
- 自動更新頻率：每 10 分鐘一次。

## 啟動

```powershell
cd C:\Users\b10n2\codex-usage-widget
.\run-widget.ps1
```

`run-widget.ps1` 使用 `uv run --no-project --python 3.13 --with pystray --with pillow`，Python runtime 與套件由 UV 管理，不需要專案內虛擬環境。

## 使用 Read API

```powershell
$env:CODEX_USAGE_READ_API_URL = "http://127.0.0.1:<port>/<read-endpoint>"
.\run-widget.ps1
```

## 不開視窗驗證資料

```powershell
$env:PYTHONPATH = "C:\Users\b10n2\codex-usage-widget\src"
uv run --no-project --python 3.13 --with pystray --with pillow python -c "from codex_usage_widget.reader import read_latest_usage; print(read_latest_usage())"
```