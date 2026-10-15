# -*- coding: utf-8 -*-
"""
跨周去重历史。

作用：上周推过的内容，这周不会再推一遍。
文件本身很小（只存 URL 和标题），会由 GitHub Actions 自动提交回仓库，
这样定时任务也顺便"保活"（公共仓库 60 天没有活动会被暂停定时任务）。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

EMPTY = {"version": 1, "items": []}


def _norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", (title or "").lower())


def keys_of(item: dict) -> list[str]:
    url = (item.get("url") or "").strip().lower().rstrip("/")
    title = _norm_title(item.get("title", ""))
    return [k for k in (f"u:{url}" if url else "", f"t:{title}" if title else "") if k]


def load(path: str) -> dict:
    file = Path(path)
    if not file.exists():
        return dict(EMPTY)
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return dict(EMPTY)
    if not isinstance(data, dict):
        return dict(EMPTY)
    data.setdefault("version", 1)
    data.setdefault("items", [])
    return data


def known_keys(data: dict) -> set[str]:
    collected: set[str] = set()
    for record in data.get("items", []):
        collected.update(keys_of(record))
    return collected


def split_new(items: list[dict], data: dict) -> tuple[list[dict], int]:
    """把条目分成"新的"和"以前推过的"。返回 (新条目, 被排除的数量)。"""
    known = known_keys(data)
    fresh, excluded = [], 0
    for item in items:
        keys = keys_of(item)
        if keys and any(key in known for key in keys):
            excluded += 1
            continue
        fresh.append(item)
    return fresh, excluded


def append(data: dict, items: list[dict], issued_on: str) -> int:
    """把这次成功发出的条目加进内存里的历史（会修改 data）。返回新增数量。"""
    known = known_keys(data)
    added = 0
    for item in items:
        keys = keys_of(item)
        if not keys or any(key in known for key in keys):
            continue
        data.setdefault("items", []).append({
            "title": (item.get("title") or "")[:200],
            "url": item.get("url") or "",
            "column": item.get("column") or "",
            "first_seen": issued_on,
        })
        known.update(keys)
        added += 1

    # 只保留最近 800 条，避免文件无限变大
    data["items"] = data.get("items", [])[-800:]
    return added


def save(path: str, data: dict) -> None:
    """把历史写回磁盘。"""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
