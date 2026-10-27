# DWG 轉圖檔

拖曳 `.dwg` 檔案到視窗，轉成 JPG 或 PNG。可選彩色或黑白、解析度與輸出位置，一次拖入多個檔案會依序處理。

## 下載與使用（Windows）

1. 到本專案的 [Releases](../../releases) 下載 `dwg-converter-windows-x64.zip`。
2. 解壓縮，執行裡面的 `dwg-converter.exe`，不需要安裝 Python。
3. 把 `.dwg` 拖進視窗，或點擊拖放區選擇檔案。轉換約需一到兩分鐘，完成後雙擊清單項目就能開啟圖片。

第一次執行時 Windows 可能跳出「Windows 已保護您的電腦」，這是因為程式沒有購買程式碼簽章。點「其他資訊」，再按「仍要執行」。

## macOS 與 Linux（尚未實機驗證）

沒有提供打包版，要自行安裝。程式碼已避開 Windows 專用的部分，但作者目前沒有 macOS 與 Linux 的環境，沒有實際測試過，遇到問題歡迎回報。

1. 安裝 Python 3.10 以上，且要包含 tkinter。Linux 可用 `sudo apt install python3-tk`。
2. 安裝 LibreDWG，程式會在系統路徑找 `dwg2dxf`：
   - macOS：`brew install libredwg`
   - Linux：`sudo apt install libredwg-tools`（套件名稱依發行版而異）
3. 安裝本程式並執行：

```bash
pipx install git+https://github.com/wkai2573/dwg-converter
dwg-converter
```

Linux 若圖面的中文變成方塊，需要安裝中文字型，例如 `sudo apt install fonts-noto-cjk`。

## 已知限制

- 只畫模型空間，不處理 DWG 裡的配置分頁。
- 轉換靠 LibreDWG 逆向解析 DWG 格式，新版 DWG 可能缺少部分圖層或物件。
- 少數特殊字型的文字會顯示成方塊。
- 輸出是整個模型空間的一張大圖，圖紙很多時單張圖紙會很小，需要放大檢視。

## 開發

```bash
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m dwg_converter
```

命令列模式，沒有視窗，輸出失敗時會在輸出檔旁寫一個 `.error.txt`：

```bash
.\.venv\Scripts\python.exe -m dwg_converter --cli 輸入.dwg 輸出.jpg [mono]
```

## 打包（Windows）

```bash
pwsh -File .\build.ps1
```

腳本會自動下載並驗證 LibreDWG，再用 PyInstaller 打包。成品在 `dist\dwg-converter`，要整個資料夾一起搬移。推送 `v1.0.0` 這類標籤時，GitHub Actions 會自動打包並建立 Release。

## 授權

GPL-3.0-or-later，見 [LICENSE](LICENSE)。第三方元件見 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
