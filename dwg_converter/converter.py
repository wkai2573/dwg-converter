"""DWG 轉圖檔核心：先用 LibreDWG 轉成 DXF，再用 ezdxf 與 matplotlib 畫成圖。"""

import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

PIXELS_PER_INCH = 100
IS_WINDOWS = sys.platform == "win32"
DWG2DXF = "dwg2dxf.exe" if IS_WINDOWS else "dwg2dxf"
FONT_CANDIDATES = [
    "Microsoft JhengHei",
    "Microsoft YaHei",
    "SimHei",
    "PingFang TC",
    "Heiti TC",
    "Noto Sans CJK TC",
    "Noto Sans TC",
    "Source Han Sans TC",
    "WenQuanYi Zen Hei",
    "Arial Unicode MS",
]
INSTALL_HINTS = {
    "darwin": "brew install libredwg",
    "linux": "sudo apt install libredwg-tools（套件名稱依發行版而異）",
}

Progress = Callable[[str], None]


def base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def find_dwg2dxf() -> str:
    bundled = base_dir() / "vendor" / "libredwg" / DWG2DXF
    if bundled.is_file():
        return str(bundled)
    if found := shutil.which("dwg2dxf"):
        return found
    hint = INSTALL_HINTS.get(sys.platform)
    raise RuntimeError("找不到 dwg2dxf（LibreDWG）" + (f"，請先安裝：{hint}" if hint else ""))


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    n = 2
    while (candidate := path.with_name(f"{path.stem} ({n}){path.suffix}")).exists():
        n += 1
    return candidate


def dwg_to_dxf(dwg: Path, dxf: Path, on_start: Callable[[subprocess.Popen], None] | None = None) -> None:
    proc = subprocess.Popen(
        [find_dwg2dxf(), "-y", "-o", str(dxf), str(dwg)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0,
    )
    if on_start:
        on_start(proc)
    proc.wait()
    if not dxf.exists() or dxf.stat().st_size == 0:
        raise RuntimeError("DWG 轉 DXF 失敗，檔案可能損毀或版本不支援")


def robust_bounds(centers: list[tuple[float, float]], clip: float) -> tuple[float, float, float, float]:
    xs = sorted(c[0] for c in centers)
    ys = sorted(c[1] for c in centers)
    lo = int(len(centers) * clip)
    hi = max(lo, int(len(centers) * (1 - clip)) - 1)
    x0, x1, y0, y1 = xs[lo], xs[hi], ys[lo], ys[hi]
    pad = 0.03 * max(x1 - x0, y1 - y0, 1.0)
    return x0 - pad, x1 + pad, y0 - pad, y1 + pad


def render_dxf(
    dxf: Path,
    out: Path,
    *,
    color: bool,
    long_side_px: int,
    auto_crop: bool,
    progress: Progress,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ezdxf import bbox, recover
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

    plt.rcParams["font.sans-serif"] = FONT_CANDIDATES
    plt.rcParams["axes.unicode_minus"] = False

    progress("讀取圖形")
    doc, _ = recover.readfile(str(dxf))
    msp = doc.modelspace()

    progress("計算取景範圍")
    if auto_crop:
        centers = []
        for entity in msp:
            box = bbox.extents([entity], fast=True)
            if box.has_data:
                centers.append((box.center.x, box.center.y))
        if not centers:
            raise RuntimeError("模型空間沒有可繪製的圖元")
        x0, x1, y0, y1 = robust_bounds(centers, 0.01)
    else:
        box = bbox.extents(msp, fast=True)
        if not box.has_data:
            raise RuntimeError("模型空間沒有可繪製的圖元")
        x0, x1, y0, y1 = box.extmin.x, box.extmax.x, box.extmin.y, box.extmax.y

    width, height = x1 - x0, y1 - y0
    scale = long_side_px / PIXELS_PER_INCH / max(width, height)

    progress("繪圖中")
    fig = plt.figure()
    try:
        ax = fig.add_axes([0, 0, 1, 1])
        config = Configuration(
            background_policy=BackgroundPolicy.WHITE,
            color_policy=ColorPolicy.COLOR if color else ColorPolicy.BLACK,
        )
        Frontend(RenderContext(doc), MatplotlibBackend(ax), config=config).draw_layout(msp)
        fig.set_size_inches(width * scale, height * scale)
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)

        progress("輸出圖檔")
        is_jpg = out.suffix.lower() in (".jpg", ".jpeg")
        fig.savefig(
            out,
            dpi=PIXELS_PER_INCH,
            facecolor="white",
            pil_kwargs={"quality": 92} if is_jpg else {},
        )
    finally:
        plt.close(fig)


def convert(
    dwg: Path,
    out: Path,
    *,
    color: bool = True,
    long_side_px: int = 12000,
    auto_crop: bool = True,
    progress: Progress = lambda _stage: None,
    on_process: Callable[[subprocess.Popen], None] | None = None,
) -> Path:
    out = unique_path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="dwgconv-") as tmp:
        dxf = Path(tmp) / "model.dxf"
        progress("轉換 DXF")
        dwg_to_dxf(dwg, dxf, on_process)
        render_dxf(dxf, out, color=color, long_side_px=long_side_px, auto_crop=auto_crop, progress=progress)
    return out
