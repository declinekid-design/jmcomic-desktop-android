from __future__ import annotations

import html
from typing import Iterable

from .jm_bridge import JmcomicText


SEPARATOR = "─" * 50


def _join_values(values: Iterable | str | None, default: str = "未知") -> str:
    if values is None:
        return default
    if isinstance(values, str):
        text = values.strip()
        return text or default
    items = [str(value).strip() for value in values if str(value).strip()]
    return ", ".join(items) if items else default


def chapter_label(index: int, name: str, photo_id: str) -> str:
    return f"第{index}话  {name}  (ID: {photo_id})"


def album_link(album) -> str:
    return JmcomicText.format_album_url(album.album_id)


def format_album_plain(album, query_text: str) -> str:
    lines = [
        f"🔍 正在查询 禁漫车号 - [{query_text}] 的详情...",
        SEPARATOR,
        f"📖 标题:  {album.name}",
        f"🆔 ID:    JM{album.album_id}",
        f"🔗 链接:  {album_link(album)}",
        f"✍️ 作者:  {_join_values(album.authors)}",
        SEPARATOR,
        f"📅 发布日期:  {album.pub_date or '未知'}",
        f"📅 更新日期:  {album.update_date or '未知'}",
        f"📄 总页数:    {album.page_count}",
        f"👀 观看:      {album.views or '未知'}",
        f"❤️ 点赞:     {album.likes or '未知'}",
        f"💬 评论:      {album.comment_count}",
        SEPARATOR,
        f"🏷️ 标签:  {_join_values(album.tags)}",
        f"🎭 人物:  {_join_values(album.actors)}",
        f"📚 作品:  {_join_values(album.works)}",
    ]
    if album.description:
        lines.append(f"📝 简介:  {album.description}")
    lines.extend([SEPARATOR, f"📑 章节 ({len(album.episode_list)}):"])
    for photo_id, photo_index, photo_name in album.episode_list:
        lines.append(
            f"    {chapter_label(int(photo_index), str(photo_name), str(photo_id))}"
        )
    lines.extend([SEPARATOR, "查询完成，请选择章节范围。"])
    return "\n".join(lines)


def format_album_html(album, query_text: str) -> str:
    def esc(value) -> str:
        return html.escape(str(value))

    link = album_link(album)
    episode_rows = "\n".join(
        (
            "<li>"
            f"{esc(chapter_label(int(photo_index), str(photo_name), str(photo_id)))}"
            "</li>"
        )
        for photo_id, photo_index, photo_name in album.episode_list
    )
    description = ""
    if album.description:
        description = (
            f"<p><b>📝 简介：</b>{esc(album.description)}</p>"
        )
    return f"""
        <h2>作品详情</h2>
        <p>🔍 正在查询 禁漫车号 - <b>[{esc(query_text)}]</b> 的详情</p>
        <hr>
        <p><b>📖 标题：</b>{esc(album.name)}</p>
        <p><b>🆔 ID：</b>JM{esc(album.album_id)}</p>
        <p><b>🔗 链接：</b><a href="{esc(link)}">{esc(link)}</a></p>
        <p><b>✍️ 作者：</b>{esc(_join_values(album.authors))}</p>
        <hr>
        <p><b>📅 发布日期：</b>{esc(album.pub_date or "未知")}</p>
        <p><b>📅 更新日期：</b>{esc(album.update_date or "未知")}</p>
        <p><b>📄 总页数：</b>{esc(album.page_count)}</p>
        <p><b>👀 观看：</b>{esc(album.views or "未知")}</p>
        <p><b>❤️ 点赞：</b>{esc(album.likes or "未知")}</p>
        <p><b>💬 评论：</b>{esc(album.comment_count)}</p>
        <hr>
        <p><b>🏷️ 标签：</b>{esc(_join_values(album.tags))}</p>
        <p><b>🎭 人物：</b>{esc(_join_values(album.actors))}</p>
        <p><b>📚 作品：</b>{esc(_join_values(album.works))}</p>
        {description}
        <hr>
        <h3>📑 章节（{len(album.episode_list)}）</h3>
        <ol>{episode_rows}</ol>
    """


def query_pending_html(query_text: str) -> str:
    return (
        "<h2>作品详情</h2>"
        f"<p>🔍 正在查询 <b>[{html.escape(query_text)}]</b> 的详情，请稍候...</p>"
    )


def query_error_html(message: str) -> str:
    return (
        "<h2>作品详情</h2>"
        "<p><b>查询失败</b></p>"
        f"<p>{html.escape(message)}</p>"
    )
