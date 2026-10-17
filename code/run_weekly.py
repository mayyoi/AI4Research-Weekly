# -*- coding: utf-8 -*-
"""
主流程（入口文件）。GitHub Actions 每周三就是执行这个文件。

顺序：
  抓取 → 去重 → 预排序 → 跳过以前推过的 → AI 打分分类 → 选出本期条目
  → 生成导读/专题/术语小抄 → 渲染 HTML → 发邮件 → 记录历史

常用参数（本地调试用）：
  --dry-run   只生成邮件文件，不真的发送
  --no-ai     跳过 AI 环节（用来检查抓取和排版是否正常）
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path

# 让下面的 import 能找到同目录的模块（直接运行 code/run_weekly.py 时也成立）
sys.path.insert(0, str(Path(__file__).resolve().parent))

import curate
import history
import llm
import render
import send_email
import sources

ROOT = Path(__file__).resolve().parent.parent

import config  # noqa: E402


def _iso_week_label(today: date) -> str:
    year, week, _ = today.isocalendar()
    return f"{year}-W{week:02d}"


def run(dry_run: bool = False, no_ai: bool = False) -> int:
    today = date.today()
    start_day = today - timedelta(days=config.LOOKBACK_DAYS)
    range_text = f"{start_day.isoformat()} ~ {today.isoformat()}"
    history_path = str(ROOT / "data" / "sent_history.json")

    print("=" * 66)
    print(f"AI × 科研效率周报　生成时间 {today.isoformat()}　范围 {range_text}")
    print("=" * 66)

    # ---------- 1. 抓取 ----------
    print("\n[1/6] 抓取信息源")
    raw_items, failures = sources.fetch_all(config.SOURCES, config.LOOKBACK_DAYS)
    print(f"      原始条目 {len(raw_items)} 条，失败的源 {len(failures)} 个")

    # ---------- 2. 去重与预排序 ----------
    print("\n[2/6] 去重与预排序")
    candidates = curate.prefilter(raw_items, config.MAX_CANDIDATES, config.BLOCKLIST)
    print(f"      进入 AI 评审的候选：{len(candidates)} 条")

    # ---------- 3. 跳过以前推过的 ----------
    print("\n[3/6] 与历史比对，跳过往期已推送内容")
    store = history.load(history_path)
    candidates, excluded = history.split_new(candidates, store)
    print(f"      排除往期 {excluded} 条，剩余 {len(candidates)} 条")

    # ---------- 4. AI 评审 ----------
    issue_no = int(store.get("issue") or 0) + 1
    rotating_topic = config.ROTATING_TOPICS[(issue_no - 1) % len(config.ROTATING_TOPICS)]
    print(f"\n[4/6] AI 评审（第 {issue_no} 期，本期专题：{rotating_topic}）")

    clients = llm.build_llms(config)
    kept: list[dict] = []
    used_fallback = False
    composition = {"intro": "", "highlight_id": None, "highlight_reason": "", "glossary": []}

    if no_ai or not candidates:
        print("      跳过 AI（--no-ai 或没有候选）")
    elif not clients:
        raise RuntimeError(
            "没有读到任何 AI 的 Key。请到仓库 Settings → Secrets and variables → Actions 里"
            "添加下面任意一个 Secret：\n"
            "  - OPENAI_API_KEY（复用你已有的 OpenAI Key）\n"
            "  - GEMINI_API_KEY（在 aistudio.google.com/apikey 免费申请）"
        )
    else:
        print(f"      可用模型：{'、'.join(client.label for client in clients)}")
        verdicts = curate.judge(clients, config, candidates, rotating_topic)
        kept, kept_total = curate.select(candidates, verdicts, config)
        print(f"      AI 判定完成：达标 {kept_total} 条，本期保留 {len(kept)} 条")
        composition = curate.compose(clients, config, kept, rotating_topic)
        if not kept:
            # AI 环节可能因为额度/网络问题整体失败。这时候不要让邮件变成空信，
            # 改成按规则排序，仍然给你一份可用的速览。
            kept = curate.fallback_selection(candidates, min(8, config.MAX_ITEMS))
            used_fallback = True
            composition = {
                "intro": "本次 AI 摘要服务没有正常返回，下面是用免费翻译整理的原文速览（附原文链接）。",
                "highlight_id": kept[0]["id"] if kept else None,
                "highlight_reason": "本期按规则评分排在最前的一条，建议优先看看。",
                "glossary": [],
            }
            print(f"      ⚠️ AI 无结果，启用兜底速览 {len(kept)} 条")

    # ---------- 5. 渲染 ----------
    print("\n[5/6] 渲染邮件")
    sections = render.build_sections(kept, config.SECTIONS)
    highlight_item = next((i for i in kept if i["id"] == composition.get("highlight_id")), None)
    source_count = len({item.get("source", "") for item in kept if item.get("source")})

    subject = f"{config.EMAIL_SUBJECT} 第 {issue_no} 期（{today.isoformat()}）"
    preheader = composition.get("intro") or f"本周 {len(kept)} 条 AI 科研动态"
    failure_note = f"，本周 {len(failures)} 个源未取到数据" if failures else ""

    context = {
        "subject": subject,
        "preheader": preheader,
        "issue_no": issue_no,
        "date_range": range_text,
        "intro": composition.get("intro") or "本周没有筛出足够好的内容，仅供参考。",
        "raw_count": len(raw_items),
        "item_count": len(kept),
        "source_count": source_count,
        "rotating_topic": rotating_topic,
        "highlight_block": render.highlight_to_html(highlight_item, composition.get("highlight_reason", "")),
        "highlight_item": highlight_item,
        "highlight_reason": composition.get("highlight_reason", ""),
        "sections_html": render.sections_to_html(sections),
        "glossary_block": render.glossary_to_html(composition.get("glossary") or []),
        "glossary": composition.get("glossary") or [],
        "footer_note": config.FOOTER_NOTE,
        "sources_note": "、".join(sorted({s["name"] for s in config.SOURCES})),
        "failure_note": failure_note,
    }
    html_body = render.build_html(str(ROOT / "templates" / "email.html"), context)
    markdown_body = render.build_markdown(context, sections)

    out_dir = ROOT / "Output"
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / f"{today.isoformat()}.html"
    md_path = out_dir / f"{today.isoformat()}.md"
    html_path.write_text(html_body, encoding="utf-8")
    md_path.write_text(markdown_body, encoding="utf-8")
    print(f"      已生成 {html_path.name}（{len(html_body)} 字符）与 {md_path.name}")

    # 基本的自检，防止发出乱码邮件
    if not html_body.lstrip().lower().startswith("<!doctype html>"):
        raise RuntimeError("HTML 开头不是 <!doctype html>，渲染可能出错，已中止发送。")
    if 'charset="utf-8"' not in html_body.lower():
        raise RuntimeError("HTML 缺少 charset=utf-8 声明，已中止发送。")

    # ---------- 6. 发送与记录 ----------
    print("\n[6/6] 发送邮件")
    should_send = bool(kept) or config.SEND_EMPTY_NOTICE
    if not should_send:
        print("      本期没有内容，且配置为不发送空邮件，跳过。")
        return 0

    send_email.send_html_email(
        subject=subject,
        html_body=html_body,
        sender=config.SENDER_EMAIL,
        receiver=config.RECEIVER_EMAIL,
        dry_run=dry_run,
    )

    if dry_run:
        print("      演练模式：不写入历史。")
    else:
        if used_fallback:
            added = 0
            print("      本次是兜底速览，不写入历史（下次 AI 正常时这些内容还能被重新推送）")
        else:
            added = history.append(store, kept, today.isoformat())
        store["issue"] = issue_no
        store["last_run"] = today.isoformat()
        history.save(history_path, store)
        print(f"      历史已更新：新增 {added} 条，期号推进到 {issue_no}")

    print("\n完成 ✅")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="生成并发送 AI × 科研效率周报")
    parser.add_argument("--dry-run", action="store_true", help="只生成邮件文件，不发送")
    parser.add_argument("--no-ai", action="store_true", help="跳过 AI 环节，仅测试抓取与排版")
    args = parser.parse_args()
    return run(dry_run=args.dry_run, no_ai=args.no_ai)


if __name__ == "__main__":
    sys.exit(main())
