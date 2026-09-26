from __future__ import annotations

import ctypes
import json
import os
import tempfile
from secrets import token_bytes
from ctypes import wintypes
from datetime import datetime, timezone
from typing import Any

from Crypto.Cipher import AES

from .constants import APP_DIR, SESSION_PATH


_DPAPI_MAGIC = b"JMD1"
_AES_MAGIC = b"JMD2"
_ENTROPY = b"JMComicDesktop/session/v1"
_CRYPTPROTECT_UI_FORBIDDEN = 0x01
_SESSION_KEY_PATH = APP_DIR / "session.key"


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def _blob(data: bytes) -> tuple[_DataBlob, ctypes.Array]:
    buffer = ctypes.create_string_buffer(data)
    blob = _DataBlob(
        len(data),
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)),
    )
    return blob, buffer


def _dpapi_crypt(data: bytes, decrypt: bool) -> bytes:
    if os.name != "nt":
        raise RuntimeError("登录会话加密仅支持 Windows。")

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    input_blob, input_buffer = _blob(data)
    entropy_blob, entropy_buffer = _blob(_ENTROPY)
    output_blob = _DataBlob()

    if decrypt:
        function = crypt32.CryptUnprotectData
        description = None
    else:
        function = crypt32.CryptProtectData
        description = "JMComic Desktop login session"

    function.argtypes = [
        ctypes.POINTER(_DataBlob),
        wintypes.LPCWSTR,
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    function.restype = wintypes.BOOL
    success = function(
        ctypes.byref(input_blob),
        description,
        ctypes.byref(entropy_blob),
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(output_blob),
    )
    # Keep the buffers alive while the native call runs.
    _ = input_buffer, entropy_buffer
    if not success:
        raise ctypes.WinError()

    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        kernel32.LocalFree(output_blob.pbData)


def save_session(
    cookies: dict[str, str],
    username: str = "",
    persist: bool = True,
) -> None:
    if not persist:
        clear_session()
        return
    payload = {
        "version": 1,
        "username": username,
        "cookies": {str(key): str(value) for key, value in cookies.items()},
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    plaintext = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    try:
        encrypted = _DPAPI_MAGIC + _dpapi_crypt(plaintext, decrypt=False)
    except (OSError, RuntimeError, AttributeError):
        encrypted = _AES_MAGIC + _aes_encrypt(plaintext)
    SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb",
        dir=SESSION_PATH.parent,
        prefix="session-",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(encrypted)
        temp_path = handle.name
    os.replace(temp_path, SESSION_PATH)


def load_session() -> dict[str, Any] | None:
    try:
        raw = SESSION_PATH.read_bytes()
    except OSError:
        return None
    try:
        if raw.startswith(_DPAPI_MAGIC):
            decrypted = _dpapi_crypt(
                raw[len(_DPAPI_MAGIC) :],
                decrypt=True,
            )
        elif raw.startswith(_AES_MAGIC):
            decrypted = _aes_decrypt(raw[len(_AES_MAGIC) :])
        else:
            return None
        payload = json.loads(decrypted.decode("utf-8"))
    except (OSError, ValueError, TypeError, RuntimeError):
        return None
    if not isinstance(payload, dict) or not isinstance(
        payload.get("cookies"), dict
    ):
        return None
    return payload


def clear_session() -> None:
    for path in (SESSION_PATH, _SESSION_KEY_PATH):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def dpapi_roundtrip(data: bytes) -> bool:
    try:
        encrypted = _DPAPI_MAGIC + _dpapi_crypt(data, decrypt=False)
        decrypted = _dpapi_crypt(encrypted[len(_DPAPI_MAGIC) :], decrypt=True)
        return decrypted == data
    except (OSError, RuntimeError, AttributeError):
        try:
            encrypted = _AES_MAGIC + _aes_encrypt(data)
            return _aes_decrypt(encrypted[len(_AES_MAGIC) :]) == data
        except (OSError, ValueError, TypeError):
            return False


def _load_or_create_key() -> bytes:
    try:
        key = _SESSION_KEY_PATH.read_bytes()
        if len(key) == 32:
            return key
    except OSError:
        pass
    key = token_bytes(32)
    _SESSION_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb",
        dir=_SESSION_KEY_PATH.parent,
        prefix="session-key-",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(key)
        temp_path = handle.name
    os.replace(temp_path, _SESSION_KEY_PATH)
    return key


def _aes_encrypt(data: bytes) -> bytes:
    cipher = AES.new(
        _load_or_create_key(),
        AES.MODE_GCM,
        nonce=token_bytes(12),
    )
    ciphertext, tag = cipher.encrypt_and_digest(data)
    return cipher.nonce + tag + ciphertext


def _aes_decrypt(data: bytes) -> bytes:
    if len(data) < 28:
        raise ValueError("会话文件长度无效。")
    nonce, tag, ciphertext = data[:12], data[12:28], data[28:]
    cipher = AES.new(_load_or_create_key(), AES.MODE_GCM, nonce=nonce)
    return cipher.decrypt_and_verify(ciphertext, tag)
