# 第三方元件聲明

本專案依 GPL-3.0-or-later 授權（見 `LICENSE`），並使用或隨附下列元件。各元件的授權以其專案公布的內容為準。

| 元件 | 用途 | 授權 |
|---|---|---|
| [LibreDWG](https://www.gnu.org/software/libredwg/) | 把 DWG 轉成 DXF（`dwg2dxf`） | GPL-3.0-or-later |
| [ezdxf](https://github.com/mozman/ezdxf) | 讀取 DXF、繪製圖形 | MIT |
| [matplotlib](https://matplotlib.org/) | 輸出圖檔 | Matplotlib License（PSF 風格） |
| [NumPy](https://numpy.org/) | matplotlib 的相依套件 | BSD-3-Clause |
| [Pillow](https://python-pillow.org/) | 存成 JPG 與 PNG | MIT-CMU |
| [tkinterdnd2](https://github.com/Eliav2/tkinterdnd2) 與 tkdnd | 視窗拖放 | MIT |
| [Python](https://www.python.org/) 與 Tcl/Tk | 執行環境 | PSF License、Tcl/Tk License |
| [PyInstaller](https://pyinstaller.org/) | 打包成 exe（只用於建置） | GPL-2.0-or-later，附打包例外條款 |

## LibreDWG 原始碼

Windows 發布版隨附的 `dwg2dxf.exe` 與相關 DLL 是 LibreDWG 官方發布的未修改執行檔，建置時直接從下列位址下載並以 SHA256 驗證：

- 發布頁：https://github.com/LibreDWG/libredwg/releases/tag/0.14
- 原始碼：同一發布頁的 `libredwg-0.14.tar.xz`，或 https://git.savannah.gnu.org/git/libredwg.git
