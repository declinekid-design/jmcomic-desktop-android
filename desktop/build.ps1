param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$desktopDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $desktopDir
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$mirror = "https://pypi.tuna.tsinghua.edu.cn/simple"

if (-not (Test-Path -LiteralPath $venvPython)) {
    python -m venv (Join-Path $projectRoot ".venv")
}

if (-not $SkipInstall) {
    & $venvPython -m pip install --upgrade pip -i $mirror
    & $venvPython -m pip install -r (Join-Path $desktopDir "requirements-build.txt") -i $mirror
}

& $venvPython (Join-Path $desktopDir "create_icon.py")
& $venvPython -m PyInstaller --noconfirm --clean (Join-Path $desktopDir "JMComicDesktop.spec")

$distDir = Join-Path $projectRoot "dist"
$updaterDir = Join-Path $distDir "JMComicDesktopUpdater"
$bundledUpdaterDir = Join-Path $distDir "JMComicDesktop\updater"
if (-not (Test-Path -LiteralPath (Join-Path $updaterDir "JMComicDesktopUpdater.exe"))) {
    throw "Updater executable was not generated: $updaterDir"
}
if (Test-Path -LiteralPath $bundledUpdaterDir) {
    Remove-Item -LiteralPath $bundledUpdaterDir -Recurse -Force
}
Copy-Item -LiteralPath $updaterDir -Destination $bundledUpdaterDir -Recurse -Force
