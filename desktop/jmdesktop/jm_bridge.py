from __future__ import annotations


_IMPORT_ERROR: BaseException | None = None

try:
    import yaml

    import jmcomic
    from jmcomic import JmModuleConfig
    from jmcomic.jm_config import jm_logger
    from jmcomic.jm_downloader import JmDownloader
    from jmcomic.jm_task_context import jm_task_context
    from jmcomic.jm_toolkit import JmcomicText
except BaseException as exc:
    _IMPORT_ERROR = exc
    yaml = None
    jmcomic = None
    JmModuleConfig = None
    jm_logger = None
    JmDownloader = None
    jm_task_context = None
    JmcomicText = None


def core_version() -> str:
    if jmcomic is None:
        return "unknown"
    return str(getattr(jmcomic, "__version__", "unknown"))


if JmModuleConfig is not None:
    JmModuleConfig.AFIELD_ADVICE["jm_id"] = (
        lambda album: f"JM{album.album_id}"
    )
