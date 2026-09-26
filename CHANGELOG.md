# Changelog

## 2026-09-26

### Windows desktop 1.5.0

- Added an embedded browser window for browsing the companion comic site.
- Added light, dark, and follow-system themes.
- Added folder naming by comic ID or comic title.
- Added full album details and chapter start/end selection.
- Added multi-chapter ZIP output.
- Added encrypted account session persistence.
- Added signed manifest based self-update and rollback.
- Moved runtime data into the application directory instead of `%APPDATA%`.
- Preserved documentation, license, and source notices during updates.

### Android browser 1.0.0

- Added a native WebView browser for `https://comic18j-hbd.space/`.
- Added back, refresh, download history, and image reader screens.
- Cookies are retained by Android WebView.
- Downloads are delegated to Android DownloadManager.
- Built and verified as a debug APK for Android 8.0 and later.

The Android application does not reuse the Windows desktop downloader or ZIP
packager.
