# Credits

## Upstream project

This project uses and extends the Python API and downloader from:

- Project: **JMComic-Crawler-Python**
- Author: **hect0x7**
- Repository: [https://github.com/hect0x7/JMComic-Crawler-Python](https://github.com/hect0x7/JMComic-Crawler-Python)
- License: MIT

The Windows desktop application is a graphical front end built around that
upstream Python package. The Android application is a separate WebView browser
that does not contain the Windows desktop downloader.

Special thanks to hect0x7 and all contributors of the upstream project for the
API, downloader, plugin system and documentation that make this work possible.

## Other dependencies

- [PySide6 / Qt for Python](https://doc.qt.io/qtforpython/) for the Windows GUI
  and embedded browser.
- [PyInstaller](https://pyinstaller.org/) for building the portable Windows
  application.
- [Android SDK](https://developer.android.com/studio) and JDK 17 for building
  the Android APK.

