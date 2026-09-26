"""Minimal import shim for Android builds.

jmcomic 2.7.7 imports its optional asynchronous HTTP client at package import
time.  The Android client intentionally uses the synchronous requests-based
client, so the async module only needs the symbol to exist during import.
"""

__version__ = "0.0.0-android-shim"
