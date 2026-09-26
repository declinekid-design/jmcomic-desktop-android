"""Import-compatible placeholder for curl_cffi.requests on Android."""


class AsyncSession:
    def __init__(self, *args, **kwargs):
        raise RuntimeError(
            "curl_cffi async client is not available in the Android build; "
            "use the requests-based client instead."
        )


class Session(AsyncSession):
    pass
