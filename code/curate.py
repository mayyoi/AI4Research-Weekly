# -*- coding: utf-8 -*-
"""
筛选层：去重 -> 预排序 -> 交给 AI 判断 -> 选出本期条目。

为什么要有"预排序"？
因为一周能抓到几百条，如果全丢给 AI，又慢又费额度，而且容易超过长度限制。
所以先用规则挑出最有潜力的 90 条，再让 AI 精挑。
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
import urllib.request
from datetime import date

import llm as llm_module

# 每个源最多先留多少条，避免某一个源（比如 arXiv）把名额全占满
PER_SOURCE_CAP = 12

# 这些词出现在标题里，说明和"AI 帮我做科研"基本无关，直接扔掉
NOISE_PATTERNS = [
    r"\bcrypto\b", r"\bnft\b", r"\bbitcoin\b", r"\betf\b", r"\bstock\b",
    r"\bsports?\b", r"\bmovie\b", r"\bcelebrity\b", r"\bhoroscope\b",
]

# 命中这些词说明内容可能真的和科研/AI 有关，加分
RELEVANT_HINTS = [
    "ai", "llm", "gpt", "gemini", "claude", "agent", "mcp", "skill", "prompt",
    "model", "dataset", "benchmark", "tool", "plugin", "workflow", "automation",
    "literature", "paper", "research", "review", "pubmed", "zotero", "obsidian",
    "bioinformatic", "single-cell", "genomic", "medical", "clinical", "imaging",
    "statistic", "python", "r package", "open source", "api",
]


def _norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", (title or "").lower())


def dedupe(items: list[dict]) -> list[dict]:
    """按 URL 和标题去重（不同源经常报道同一件事）。"""
    seen: set[str] = set()
    output = []
    for item in items:
        title_key = _norm_title(item.get("title", ""))
        url = (item.get("url") or "").strip().lower().rstrip("/")
        keys = [k for k in (f"u:{url}" if url else "", f"t:{title_key}" if title_key else "") if k]
        if not keys:
            continue
        if any(k in seen for k in keys):
            continue
        seen.update(keys)
        output.append(item)
    return output


def _freshness_score(published: str) -> float:
    iso = re.sub(r"[^0-9-]", "", published or "")
    try:
        delta = (date.today() - date.fromisoformat(iso[:10])).days
    except ValueError:
        return 3.0
    if delta <= 3:
        return 10.0
    if delta <= 7:
        return 8.0
    if delta <= 14:
        return 6.0
    return 4.0


def heuristic_score(item: dict) -> float:
    """纯规则打分，用来决定"哪些内容值得送去给 AI 看"。"""
    title = (item.get("title") or "").lower()
    summary = (item.get("summary") or "").lower()
    score = _freshness_score(item.get("published", ""))
    score += sum(1.6 for hint in RELEVANT_HINTS if hint in title)
    score += sum(0.5 for hint in RELEVANT_HINTS if hint in summary)
    if len(item.get("summary") or "") > 120:
        score += 1.5  # 有实质内容，不是一句空标题
    if any(re.search(pattern, title) for pattern in NOISE_PATTERNS):
        score -= 25
    return score


def prefilter(items: list[dict], max_candidates: int, blocklist: list[str]) -> list[dict]:
    """去重 -> 丢弃噪音 -> 每个源限额 -> 按规则分排序 -> 截断。"""
    items = dedupe(items)
    blocked_words = [w.strip().lower() for w in blocklist if w and w.strip()]
    items = [
        item for item in items
        if not any(word in (item.get("title") or "").lower() for word in blocked_words)
    ]

    buckets: dict[str, list[dict]] = {}
    for item in items:
        buckets.setdefault(item.get("source", ""), []).append(item)

    picked: list[dict] = []
    for bucket in buckets.values():
        bucket.sort(key=heuristic_score, reverse=True)
        picked.extend(bucket[:PER_SOURCE_CAP])

    picked.sort(key=heuristic_score, reverse=True)
    return picked[:max_candidates]


# ---------------------------------------------------------------------------
# 让 AI 判断
# ---------------------------------------------------------------------------

JUDGE_INSTRUCTIONS = """
【栏目定义】每条内容只能归入下面 5 个栏目之一：
1. 工具雷达 —— 能直接下载、注册或安装就用的软件、网站、浏览器插件、数据集平台。
2. 方法前沿 —— 新的研究方法、模型、算法、数据库、基准测试，偏学术。
3. 技能配方 —— 可以照抄的 AI 使用方法：提示词、工作流、Agent/Skill 配置、自动化脚本。
4. 学术与合规 —— 期刊政策、投稿要求、AI 使用规范、伦理、学术出版动态。
5. 模型更新 —— 大模型或平台发布了新版本、新能力、价格或免费额度变化。

【打分标准】score 取 0-100，只衡量一件事：对一名医学生/临床研究者做科研的效率提升。
  90-100：立刻能用，且能明显省时间（比如直接解决检索/阅读/写作/统计中的痛点）
  70-89 ：值得了解，很可能用得上
  50-69 ：一般性动态，了解一下即可
  0-49  ：与科研效率基本无关（纯商业融资、玩具项目、行业八卦等）

【字段要求】
- what：用大白话说清"这是什么"，不要用行话，40 字以内。
- why：为什么值得看，具体能帮到科研的哪个环节，60 字以内。
- how：具体怎么上手，60 字以内；如果没有操作步骤就写"了解即可"。
- difficulty：只能是 开箱即用 / 需注册 / 需配置 / 需编程 之一。
- cost：只能是 免费 / 有免费额度 / 付费 之一。
- tags：1-3 个中文短标签，例如 文献检索、写作润色、统计绘图。
- keep：score >= 60 时填 true，否则 false。

严格只输出一个 JSON 数组，不要任何解释文字、不要 Markdown 代码块。
数组里每一项对应输入中的一条，id 必须和输入一致。
""".strip()


def _format_candidates(batch: list[dict], offset: int) -> str:
    lines = []
    for index, item in enumerate(batch, start=offset):
        summary = (item.get("summary") or "（无摘要）")[:600]
        lines.append(
            f"id={index}\n"
            f"标题：{item.get('title', '')}\n"
            f"来源：{item.get('source', '')}　日期：{item.get('published', '未知')}　"
            f"补充：{item.get('extra', '') or '无'}\n"
            f"摘要：{summary}\n"
        )
    return "\n".join(lines)


def _run_batches(client, cfg, items: list[dict], rotating_topic: str) -> dict[int, dict]:
    """用某一个模型把所有批次跑一遍，返回 {序号: 判断结果}。"""
    verdicts: dict[int, dict] = {}
    batch_size = cfg.AI_BATCH_SIZE
    total_batches = (len(items) + batch_size - 1) // batch_size

    for batch_index in range(total_batches):
        start = batch_index * batch_size
        batch = items[start:start + batch_size]
        prompt = (
            f"本期轮换专题是「{rotating_topic}」。如果某条内容正好切合这个专题，"
            f"请在 why 里点明这一点，并在 tags 里加上「{rotating_topic}」。\n\n"
            f"{JUDGE_INSTRUCTIONS}\n\n"
            f"下面是 {len(batch)} 条候选内容：\n\n{_format_candidates(batch, start)}"
        )
        print(f"  [AI] 正在判断第 {batch_index + 1}/{total_batches} 批（{len(batch)} 条）…")
        try:
            result = client.generate_json(
                prompt=prompt,
                system=cfg.EDITOR_PERSONA,
                temperature=0.2,
                max_retries=cfg.AI_MAX_RETRIES,
            )
        except llm_module.AuthError as exc:
            # Key 无效 / 没有权限：后面每一批都会以同样方式失败，直接放弃这个平台
            print(f"  [AI] 凭据被拒绝，放弃 {client.label}：{str(exc)[:140]}")
            break
        except Exception as exc:  # noqa: BLE001
            print(f"  [AI] 这一批失败，跳过：{type(exc).__name__}: {str(exc)[:120]}")
            continue

        if isinstance(result, dict):
            result = [result]
        for entry in result or []:
            if not isinstance(entry, dict):
                continue
            try:
                verdicts[int(entry.get("id"))] = entry
            except (TypeError, ValueError):
                continue
    return verdicts


def judge(clients: list, cfg, items: list[dict], rotating_topic: str) -> dict[int, dict]:
    """
    分批把候选内容交给 AI 打分。返回 {序号: 判断结果}。

    clients 是按优先顺序排好的模型列表。第一个跑不通（Key 失效、额度用完、
    模型名不对等）时，会自动用第二个再跑一遍。
    """
    for index, client in enumerate(clients):
        print(f"  [AI] 使用 {client.label} 评审")
        verdicts = _run_batches(client, cfg, items, rotating_topic)
        if verdicts:
            return verdicts
        if index + 1 < len(clients):
            print(f"  [AI] {client.label} 没有产出结果，改用 {clients[index + 1].label} 重试")
    return {}


def select(items: list[dict], verdicts: dict[int, dict], cfg):
    """按 AI 打分会合出最终条目，并按分数从高到低排序。"""
    kept = []
    for index, item in enumerate(items):
        verdict = verdicts.get(index)
        if not verdict:
            continue
        try:
            score = float(verdict.get("score", 0))
        except (TypeError, ValueError):
            score = 0.0
        if score < cfg.MIN_SCORE:
            continue
        merged = dict(item)
        merged["id"] = index
        merged["score"] = score
        merged["column"] = str(verdict.get("column") or item.get("pool") or "工具雷达").strip()
        merged["what"] = str(verdict.get("what") or "").strip()
        merged["why"] = str(verdict.get("why") or "").strip()
        merged["how"] = str(verdict.get("how") or "").strip()
        merged["difficulty"] = str(verdict.get("difficulty") or "").strip()
        merged["cost"] = str(verdict.get("cost") or "").strip()
        tags = verdict.get("tags") or []
        merged["tags"] = [str(t).strip() for t in tags if str(t).strip()][:3] if isinstance(tags, list) else []
        kept.append(merged)

    kept.sort(key=lambda record: record["score"], reverse=True)
    return kept[:cfg.MAX_ITEMS], len(kept)


COMPOSE_INSTRUCTIONS = """
你要为这一期周报写一段开篇导读、挑出"本周只值得动手试的一件事"，再做一份术语小抄。

输出严格的 JSON 对象，不要任何解释文字、不要 Markdown 代码块：
{
  "intro": "一句话导读，概括这周 AI 圈对科研人最有价值的信号，60 字以内",
  "highlight_id": 12,
  "highlight_reason": "为什么这一条最值得这周动手试，70 字以内",
  "glossary": [
    {"term": "术语名", "plain": "用大白话解释，40 字以内"}
  ]
}

要求：
- highlight_id 必须从下面给出的条目里选一个 id。
- glossary 选 3 到 5 个本期出现的、外行看不懂的术语（例如 MCP、SOTA、Agent、微调、基准）。
- 如果某个术语太基础，就不要选它。
""".strip()


def compose(clients: list, cfg, kept: list[dict], rotating_topic: str) -> dict:
    """生成导读、本周最值得动手的一条、以及术语小抄。失败时返回可用的兜底内容。"""
    fallback = {
        "intro": f"本周共筛出 {len(kept)} 条值得关注的 AI 动态，专题方向：{rotating_topic}。",
        "highlight_id": kept[0]["id"] if kept else None,
        "highlight_reason": "本期得分最高的一条，建议优先花 10 分钟看看。",
        "glossary": [],
    }
    if not kept:
        return fallback

    listing = "\n".join(
        f"id={item['id']}｜{item['column']}｜{item['title'][:90]}\n"
        f"    是什么：{item.get('what', '')}\n"
        f"    为什么：{item.get('why', '')}"
        for item in kept
    )
    prompt = (
        f"本期轮换专题：{rotating_topic}\n\n{COMPOSE_INSTRUCTIONS}\n\n本期入选条目：\n{listing}"
    )
    result = None
    for client in clients:
        try:
            result = client.generate_json(
                prompt=prompt,
                system=cfg.EDITOR_PERSONA,
                temperature=0.4,
                max_retries=cfg.AI_MAX_RETRIES,
            )
            break
        except Exception as exc:  # noqa: BLE001
            print(f"  [AI] {client.label} 导读生成失败：{type(exc).__name__}: {str(exc)[:100]}")
            result = None
    if result is None:
        print("  [AI] 导读生成失败，使用兜底文案")
        return fallback

    if not isinstance(result, dict):
        return fallback
    valid_ids = {item["id"] for item in kept}
    highlight = result.get("highlight_id")
    if highlight is not None:
        try:
            highlight = int(highlight)
        except (TypeError, ValueError):
            highlight = None
    if highlight not in valid_ids:
        highlight = kept[0]["id"]

    glossary = []
    for entry in result.get("glossary") or []:
        if isinstance(entry, dict) and entry.get("term") and entry.get("plain"):
            glossary.append({"term": str(entry["term"])[:20], "plain": str(entry["plain"])[:80]})

    return {
        "intro": str(result.get("intro") or fallback["intro"])[:160],
        "highlight_id": highlight,
        "highlight_reason": str(result.get("highlight_reason") or fallback["highlight_reason"])[:200],
        "glossary": glossary[:5],
    }


def fingerprint(items: list[dict]) -> str:
    """给一批条目算个指纹，用于日志排查。"""
    digest = hashlib.sha1()
    for item in items:
        digest.update((item.get("url") or item.get("title") or "").encode("utf-8", errors="ignore"))
    return digest.hexdigest()[:12]


TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"


def translate_zh(text: str, timeout: int = 15) -> str:
    """
    用免费的 Google 翻译接口把一段文字翻成中文（不需要任何 Key）。
    失败时返回空字符串，调用方自己决定怎么兜底。
    """
    text = (text or "").strip()
    if not text:
        return ""
    params = {"client": "gtx", "sl": "auto", "tl": "zh-CN", "dt": "t", "q": text[:1500]}
    url = TRANSLATE_URL + "?" + urllib.parse.urlencode(params)
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
        return "".join(part[0] for part in data[0] if part and part[0]).strip()
    except Exception:  # noqa: BLE001
        return ""


def fallback_selection(items: list[dict], limit: int = 8) -> list[dict]:
    """
    兜底方案：当所有 AI 平台都不可用时，按规则分数挑出前几条，
    **用免费翻译把它变成中文**，再配上原文链接。
    这样即使 AI 完全用不了，你收到的至少是一份能看懂的中文速览，
    而不是一堆英文标题。
    """
    picked = []
    for rank, item in enumerate(sorted(items, key=heuristic_score, reverse=True)[:limit]):
        raw_title = (item.get("title") or "").strip()
        title_zh = translate_zh(raw_title)
        summary_zh = translate_zh((item.get("summary") or "")[:500])
        merged = dict(item)
        merged["id"] = rank
        merged["score"] = 0
        merged["column"] = item.get("pool") or "工具雷达"
        merged["title"] = f"{title_zh}（{raw_title[:70]}）" if title_zh else raw_title
        merged["what"] = summary_zh[:180] if summary_zh else "（本条没有摘要，点开原文查看）"
        merged["why"] = "本次 AI 摘要服务未启用，下面给的是原文内容的中文翻译，供你快速判断值不值得细看。"
        merged["how"] = ""
        merged["difficulty"] = ""
        merged["cost"] = ""
        merged["tags"] = ["待人工判断"]
        picked.append(merged)
        print(f"  [兜底] 已翻译第 {rank + 1} 条")
    return picked


def dump_json(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
