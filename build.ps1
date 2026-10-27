$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$libredwgVersion = '0.14'
$libredwgSha256 = '1AD7E15344D20B3426C3435B078D82FB84B35062815946B2CCA9C5FC9810FEA8'
$libredwgDir = 'vendor\libredwg'
$bundled = 'dwg2dxf.exe', 'libredwg-0.dll', 'libiconv-2.dll', 'libpcre2-8-0.dll', 'libpcre2-16-0.dll'

if (-not (Test-Path "$libredwgDir\dwg2dxf.exe")) {
    $zip = Join-Path ([IO.Path]::GetTempPath()) "libredwg-$libredwgVersion-win64.zip"
    $url = "https://github.com/LibreDWG/libredwg/releases/download/$libredwgVersion/libredwg-$libredwgVersion-win64.zip"
    Invoke-WebRequest $url -OutFile $zip
    if ((Get-FileHash $zip -Algorithm SHA256).Hash -ne $libredwgSha256) {
        Remove-Item $zip
        throw 'LibreDWG 下載檔的 SHA256 不符，已中止'
    }
    Expand-Archive $zip -DestinationPath $libredwgDir -Force
    Remove-Item $zip
}

if (-not (Test-Path .venv)) {
    python -m venv .venv
}
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

$addData = $bundled | ForEach-Object { '--add-data'; "$libredwgDir\$_;vendor\libredwg" }
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --windowed --name dwg-converter --hidden-import matplotlib.backends.backend_svg @addData run.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller 打包失敗' }

# dwg2dxf.exe 會在自己的資料夾找 DLL，PyInstaller 另外複製到頂層的那份是重複的
foreach ($name in $bundled | Where-Object { $_ -like '*.dll' }) {
    Remove-Item "dist\dwg-converter\_internal\$name" -ErrorAction SilentlyContinue
}

Copy-Item LICENSE, THIRD_PARTY_NOTICES.md dist\dwg-converter\
