# -*- mode: python ; coding: utf-8 -*-

import os
import sys
import sysconfig
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules


desktop_dir = Path(SPECPATH)
project_root = desktop_dir.parent
src_dir = project_root / "src"
icon_path = desktop_dir / "assets" / "app.ico"
debug_console = os.environ.get("JMCOMIC_DESKTOP_CONSOLE") == "1"
app_name = "JMComicDesktopDebug" if debug_console else "JMComicDesktop"
sys.path.insert(0, str(desktop_dir))

datas = []
binaries = []
hiddenimports = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "yaml",
    "jmdesktop",
    "jmdesktop.browser",
    "jmdesktop.login",
    "jmdesktop.session",
    "jmdesktop.update_manager",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebChannel",
    "PySide6.QtNetwork",
]
datas += [(str(icon_path), "assets")]

site_packages = Path(sysconfig.get_paths()["purelib"])
for relative_path, destination in (
    ("PySide6/msvcp140_codecvt_ids.dll", "PySide6"),
    ("shiboken6/msvcp140_codecvt_ids.dll", "shiboken6"),
):
    dependency = site_packages / relative_path
    if dependency.exists():
        binaries += [(str(dependency), destination)]

for package_name in ("jmcomic", "common", "curl_cffi", "PIL", "Crypto", "yaml"):
    try:
        package_datas, package_binaries, package_hiddenimports = collect_all(package_name)
    except Exception:
        continue
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

for package_name in ("curl_cffi", "common"):
    try:
        hiddenimports += collect_submodules(package_name)
    except Exception:
        pass

try:
    hiddenimports += collect_submodules("jmdesktop")
except Exception:
    pass

a = Analysis(
    [str(desktop_dir / "jmcomic_desktop.py")],
    pathex=[str(src_dir), str(desktop_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "unittest", "tkinter", "_tkinter", "PIL._tkinter_finder"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=debug_console,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_path) if icon_path.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=app_name,
)

# The updater must be a separate executable so it can replace the main EXE
# after the application exits.
a_updater = Analysis(
    [str(desktop_dir / "updater_app.py")],
    pathex=[str(desktop_dir)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PySide6",
        "jmcomic",
        "common",
        "curl_cffi",
        "PIL",
        "Crypto",
        "yaml",
        "pytest",
        "unittest",
        "tkinter",
    ],
    noarchive=False,
    optimize=1,
)
pyz_updater = PYZ(a_updater.pure)
updater_exe = EXE(
    pyz_updater,
    a_updater.scripts,
    [],
    exclude_binaries=True,
    name="JMComicDesktopUpdater",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
updater_coll = COLLECT(
    updater_exe,
    a_updater.binaries,
    a_updater.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="JMComicDesktopUpdater",
)
