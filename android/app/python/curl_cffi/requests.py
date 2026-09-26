"""Standard-library implementation of the curl_cffi.requests subset.

jmcomic only needs synchronous requests and response objects. Keeping this
module independent of the requests/urllib3 package chain avoids unreliable
native wheels in the Android build.
"""

from __future__ import annotations

import gzip
import json as _json
import ssl
import urllib.error
import urllib.parse
import urllib.request
import zlib
from http.cookies import SimpleCookie
from types import SimpleNamespace
from typing import Any, Mapping


class RequestException(Exception):
    """Base exception compatible with the requests exception hierarchy."""


class ConnectionError(RequestException):
    pass


class Timeout(RequestException):
    pass


class ProxyError(ConnectionError):
    pass


class SSLError(ConnectionError):
    pass


class HTTPError(RequestException):
    def __init__(self, message: str, response: Any = None) -> None:
        super().__init__(message)
        self.response = response


exceptions = SimpleNamespace(
    RequestException=RequestException,
    ConnectionError=ConnectionError,
    Timeout=Timeout,
    ProxyError=ProxyError,
    SSLError=SSLError,
    HTTPError=HTTPError,
)


class CaseInsensitiveDict(dict):
    def __init__(self, values: Mapping[str, Any] | None = None) -> None:
        super().__init__()
        if values:
            self.update(values)

    @staticmethod
    def _key(key: str) -> str:
        return str(key).lower()

    def __setitem__(self, key: str, value: Any) -> None:
        super().__setitem__(self._key(key), value)

    def __getitem__(self, key: str) -> Any:
        return super().__getitem__(self._key(key))

    def get(self, key: str, default: Any = None) -> Any:
        return super().get(self._key(key), default)

    def __contains__(self, key: object) -> bool:
        return super().__contains__(self._key(str(key)))

    def update(
        self,
        values: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        if values:
            for key, value in dict(values).items():
                self[key] = value
        for key, value in kwargs.items():
            self[key] = value


class _Request:
    def __init__(
        self,
        method: str,
        url: str,
        headers: Mapping[str, Any],
    ) -> None:
        self.method = method
        self.url = url
        self.headers = CaseInsensitiveDict(headers)


class Response:
    def __init__(
        self,
        *,
        content: bytes,
        status_code: int,
        url: str,
        headers: Mapping[str, Any],
        request: _Request,
        cookies: Mapping[str, str] | None = None,
        redirect_count: int = 0,
    ) -> None:
        self.content = content
        self.status_code = int(status_code)
        self.url = url
        self.headers = CaseInsensitiveDict(headers)
        self.request = request
        self.cookies = dict(cookies or {})
        self.redirect_count = redirect_count
        self.history: list[Response] = []
        self.encoding = self._detect_encoding()

    def _detect_encoding(self) -> str:
        content_type = str(self.headers.get("Content-Type") or "")
        for part in content_type.split(";")[1:]:
            key, separator, value = part.strip().partition("=")
            if separator and key.lower() == "charset":
                return value.strip("\"'") or "utf-8"
        return "utf-8"

    @property
    def text(self) -> str:
        return self.content.decode(self.encoding, errors="replace")

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 400

    def json(self, **kwargs: Any) -> Any:
        return _json.loads(self.text, **kwargs)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise HTTPError(
                f"{self.status_code} HTTP error for {self.url}",
                response=self,
            )


_UNSUPPORTED_OPTIONS = {
    "impersonate",
    "ja3",
    "akamai",
    "extra_fp",
    "default_headers",
    "default_encoding",
    "curl_options",
    "interface",
    "debug",
    "http_version",
    "stream",
    "hooks",
    "auth",
    "files",
    "cert",
    "is_image",
}


def _clean_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    for option in _UNSUPPORTED_OPTIONS:
        kwargs.pop(option, None)
    return kwargs


def _merge_headers(
    default_headers: Mapping[str, Any],
    request_headers: Mapping[str, Any] | None,
) -> CaseInsensitiveDict:
    headers = CaseInsensitiveDict(default_headers)
    if request_headers:
        headers.update(request_headers)
    return headers


def _encode_body(
    data: Any,
    json_body: Any,
    headers: CaseInsensitiveDict,
) -> bytes | None:
    if json_body is not None:
        headers.setdefault("content-type", "application/json")
        return _json.dumps(json_body).encode("utf-8")
    if data is None:
        return None
    if isinstance(data, bytes):
        return data
    if isinstance(data, str):
        return data.encode("utf-8")
    if isinstance(data, Mapping):
        headers.setdefault(
            "content-type",
            "application/x-www-form-urlencoded",
        )
        return urllib.parse.urlencode(data, doseq=True).encode("utf-8")
    return str(data).encode("utf-8")


def _cookie_header(cookies: Mapping[str, str]) -> str:
    return "; ".join(
        f"{key}={value}"
        for key, value in cookies.items()
        if value is not None
    )


def _parse_cookies(response: Any) -> dict[str, str]:
    cookies: dict[str, str] = {}
    get_all = getattr(response.headers, "get_all", None)
    headers = get_all("Set-Cookie", []) if get_all else []
    for header in headers or []:
        parsed = SimpleCookie()
        try:
            parsed.load(header)
        except BaseException:
            continue
        for key, morsel in parsed.items():
            cookies[key] = morsel.value
    return cookies


def _decode_content(content: bytes, headers: Mapping[str, Any]) -> bytes:
    encoding = str(
        CaseInsensitiveDict(headers).get("Content-Encoding") or ""
    ).lower()
    if encoding == "gzip" or content.startswith(b"\x1f\x8b"):
        return gzip.decompress(content)
    if encoding == "deflate":
        try:
            return zlib.decompress(content)
        except zlib.error:
            return zlib.decompress(content, -zlib.MAX_WBITS)
    return content


class Session:
    """Requests-like session with curl_cffi-only options removed."""

    def __init__(self, **kwargs: Any) -> None:
        self.headers = CaseInsensitiveDict(kwargs.pop("headers", None))
        self.cookies: dict[str, str] = dict(
            kwargs.pop("cookies", None) or {}
        )
        self.proxies = dict(kwargs.pop("proxies", None) or {})
        self.verify = kwargs.pop("verify", True)
        _clean_kwargs(kwargs)

    def request(self, method: str, url: str, **kwargs: Any) -> Response:
        kwargs = _clean_kwargs(kwargs)

        params = kwargs.pop("params", None)
        if params:
            query = urllib.parse.urlencode(params, doseq=True)
            separator = "&" if urllib.parse.urlparse(url).query else "?"
            url = f"{url}{separator}{query}"

        headers = _merge_headers(
            self.headers,
            kwargs.pop("headers", None),
        )
        request_cookies = dict(self.cookies)
        request_cookies.update(kwargs.pop("cookies", None) or {})
        if request_cookies and "Cookie" not in headers:
            headers["Cookie"] = _cookie_header(request_cookies)

        headers.setdefault(
            "User-Agent",
            "Mozilla/5.0 (Linux; Android 13) JMComicAndroid/1.0.1",
        )
        body = _encode_body(
            kwargs.pop("data", None),
            kwargs.pop("json", None),
            headers,
        )
        timeout = kwargs.pop("timeout", None) or 30
        allow_redirects = kwargs.pop("allow_redirects", True)
        proxies = kwargs.pop("proxies", None) or self.proxies
        verify = kwargs.pop("verify", self.verify)
        kwargs.pop("cert", None)

        request = urllib.request.Request(
            url,
            data=body,
            headers=dict(headers),
            method=str(method).upper(),
        )

        handlers: list[Any] = []
        if proxies:
            proxy_map = {
                str(key): str(value)
                for key, value in dict(proxies).items()
                if value
            }
            handlers.append(urllib.request.ProxyHandler(proxy_map))
        else:
            handlers.append(urllib.request.ProxyHandler({}))

        if allow_redirects is False:
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(
                    self,
                    *args: Any,
                    **kwargs: Any,
                ) -> None:
                    return None

            handlers.append(NoRedirect())

        context = None
        if verify is False:
            context = ssl._create_unverified_context()
        if context is not None:
            handlers.append(urllib.request.HTTPSHandler(context=context))

        opener = urllib.request.build_opener(*handlers)
        try:
            with opener.open(request, timeout=timeout) as raw_response:
                final_url = raw_response.geturl()
                response_headers = dict(raw_response.headers.items())
                response = Response(
                    content=_decode_content(
                        raw_response.read(),
                        response_headers,
                    ),
                    status_code=raw_response.getcode(),
                    url=final_url,
                    headers=response_headers,
                    request=_Request(
                        str(method).upper(),
                        final_url,
                        headers,
                    ),
                    cookies=_parse_cookies(raw_response),
                )
        except urllib.error.HTTPError as error:
            response_headers = dict(error.headers.items())
            response = Response(
                content=_decode_content(
                    error.read(),
                    response_headers,
                ),
                status_code=error.code,
                url=error.geturl(),
                headers=response_headers,
                request=_Request(
                    str(method).upper(),
                    error.geturl(),
                    headers,
                ),
                cookies=_parse_cookies(error),
            )
        except urllib.error.URLError as error:
            reason = error.reason
            if isinstance(reason, ssl.SSLError):
                raise SSLError(str(reason)) from error
            if "proxy" in str(reason).lower():
                raise ProxyError(str(reason)) from error
            raise ConnectionError(str(reason)) from error
        except TimeoutError as error:
            raise Timeout(str(error)) from error

        self.cookies.update(response.cookies)
        return response

    def get(self, url: str, **kwargs: Any) -> Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> Response:
        return self.request("POST", url, **kwargs)

    def close(self) -> None:
        pass

    def __enter__(self) -> "Session":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


def request(method: str, url: str, **kwargs: Any) -> Response:
    return Session().request(method, url, **kwargs)


def get(url: str, **kwargs: Any) -> Response:
    return request("GET", url, **kwargs)


def post(url: str, **kwargs: Any) -> Response:
    return request("POST", url, **kwargs)


class AsyncSession:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise RuntimeError(
            "curl_cffi async client is not available in the Android build; "
            "use the standard-library synchronous client instead."
        )
