# -*- coding: utf-8 -*-
"""
渲染层：把筛选结果套进 templates/email.html，生成最终邮件。

邮件 HTML 和网页 HTML 不一样，有几条硬规矩（不然在 QQ 邮箱/Outlook 里会散架）：
1. 用 <table> 排版，不用 flex/grid。
2. 关键样式写在内联 style 里，不能只写在 <head> 的 <style> 里。
3. 宽度固定 640px，靠 media query 在手机上做微调。
"""

from __future__ import annotations

import html
import re
from pathlib import Path

FONT = "-apple-system,'PingFang SC','Microsoft YaHei','Helvetica Neue',Arial,sans-serif"
DEFAULT_THEME = "#2563eb"
# 长英文单词/链接不换行会把表格撑破，这几个属性是邮件的常规防护
BREAK = "word-break:break-word;overflow-wrap:anywhere;"


def _e(text) -> str:
    """转义，避免内容里的 < > & 把版面弄坏。"""
    return html.escape(str(text or ""), quote=True)


def _clip(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def _chip(text: str, color: str = "#475569", background: str = "#f1f5f9") -> str:
    if not text:
        return ""
    return (
        f'<span style="display:inline-block;background-color:{background};color:{color};'
        f'font-size:11px;line-height:1.6;padding:2px 8px;border-radius:999px;margin:0 6px 6px 0;'
        f'font-family:{FONT};white-space:nowrap;">{_e(text)}</span>'
    )


def _field_row(label: str, value: str, color: str) -> str:
    if not value:
        return ""
    return (
        '<tr>'
        f'<td class="label-col" width="52" valign="top" '
        f'style="font-family:{FONT};font-size:11px;font-weight:700;color:{color};'
        f'line-height:1.75;padding:3px 0;white-space:nowrap;">{_e(label)}</td>'
        f'<td style="font-family:{FONT};font-size:13px;color:#3f4a5a;line-height:1.75;'
        f'padding:3px 0;{BREAK}">{_e(value)}</td>'
        '</tr>'
    )


def _item_card(item: dict, theme: str) -> str:
    chips = "".join([
        _chip(item.get("difficulty", ""), "#1d4ed8", "#e8efff"),
        _chip(item.get("cost", ""), "#047857", "#e7f7ef"),
        _chip(item.get("source", ""), "#5b6472", "#f1f5f9"),
        _chip(item.get("published", ""), "#9aa3b2", "#f8fafc"),
        *[_chip(tag, "#7c3aed", "#f2ecff") for tag in item.get("tags", [])],
    ])
    rows = (
        _field_row("是什么", item.get("what", ""), "#64748b")
        + _field_row("为什么", item.get("why", ""), theme)
        + _field_row("怎么做", item.get("how", ""), "#64748b")
    )
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="margin:0 0 12px 0;">'
        '<tr><td class="card" style="background-color:#ffffff;border:1px solid #e8edf5;'
        f'border-left:4px solid {theme};border-radius:12px;padding:14px 16px 12px 16px;">'
        f'<a class="item-title" href="{_e(item.get("url"))}" '
        f'style="font-family:{FONT};font-size:14.5px;font-weight:700;color:#131a26;'
        f'line-height:1.6;text-decoration:none;display:block;{BREAK}">'
        f'{_e(_clip(item.get("title", ""), 160))}</a>'
        f'<div style="margin-top:8px;">{chips}</div>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="margin-top:4px;">{rows}</table>'
        f'<a href="{_e(item.get("url"))}" style="font-family:{FONT};font-size:12px;'
        f'color:{theme};text-decoration:none;display:inline-block;margin-top:6px;{BREAK}">查看原文 →</a>'
        '</td></tr></table>'
    )


def _section_block(name: str, icon: str, desc: str, theme: str, items: list[dict]) -> str:
    cards = "".join(_item_card(item, theme) for item in items)
    return (
        '<tr><td class="pad" style="padding:24px 28px 0 28px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        f'<td style="font-family:{FONT};font-size:15px;font-weight:800;color:{theme};">{icon} {_e(name)}</td>'
        f'<td align="right" style="font-family:{FONT};font-size:11px;color:#9aa3b2;">{len(items)} 条</td>'
        '</tr></table>'
        f'<div style="height:2px;background-color:{theme};opacity:0.22;border-radius:2px;margin-top:8px;"></div>'
        f'<div style="font-family:{FONT};font-size:12px;color:#9aa3b2;margin-top:6px;">{_e(desc)}</div>'
        '</td></tr>'
        f'<tr><td class="pad" style="padding:14px 28px 0 28px;">{cards}</td></tr>'
    )


def _highlight_block(item, reason: str) -> str:
    if not item:
        return ""
    return (
        '<tr><td class="pad" style="padding:24px 28px 0 28px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="background-color:#fffbeb;border:1px solid #fde68a;border-left:4px solid #f59e0b;'
        'border-radius:12px;">'
        '<tr><td style="padding:16px 18px;">'
        f'<div style="font-family:{FONT};font-size:12px;font-weight:800;color:#b45309;letter-spacing:1px;">'
        '🎯 本周只值得动手试的一件事</div>'
        f'<a href="{_e(item.get("url"))}" style="font-family:{FONT};font-size:15px;font-weight:700;'
        f'color:#92400e;text-decoration:none;display:block;margin-top:8px;line-height:1.6;">'
        f'{_e(_clip(item.get("title", ""), 140))}</a>'
        f'<div style="font-family:{FONT};font-size:13px;color:#78350f;line-height:1.75;margin-top:6px;">'
        f'{_e(reason)}</div>'
        '</td></tr></table></td></tr>'
    )


def _glossary_block(glossary: list[dict]) -> str:
    if not glossary:
        return ""
    rows = "".join(
        '<tr>'
        f'<td width="112" valign="top" style="font-family:{FONT};font-size:13px;font-weight:700;'
        f'color:#1e293b;padding:6px 10px 6px 0;line-height:1.7;">{_e(_clip(entry["term"], 20))}</td>'
        f'<td style="font-family:{FONT};font-size:13px;color:#475569;line-height:1.7;padding:6px 0;">'
        f'{_e(_clip(entry["plain"], 90))}</td>'
        '</tr>'
        for entry in glossary
    )
    return (
        '<tr><td class="pad" style="padding:26px 28px 0 28px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="background-color:#f8fafc;border:1px solid #e8edf5;border-radius:12px;">'
        '<tr><td style="padding:16px 18px;">'
        f'<div style="font-family:{FONT};font-size:13px;font-weight:800;color:#0f172a;">📚 本期术语小抄</div>'
        f'<div style="font-family:{FONT};font-size:12px;color:#9aa3b2;margin-top:4px;">'
        '看不懂的词，这里用大白话解释</div>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="margin-top:8px;">{rows}</table>'
        '</td></tr></table></td></tr>'
    )


def build_html(template_path: str, context: dict) -> str:
    """把占位符替换成真实内容。"""
    template = Path(template_path).read_text(encoding="utf-8")
    placeholders = {
        "{{SUBJECT}}": _e(context["subject"]),
        "{{PREHEADER}}": _e(context["preheader"]),
        "{{ISSUE_NO}}": _e(context["issue_no"]),
        "{{DATE_RANGE}}": _e(context["date_range"]),
        "{{INTRO}}": _e(context["intro"]),
        "{{RAW_COUNT}}": _e(context["raw_count"]),
        "{{ITEM_COUNT}}": _e(context["item_count"]),
        "{{SOURCE_COUNT}}": _e(context["source_count"]),
        "{{ROTATING_TOPIC}}": _e(context["rotating_topic"]),
        "{{HIGHLIGHT_BLOCK}}": context["highlight_block"],
        "{{SECTIONS_HTML}}": context["sections_html"],
        "{{GLOSSARY_BLOCK}}": context["glossary_block"],
        "{{FOOTER_NOTE}}": _e(context["footer_note"]),
        "{{SOURCES_NOTE}}": _e(context["sources_note"]),
        "{{FAILURE_NOTE}}": _e(context.get("failure_note", "")),
    }
    for token, value in placeholders.items():
        template = template.replace(token, value)
    return template


def build_markdown(context: dict, sections: list[tuple[dict, list[dict]]]) -> str:
    """另外生成一份 Markdown，方便本地查看和排查问题。"""
    lines = [
        f"# {context['subject']}",
        "",
        f"- 期号：第 {context['issue_no']} 期",
        f"- 时间范围：{context['date_range']}",
        f"- 本期专题：{context['rotating_topic']}",
        f"- 候选 {context['raw_count']} 条 → 入选 {context['item_count']} 条",
        "",
        f"> {context['intro']}",
        "",
    ]
    highlight = context.get("highlight_item")
    if highlight:
        lines += [
            "## 🎯 本周只值得动手试的一件事",
            "",
            f"**[{highlight.get('title')}]({highlight.get('url')})**",
            "",
            context.get("highlight_reason", ""),
            "",
        ]
    for meta, items in sections:
        lines += [f"## {meta['icon']} {meta['key']}（{len(items)} 条）", ""]
        for item in items:
            lines += [
                f"### [{item.get('title')}]({item.get('url')})",
                "",
                f"- 是什么：{item.get('what', '')}",
                f"- 为什么：{item.get('why', '')}",
                f"- 怎么做：{item.get('how', '')}",
                f"- 属性：{item.get('difficulty', '')} / {item.get('cost', '')} / "
                f"{item.get('source', '')} / {item.get('published', '')}",
                "",
            ]
    glossary = context.get("glossary") or []
    if glossary:
        lines += ["## 📚 本期术语小抄", ""]
        lines += [f"- **{entry['term']}**：{entry['plain']}" for entry in glossary]
        lines += [""]
    lines += ["---", "", context["footer_note"], ""]
    return "\n".join(lines)


def build_sections(kept: list[dict], section_meta: list[dict]) -> list[tuple[dict, list[dict]]]:
    """按栏目分组，保持 config 里的顺序；空栏目自动隐藏。"""
    grouped: list[tuple[dict, list[dict]]] = []
    known = {meta["key"] for meta in section_meta}
    for meta in section_meta:
        items = [item for item in kept if item.get("column") == meta["key"]]
        if items:
            grouped.append((meta, items))
    others = [item for item in kept if item.get("column") not in known]
    if others:
        grouped.append((
            {"key": "其它值得一看", "icon": "✨", "desc": "没归进上面几类，但也不错", "theme": "#0f766e"},
            others,
        ))
    return grouped


def sections_to_html(sections: list[tuple[dict, list[dict]]]) -> str:
    return "".join(
        _section_block(meta["key"], meta.get("icon", "•"), meta.get("desc", ""),
                       meta.get("theme", DEFAULT_THEME), items)
        for meta, items in sections
    )


def highlight_to_html(item, reason: str) -> str:
    return _highlight_block(item, reason)


def glossary_to_html(glossary: list[dict]) -> str:
    return _glossary_block(glossary)
