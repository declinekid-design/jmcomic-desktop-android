# Credits

## Upstream project

This project uses and extends the Python API and downloader from:

- Project: **JMComic-Crawler-Python**
- Author: **hect0x7**
- Repository: [https://github.com/hect0x7/JMComic-Crawler-Python](https://github.com/hect0x7/JMComic-Crawler-Python)
- License: MIT

The Windows desktop application and Android application are graphical front
ends built around that upstream Python package. The Android app embeds Python
3.12 with Chaquopy and uses the same query, downloader and ZIP plugin behavior
as the Windows client.

Special thanks to hect0x7 and all contributors of the upstream project for the
API, downloader, plugin system and documentation that make this work possible.

## Other dependencies

- [PySide6 / Qt for Python](https://doc.qt.io/qtforpython/) for the Windows GUI
  and embedded browser.
- [PyInstaller](https://pyinstaller.org/) for building the portable Windows
  application.
- [Android SDK](https://developer.android.com/studio) and JDK 17 for building
  the Android APK.
- [Chaquopy](https://chaquo.com/chaquopy/) for embedding Python 3.12 in the
  Android application.
- [Pillow](https://python-pillow.org/), [PyYAML](https://pyyaml.org/) and
  [PyCryptodome](https://www.pycryptodome.org/) for Android image processing,
  configuration and encrypted sessions.
