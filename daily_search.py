#!/usr/bin/env python3
"""
招聘/教育平台私域付费情报 — 每日自动抓取脚本
在 GitHub Actions 中运行，不依赖 Claude。
搜索策略：ddgs 关键词搜索 + RSS 新闻源
"""

import time
import json
import hashlib
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


PROJECT_DIR = Path(__file__).parent
REPORTS_DIR = PROJECT_DIR / "reports"
DATA_DIR = PROJECT_DIR / "data"

# ── 搜索主题配置 ──────────────────────────────────
SEARCH_QUERIES = [
    ("BOSS直聘", [
        "BOSS直聘 2026 付费 营收 用户",
        "BOSS直聘 私域 运营 付费模式",
        "BOSS直聘 合作 平台 生态",
    ]),
    ("智联招聘", [
        "智联招聘 2026 付费 私域",
        "智联招聘 企业客户 营收",
    ]),
    ("前程无忧", [
        "前程无忧 51job 2026 付费 私域",
        "前程无忧 AI 招聘 用户来源",
    ]),
    ("同道猎聘", [
        "猎聘 2026 营收 付费用户 财报",
        "同道猎聘 AI 私域 招聘",
    ]),
    ("高途教育", [
        "高途教育 2026 付费 用户 获客",
        "高途 财报 营收 盈利",
    ]),
    ("高顿教育", [
        "高顿教育 2026 付费 用户 获客",
        "高顿 融资 业务 扩展",
    ]),
    ("海马职加", [
        "海马职加 付费 求职 2026",
        "留学生 付费内推 求职机构",
    ]),
    ("实习僧", [
        "实习僧 2026 付费 私域",
        "实习招聘平台 用户 付费",
    ]),
    ("牛客网", [
        "牛客网 2026 付费 校招 产品",
        "技术求职平台 付费 用户",
    ]),
]

BROAD_QUERIES = [
    "在线招聘 付费模式 私域流量 2026",
    "在线教育 付费用户 获客成本 2026",
    "求职平台 用户付费 营收 财报",
    "招聘行业 AI 私域 趋势 2026",
    "职业教育 知识付费 转化 2026",
]

RSS_FEEDS = [
    ("36氪", "https://36kr.com/feed"),
    ("虎嗅", "https://www.huxiu.com/rss/0.xml"),
    ("DoNews", "https://www.donews.com/rss"),
]

# ── 搜索模块 ─────────────────────────────────────

def search_ddgs(query: str, max_results: int = 5) -> list[dict]:
    """使用 ddgs 搜索，带重试和退避"""
    for attempt in range(3):
        try:
            from ddgs import DDGS
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", ""),
                    })
            if results:
                return results
        except Exception as e:
            wait = (attempt + 1) * 3 + random.uniform(1, 3)
            print(f"  [ddgs] {query[:30]}... 失败 (尝试 {attempt+1}/3): {e}")
            time.sleep(wait)
    return []


def fetch_rss(feed_name: str, feed_url: str, max_items: int = 10) -> list[dict]:
    """拉取 RSS 源"""
    try:
        import feedparser
        feed = feedparser.parse(feed_url)
        items = []
        for entry in feed.entries[:max_items]:
            items.append({
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),
                "snippet": entry.get("summary", ""),
                "source": feed_name,
                "published": entry.get("published", ""),
            })
        print(f"  [RSS] {feed_name}: {len(items)} 条")
        return items
    except Exception as e:
        print(f"  [RSS] {feed_name}: 失败 - {e}")
        return []


# ── 去重模块 ─────────────────────────────────────

def load_recent_urls(days: int = 7) -> set:
    """加载近 N 天报告中出现过的 URL"""
    urls = set()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    for f in sorted(REPORTS_DIR.glob("*.md")):
        if f.stem < cutoff:
            continue
        for line in f.read_text().split("\n"):
            if "http" in line:
                # 提取 URL
                import re
                found = re.findall(r'https?://[^\s\)\[\]]+', line)
                urls.update(found)
    return urls


def load_recent_titles(days: int = 7) -> set:
    """加载近 N 天报告中出现过的新闻标题关键词"""
    titles = set()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    for f in sorted(REPORTS_DIR.glob("*.md")):
        if f.stem < cutoff:
            continue
        for line in f.read_text().split("\n"):
            if line.startswith("- **") or line.startswith("- ["):
                titles.add(line.strip()[:120])
    return titles


# ── 报告生成 ─────────────────────────────────────

def generate_report(today: str, platform_results: dict, broad_results: list, rss_items: list) -> str:
    """将搜索结果编译为 markdown 报告"""
    lines = []
    lines.append(f"# 招聘/教育平台私域付费动态情报")
    lines.append("")
    lines.append(f"> 生成时间：{today}  {datetime.now().strftime('%H:%M')} CST  ")
    lines.append(f"> 覆盖平台：BOSS直聘、智联招聘、前程无忧、猎聘、高途、高顿、海马职加、实习僧、牛客网  ")
    lines.append(f"> 数据来源：公开搜索 + RSS 聚合，自动生成  ")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 平台专项
    for platform_name, queries in SEARCH_QUERIES:
        items = platform_results.get(platform_name, [])
        lines.append(f"## {platform_name}")
        lines.append("")
        if items:
            for item in items[:6]:
                title = item.get("title", "无标题")
                url = item.get("url", "")
                snippet = item.get("snippet", "")
                if snippet:
                    lines.append(f"- **{title}** — {snippet[:150]} [来源]({url})")
                else:
                    lines.append(f"- **{title}** [来源]({url})")
        else:
            lines.append("> 本日未发现新的相关动态")
        lines.append("")
        lines.append("---")
        lines.append("")

    # 行业综合
    lines.append("## ⚪ 行业综合动态")
    lines.append("")
    if broad_results:
        for item in broad_results[:10]:
            title = item.get("title", "")
            url = item.get("url", "")
            snippet = item.get("snippet", "")
            lines.append(f"- **{title}** — {snippet[:150]} [来源]({url})")
    lines.append("")
    lines.append("---")
    lines.append("")

    # RSS 要闻
    if rss_items:
        lines.append("## ⚪ RSS 新闻聚合")
        lines.append("")
        for item in rss_items[:15]:
            source = item.get("source", "")
            title = item.get("title", "")
            url = item.get("url", "")
            snippet = item.get("snippet", "")[:120]
            lines.append(f"- [{source}] **{title}** — {snippet} [原文]({url})")
        lines.append("")

    return "\n".join(lines)


# ── 主流程 ───────────────────────────────────────

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"=== 招聘情报自动抓取 {today} ===\n")

    # 加载历史去重
    recent_urls = load_recent_urls()
    recent_titles = load_recent_titles()
    print(f"[去重] 近7天历史 URL: {len(recent_urls)} 条\n")

    # 平台专项搜索
    platform_results = {}
    for platform_name, queries in SEARCH_QUERIES:
        print(f"[搜索] {platform_name}...")
        all_items = []
        seen = set()
        for q in queries:
            results = search_ddgs(q, max_results=5)
            for r in results:
                url = r.get("url", "")
                title = r.get("title", "")
                # 去重
                if url in recent_urls or url in seen:
                    continue
                if title[:80] in recent_titles:
                    continue
                seen.add(url)
                all_items.append(r)
            time.sleep(2)  # 请求间隔
        platform_results[platform_name] = all_items
        print(f"  -> {len(all_items)} 条新结果\n")

    # 行业综合搜索
    print("[搜索] 行业综合...")
    broad_results = []
    broad_seen = set()
    for q in BROAD_QUERIES:
        results = search_ddgs(q, max_results=4)
        for r in results:
            url = r.get("url", "")
            if url in recent_urls or url in broad_seen:
                continue
            broad_seen.add(url)
            broad_results.append(r)
        time.sleep(2)
    print(f"  -> {len(broad_results)} 条新结果\n")

    # RSS
    print("[RSS] 拉取新闻源...")
    rss_items = []
    for name, url in RSS_FEEDS:
        items = fetch_rss(name, url)
        for item in items:
            item_url = item.get("url", "")
            if item_url not in recent_urls:
                rss_items.append(item)
        time.sleep(1)
    print(f"  -> {len(rss_items)} 条 RSS 新闻\n")

    # 生成报告
    total = sum(len(v) for v in platform_results.values()) + len(broad_results)
    if total == 0 and not rss_items:
        print("[跳过] 今日无任何新信息，不生成报告")
        return

    report = generate_report(today, platform_results, broad_results, rss_items)
    report_path = REPORTS_DIR / f"{today}.md"
    report_path.write_text(report)
    print(f"[报告] 已保存: {report_path} ({len(report)} 字符)")


if __name__ == "__main__":
    main()
