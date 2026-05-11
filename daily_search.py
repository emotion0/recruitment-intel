#!/usr/bin/env python3
"""
大学生求职竞品付费情报 — 每日自动抓取
目标用户：大学生/应届生 | 时间范围：近3天发布
搜索源：微信/微博/抖音/B站/知乎/小红书 + 各平台官网 + 公众号
聚焦：求职相关付费产品、用户行为、舆论反响
"""

import time
import re
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
REPORTS_DIR = PROJECT_DIR / "reports"
DATA_DIR = PROJECT_DIR / "data"
TODAY = datetime.now().strftime("%Y-%m-%d")
NOW = datetime.now()
MAX_AGE_DAYS = 3  # 只保留近3天发布的内容
CUTOFF_DATE = NOW - timedelta(days=MAX_AGE_DAYS)

# ── 垃圾域名和关键词黑名单 ──────────────────────
JUNK_DOMAINS = {
    "51chigua", "chigua", "xxskkr", "yudou789", "fhkoyytp",
    "eibuipa", "lhpwxsrgq", "qweweqwe", "tmduldg", "kgetgnop",
    "cmkktxig", "plusbye", "qxqgajte",
    "6a4mpy", "leapvpn", "lemonki", "1688.com", "alibaba",
    "sj.qq.com", "apps.apple.com", "appsupports.co",
    "gemini.google.com", "kimi.com",
    "youtube.com", "dzen.ru", "kitau.ru",
    "mint-wireless", "usccstrategy", "wearesellers",
    "bbs.wforum", "startup.aliyun", "zmtzn.com",
    "st-guanjia.com", "dh.ally.ren", "qizansea.com", "bbc.com",
}

JUNK_KEYWORDS = [
    "吃瓜", "黑料", "福利姬", "探花", "约炮", "性爱", "淫秽",
    "OnlyFans", "onlyfans", "下海", "揉奶", "抠逼", "口活",
    "嫖", "妓", "做爱", "巨屌", "肉棒", "嫩穴", "自慰",
    "VPN", "翻墙", "博彩", "赌博", "彩票", "赌场",
    "裸", "露点", "偷拍", "泄密",
    "Google LLC", "© 2026 Google",
    "Работа в Китае", "русских", "Китае",
    "Mint Mobile", "加密货币", "比特币",
    "阿里1688首页", "阿里巴巴（1688.com）",
    "Kimi AI", "Gemini", "LeapVPN", "博彩网站",
    "亚马逊卖家", "отзывы", "Дзен",
]

JUNK_TITLE_PATTERNS = [
    r'「.+招聘信息」-BOSS直聘',
    r'「.+招聘信息」-智联',
    r'招聘信息页介绍', r'相关热门职位',
    r'H5模板', r'免费制作', r'易企秀', r'模板',
    r'公众号迁移', r'成功后再付款',
    r'发发笔记月挣', r'不做图不发货',
    r'app-官方正版软件', r'应用宝官网',
    r'Apps Supports', r'mobile apps developer',
    r'2026届.*校园招聘',
]

# ── 搜索配置 ──────────────────────────────────
PLATFORM_QUERIES = [
    ("BOSS直聘", [
        "BOSS直聘 大学生 付费 2026",
        "BOSS直聘 应届生 付费 会员 site:zhihu.com",
        "BOSS直聘 付费 争议 学生 site:zhihu.com",
    ]),
    ("智联招聘", [
        "智联招聘 大学生 付费 会员 2026",
        "智联招聘 应届生 求职 付费 site:zhihu.com",
    ]),
    ("前程无忧", [
        "前程无忧 51job 大学生 付费 2026",
        "前程无忧 应届生 求职 付费 site:zhihu.com",
    ]),
    ("同道猎聘", [
        "猎聘 大学生 应届生 付费 site:zhihu.com",
        "猎聘 校招 付费 会员 2026",
    ]),
    ("海马职加", [
        "海马职加 付费 内推 留学生 site:zhihu.com",
        "付费求职 大学生 应届生 2026",
    ]),
    ("实习僧", [
        "实习僧 大学生 付费 会员 site:zhihu.com",
        "实习僧 付费 实习 2026",
    ]),
    ("牛客网", [
        "牛客网 大学生 付费 笔试 2026",
        "牛客网 校招 付费 会员 site:zhihu.com",
    ]),
]

CROSS_PLATFORM_QUERIES = [
    "大学生 求职 付费内推 2026 site:zhihu.com",
    "应届生 招聘平台 付费 对比 2026",
    "大学生 求职 付费服务 2026 site:mp.weixin.qq.com",
    "校招 付费内推 2026 site:zhihu.com",
    "应届生 付费 简历 面试 2026 site:zhihu.com",
]


def is_junk(item: dict) -> bool:
    url = item.get("url", "")
    title = item.get("title", "")
    snippet = item.get("snippet", "")
    text = f"{title} {snippet}".lower()

    for domain in JUNK_DOMAINS:
        if domain in url:
            return True
    for kw in JUNK_KEYWORDS:
        if kw.lower() in text:
            return True
    for pat in JUNK_TITLE_PATTERNS:
        if re.search(pat, title):
            return True

    if len(re.findall(r'[一-鿿]', title + snippet)) < 10:
        return True
    if not url or len(url) < 15:
        return True
    return False


def is_relevant(item: dict) -> bool:
    title = item.get("title", "")
    snippet = item.get("snippet", "")
    text = f"{title} {snippet}"
    must_have = ["付费", "会员", "VIP", "订阅", "套餐", "收费", "内推", "价格", "投诉", "争议"]
    context = ["大学生", "应届生", "求职", "招聘", "校招", "实习", "简历", "面试",
               "秋招", "春招", "学生", "毕业生", "校园", "留学生"]
    return any(kw in text for kw in must_have) and any(kw in text for kw in context)


def parse_date(text: str) -> datetime | None:
    """从文本中提取日期，返回 datetime 或 None"""
    patterns = [
        (r'(\d{4})-(\d{1,2})-(\d{1,2})', '%Y-%m-%d'),
        (r'(\d{4})年(\d{1,2})月(\d{1,2})日', '%Y-%m-%d'),
        (r'(\d{1,2})月(\d{1,2})日', '%m-%d'),
    ]
    for pat, fmt in patterns:
        m = re.search(pat, text)
        if m:
            try:
                groups = m.groups()
                if len(groups) == 2:
                    # 月日格式，补充当前年份
                    dt = datetime.strptime(f"{NOW.year}-{groups[0]}-{groups[1]}", '%Y-%m-%d')
                    if dt > NOW:
                        dt = dt.replace(year=NOW.year - 1)
                    return dt
                else:
                    return datetime.strptime(f"{groups[0]}-{groups[1]}-{groups[2]}", '%Y-%m-%d')
            except ValueError:
                continue
    return None


def is_recent(item: dict) -> bool:
    """检查信息是否在近 MAX_AGE_DAYS 天内发布。
    无法解析日期的直接丢弃（宁可漏报，不报旧闻）。"""
    # 先从 ddgs 自带的 date 字段
    d = item.get("date", "")
    if d:
        try:
            dt = datetime.fromisoformat(d.replace("Z", "+00:00").replace("+00:00", ""))
            if dt.tzinfo:
                dt = dt.replace(tzinfo=None)
            return dt >= CUTOFF_DATE
        except (ValueError, TypeError):
            pass

    # 从标题和摘要中解析
    text = item.get("title", "") + " " + item.get("snippet", "")
    dt = parse_date(text)
    if dt:
        return dt >= CUTOFF_DATE

    # 无法解析日期 → 丢弃
    return False


def extract_date_str(item: dict) -> str:
    """提取日期字符串用于显示"""
    d = item.get("date", "")
    if d and len(d) >= 10:
        return d[:10]
    text = item.get("title", "") + " " + item.get("snippet", "")
    dt = parse_date(text)
    return dt.strftime("%Y-%m-%d") if dt else ""


def classify_source(url: str) -> str:
    mapping = [
        ("mp.weixin.qq.com", "微信公众号"), ("zhihu.com", "知乎"),
        ("weibo.com", "微博"), ("xiaohongshu.com", "小红书"),
        ("douyin.com", "抖音"), ("bilibili.com", "B站"),
        ("zhipin.com", "BOSS直聘官网"), ("51job.com", "前程无忧官网"),
        ("zhaopin.com", "智联招聘官网"), ("liepin.com", "猎聘官网"),
        ("shixiseng.com", "实习僧官网"), ("nowcoder.com", "牛客网官网"),
        ("36kr.com", "36氪"), ("huxiu.com", "虎嗅"),
        ("jiemian.com", "界面新闻"), ("jiemodui.com", "芥末堆"),
        ("tmtpost.com", "钛媒体"), ("eastmoney.com", "东方财富"),
        ("thepaper.cn", "澎湃新闻"), ("ithome.com", "IT之家"),
        ("iheima.com", "i黑马"), ("lanjing.com", "蓝鲸财经"),
    ]
    for key, label in mapping:
        if key in url:
            return label
    return "综合媒体"


def search_ddgs(query: str, max_results: int = 5) -> list[dict]:
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
            time.sleep((attempt + 1) * 4)
    return []


def load_recent_urls(days: int = 7) -> set:
    urls = set()
    cutoff = (NOW - timedelta(days=days)).strftime("%Y-%m-%d")
    for f in sorted(REPORTS_DIR.glob("*.md")):
        if f.stem < cutoff:
            continue
        for line in f.read_text().split("\n"):
            if "http" in line:
                urls.update(re.findall(r'https?://[^\s\)\[\]]+', line))
    return urls


def load_recent_titles(days: int = 7) -> set:
    titles = set()
    cutoff = (NOW - timedelta(days=days)).strftime("%Y-%m-%d")
    for f in sorted(REPORTS_DIR.glob("*.md")):
        if f.stem < cutoff:
            continue
        for line in f.read_text().split("\n"):
            if line.strip().startswith("- **"):
                titles.add(line.strip()[:120])
    return titles


def generate_report(items_by_platform: dict, cross_items: list,
                    aged_out_platforms: set, aged_out_cross: int) -> str:
    lines = [
        "# 大学生求职竞品付费情报",
        "",
        f"> 生成日期：{TODAY}  {NOW.strftime('%H:%M')} CST",
        f"> 时间范围：仅收录近 {MAX_AGE_DAYS} 天内发布的信息",
        "> 目标用户：大学生/应届生",
        "> 检索范围：BOSS直聘、智联招聘、前程无忧、猎聘、海马职加、实习僧、牛客网",
        "> 信息源：微信/微博/抖音/B站/知乎/小红书 + 公众号/各平台官网",
        "",
        "---",
        "",
    ]

    total_items = 0
    for platform_name, _ in PLATFORM_QUERIES:
        items = items_by_platform.get(platform_name, [])
        total_items += len(items)

        hot_count = sum(1 for i in items if any(
            kw in (i.get("title", "") + i.get("snippet", ""))
            for kw in ["营收", "净利润", "财报", "亿元", "上市", "监管", "处罚"]
        ))
        if hot_count >= 2:
            marker = " 🔴"
        elif hot_count >= 1 or len(items) >= 3:
            marker = " 🟡"
        else:
            marker = ""

        lines.append(f"## {marker} {platform_name}")
        lines.append("")

        if items:
            for item in items[:5]:
                title = item.get("title", "").replace("|", "-").strip()
                url = item.get("url", "")
                snippet = item.get("snippet", "").replace("\n", " ")[:200]
                date = extract_date_str(item) or TODAY
                source = classify_source(url)
                lines.append(f"- **{title}**")
                if snippet:
                    lines.append(f"  {snippet}")
                lines.append(f"  📅 {date} · 来源：{source} · [查看原文]({url})")
                lines.append("")
        elif platform_name in aged_out_platforms:
            lines.append(f"> 近{MAX_AGE_DAYS}日内无相关付费动态")
        else:
            lines.append("> 未检索到相关信息")
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("## ⚪ 跨平台付费行为综合")
    lines.append("")
    if cross_items:
        for item in cross_items[:8]:
            title = item.get("title", "").replace("|", "-").strip()
            url = item.get("url", "")
            snippet = item.get("snippet", "").replace("\n", " ")[:200]
            date = extract_date_str(item) or TODAY
            source = classify_source(url)
            lines.append(f"- **{title}**")
            if snippet:
                lines.append(f"  {snippet}")
            lines.append(f"  📅 {date} · 来源：{source} · [查看原文]({url})")
            lines.append("")
    elif aged_out_cross > 0:
        lines.append(f"> 近{MAX_AGE_DAYS}日内无相关跨平台动态")
    else:
        lines.append("> 未检索到相关信息")
    lines.append("")

    day_total = total_items + len(cross_items)
    lines.append("---")
    lines.append(f"*本日共检索到 {day_total} 条近{MAX_AGE_DAYS}天内发布的有效信息。*")
    lines.append(f"*信息均来自公开搜索结果原文，未做任何加工篡改。*")
    lines.append(f"*自动生成于 {NOW.strftime('%Y-%m-%d %H:%M')} CST*")

    return "\n".join(lines)


def main():
    print(f"=== 大学生求职竞品付费情报 {TODAY} ===\n")
    print(f"[时效] 仅保留 {CUTOFF_DATE.strftime('%Y-%m-%d')} 之后发布的内容\n")

    recent_urls = load_recent_urls()
    recent_titles = load_recent_titles()
    print(f"[去重] 近7天历史 URL: {len(recent_urls)} 条\n")

    items_by_platform = {}
    aged_out_platforms = set()
    total_kept = 0
    total_junk = 0
    total_aged = 0

    for platform_name, queries in PLATFORM_QUERIES:
        print(f"[搜索] {platform_name}...")
        all_items = []
        seen = set()
        aged_count = 0

        for q in queries:
            results = search_ddgs(q, max_results=5)
            for r in results:
                url = r.get("url", "")
                if url in recent_urls or url in seen:
                    continue
                if r.get("title", "")[:60] in recent_titles:
                    continue
                if is_junk(r):
                    total_junk += 1
                    continue
                if not is_relevant(r):
                    total_junk += 1
                    continue

                # 时效过滤：近3天
                if not is_recent(r):
                    aged_count += 1
                    total_aged += 1
                    continue

                seen.add(url)
                all_items.append(r)
            time.sleep(2)

        items_by_platform[platform_name] = all_items
        total_kept += len(all_items)
        if aged_count > 0 and len(all_items) == 0:
            aged_out_platforms.add(platform_name)
        print(f"  -> {len(all_items)} 条有效 (过期: {aged_count}, 垃圾累计: {total_junk})\n")

    print("[搜索] 跨平台综合...")
    cross_items = []
    cross_seen = set()
    cross_aged = 0
    for q in CROSS_PLATFORM_QUERIES:
        results = search_ddgs(q, max_results=5)
        for r in results:
            url = r.get("url", "")
            if url in recent_urls or url in cross_seen:
                continue
            if is_junk(r):
                total_junk += 1
                continue
            if not is_relevant(r):
                total_junk += 1
                continue
            if not is_recent(r):
                cross_aged += 1
                total_aged += 1
                continue
            cross_seen.add(url)
            cross_items.append(r)
        time.sleep(2)
    total_kept += len(cross_items)
    print(f"  -> {len(cross_items)} 条有效 (过期: {cross_aged})\n")

    print(f"[统计] 有效: {total_kept} | 过期: {total_aged} | 垃圾: {total_junk}")

    report = generate_report(items_by_platform, cross_items, aged_out_platforms, cross_aged)
    report_path = REPORTS_DIR / f"{TODAY}.md"
    report_path.write_text(report)

    insight_lines = []
    for name, items in items_by_platform.items():
        for item in items[:3]:
            insight_lines.append(f"[{name}] {item.get('title','')}")
    for item in cross_items[:5]:
        insight_lines.append(f"[行业] {item.get('title','')}")
    (DATA_DIR / "insight_data.txt").write_text("\n".join(insight_lines))

    print(f"[报告] 已保存: {report_path} ({len(report)} 字符)")


if __name__ == "__main__":
    main()
