#!/usr/bin/env python3
"""
招聘/教育平台私域付费情报 — 每日自动抓取脚本
搜索源限定：微信/微博/抖音/B站/知乎/小红书 + 各平台官网
聚焦：付费项目相关行为、结果数据、舆论反响
"""

import time
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
REPORTS_DIR = PROJECT_DIR / "reports"
DATA_DIR = PROJECT_DIR / "data"

TODAY = datetime.now().strftime("%Y-%m-%d")

# ── 平台搜索配置（每个平台 + 限定搜索源） ─────────────────
PLATFORM_QUERIES = [
    ("BOSS直聘", [
        "BOSS直聘 付费 用户 数据 2026 site:zhipin.com",
        "BOSS直聘 营收 付费企业 财报",
        "BOSS直聘 付费 争议 用户 投诉",
        "BOSS直聘 付费 知乎",
        "BOSS直聘 付费 微博",
    ]),
    ("智联招聘", [
        "智联招聘 付费 企业客户 营收",
        "智联招聘 付费 私域 社群",
        "智联招聘 付费 知乎 微博",
    ]),
    ("前程无忧", [
        "前程无忧 51job 付费 会员 价格",
        "前程无忧 AI 用户 付费",
        "前程无忧 付费 知乎 site:51job.com",
    ]),
    ("同道猎聘", [
        "猎聘 付费用户 2026 财报",
        "猎聘 付费 企业版 AI",
        "猎聘 付费 知乎 微博",
    ]),
    ("高途教育", [
        "高途 付费用户 获客 抖音 2026",
        "高途 财报 营收 利润",
        "高途 付费 知乎 小红书",
    ]),
    ("高顿教育", [
        "高顿教育 付费 用户 小红书",
        "高顿 财经培训 付费 知乎",
        "高顿 官网 课程 价格 site:goldeneducation.cn",
    ]),
    ("海马职加", [
        "海马职加 付费 内推 知乎",
        "付费求职机构 留学生 小红书 微博",
        "付费 远程实习 争议 投诉",
    ]),
    ("实习僧", [
        "实习僧 付费 会员 用户",
        "实习僧 知乎 小红书 site:shixiseng.com",
    ]),
    ("牛客网", [
        "牛客网 付费 校招 产品 知乎",
        "牛客网 付费 笔试 面试 微博",
    ]),
]

# 跨平台付费行为综合检索
CROSS_PLATFORM_QUERIES = [
    "招聘平台 付费用户 数据 2026 知乎",
    "在线教育 付费 获客 转化 抖音 小红书",
    "求职平台 会员付费 续费率 微博 知乎",
    "职业教育 知识付费 用户 行为 数据 2026",
    "招聘 APP 付费 价格 对比 知乎",
    "私域运营 付费转化 招聘 微博 小红书",
]


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
                        "date": r.get("date", ""),
                    })
            if results:
                return results
        except Exception as e:
            wait = (attempt + 1) * 4 + random.uniform(1, 3)
            print(f"  [ddgs] {query[:40]}... 重试 {attempt+1}/3: {str(e)[:80]}")
            time.sleep(wait)
    return []


def infer_date(item: dict) -> str:
    """推断信息发布日期"""
    d = item.get("date", "")
    if d:
        return d[:10]
    snippet = item.get("snippet", "")
    title = item.get("title", "")
    text = title + snippet
    import re
    for pat in [r'(\d{4}-\d{2}-\d{2})', r'(\d{4}年\d{1,2}月\d{1,2}日)']:
        m = re.search(pat, text)
        if m:
            return m.group(1)
    return TODAY


def infer_source_platform(item: dict) -> str:
    """根据 URL 推断信息来源平台"""
    url = item.get("url", "")
    if "zhihu.com" in url:
        return "知乎"
    if "weibo.com" in url:
        return "微博"
    if "douyin.com" in url:
        return "抖音"
    if "bilibili.com" in url:
        return "B站"
    if "xiaohongshu.com" in url:
        return "小红书"
    if "mp.weixin.qq.com" in url:
        return "微信公众号"
    if "zhipin.com" in url:
        return "BOSS直聘官网"
    if "51job.com" in url:
        return "前程无忧官网"
    if "zhaopin.com" in url:
        return "智联招聘官网"
    if "liepin.com" in url:
        return "猎聘官网"
    if "gaotu.cn" in url or "gaotu.com" in url:
        return "高途官网"
    if "goldeneducation.cn" in url:
        return "高顿官网"
    if "shixiseng.com" in url:
        return "实习僧官网"
    if "nowcoder.com" in url:
        return "牛客网官网"
    return "综合媒体"


def load_recent_urls(days: int = 7) -> set:
    urls = set()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    for f in sorted(REPORTS_DIR.glob("*.md")):
        if f.stem < cutoff:
            continue
        for line in f.read_text().split("\n"):
            if "http" in line:
                import re
                urls.update(re.findall(r'https?://[^\s\)\[\]]+', line))
    return urls


def load_recent_titles(days: int = 7) -> set:
    titles = set()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    for f in sorted(REPORTS_DIR.glob("*.md")):
        if f.stem < cutoff:
            continue
        for line in f.read_text().split("\n"):
            if line.strip().startswith("- **"):
                titles.add(line.strip()[:120])
    return titles


def collect_for_insight(items_by_platform: dict, cross_items: list) -> str:
    """收集所有条目文本，供 AI 生成洞察摘要"""
    texts = []
    for name, items in items_by_platform.items():
        for item in items[:4]:
            texts.append(f"[{name}] {item.get('title','')}: {item.get('snippet','')[:200]}")
    for item in cross_items[:5]:
        texts.append(f"[行业] {item.get('title','')}: {item.get('snippet','')[:200]}")
    return "\n".join(texts)


def generate_report(items_by_platform: dict, cross_items: list) -> str:
    lines = []
    lines.append(f"# 招聘/教育平台私域付费情报")
    lines.append("")
    lines.append(f"> 生成日期：{TODAY}  ")
    lines.append(f"> 检索范围：BOSS直聘、智联招聘、前程无忧、猎聘、高途、高顿、海马职加、实习僧、牛客网  ")
    lines.append(f"> 信息源限定：微信/微博/抖音/B站/知乎/小红书 + 各平台官网  ")
    lines.append("")
    lines.append("---")
    lines.append("")

    total_items = 0
    for platform_name, queries in PLATFORM_QUERIES:
        items = items_by_platform.get(platform_name, [])
        total_items += len(items)

        # 按热度自动标记
        hot_count = sum(1 for i in items if any(
            kw in (i.get("title", "") + i.get("snippet", ""))
            for kw in ["营收", "净利润", "财报", "亿元", "上市", "监管", "处罚"]
        ))
        if hot_count >= 2:
            marker = " 🔴"
        elif hot_count >= 1 or len(items) >= 4:
            marker = " 🟡"
        else:
            marker = ""

        lines.append(f"## {marker} {platform_name}")
        lines.append("")

        if items:
            for idx, item in enumerate(items[:6]):
                title = item.get("title", "无标题").replace("|", "-")
                url = item.get("url", "")
                snippet = item.get("snippet", "").replace("\n", " ")[:180]
                date = infer_date(item)
                source = infer_source_platform(item)

                lines.append(f"- **{title}**")
                if snippet:
                    lines.append(f"  {snippet}")
                lines.append(f"  📅 {date} · 来源：{source} · [查看原文]({url})")
                lines.append("")
        else:
            lines.append("> 本日未发现新的相关动态")
        lines.append("")
        lines.append("---")
        lines.append("")

    # 行业综合
    lines.append("## ⚪ 跨平台付费行为综合")
    lines.append("")
    if cross_items:
        for item in cross_items[:10]:
            title = item.get("title", "").replace("|", "-")
            url = item.get("url", "")
            snippet = item.get("snippet", "").replace("\n", " ")[:180]
            date = infer_date(item)
            source = infer_source_platform(item)
            lines.append(f"- **{title}**")
            if snippet:
                lines.append(f"  {snippet}")
            lines.append(f"  📅 {date} · 来源：{source} · [查看原文]({url})")
            lines.append("")
    lines.append("")

    # 数据摘要
    today_items = total_items + len(cross_items)
    lines.append("---")
    lines.append(f"*本日共检索到 {today_items} 条相关信息，去重后纳入报告。*")
    lines.append(f"*自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')} CST*")

    return "\n".join(lines)


def main():
    print(f"=== 招聘情报自动抓取 {TODAY} ===\n")

    recent_urls = load_recent_urls()
    recent_titles = load_recent_titles()
    print(f"[去重] 近7天历史 URL: {len(recent_urls)} 条\n")

    items_by_platform = {}
    insight_texts = []

    for platform_name, queries in PLATFORM_QUERIES:
        print(f"[搜索] {platform_name}...")
        all_items = []
        seen = set()
        for q in queries:
            results = search_ddgs(q, max_results=4)
            for r in results:
                url = r.get("url", "")
                title = r.get("title", "")
                if url in recent_urls or url in seen:
                    continue
                if title[:60] in recent_titles:
                    continue
                seen.add(url)
                all_items.append(r)
            time.sleep(2)
        items_by_platform[platform_name] = all_items
        print(f"  -> {len(all_items)} 条新结果\n")

    print("[搜索] 跨平台综合...")
    cross_items = []
    cross_seen = set()
    for q in CROSS_PLATFORM_QUERIES:
        results = search_ddgs(q, max_results=4)
        for r in results:
            url = r.get("url", "")
            if url in recent_urls or url in cross_seen:
                continue
            cross_seen.add(url)
            cross_items.append(r)
        time.sleep(2)
    print(f"  -> {len(cross_items)} 条\n")

    total = sum(len(v) for v in items_by_platform.values()) + len(cross_items)
    if total == 0:
        print("[跳过] 今日无新信息")
        return

    report = generate_report(items_by_platform, cross_items)
    report_path = REPORTS_DIR / f"{TODAY}.md"
    report_path.write_text(report)

    # 保存原始数据供 AI 洞察使用
    insight_data = collect_for_insight(items_by_platform, cross_items)
    (DATA_DIR / "insight_data.txt").write_text(insight_data)

    print(f"[报告] 已保存: {report_path} ({len(report)} 字符)")
    print(f"[数据] 洞察素材: {len(insight_data)} 字符")


if __name__ == "__main__":
    main()
