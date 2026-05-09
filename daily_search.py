#!/usr/bin/env python3
"""
大学生求职竞品付费情报 — 每日自动抓取
目标用户：大学生/应届生
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

# ── 垃圾域名和关键词黑名单 ──────────────────────
JUNK_DOMAINS = {
    "51chigua", "chigua", "xxskkr", "yudou789", "fhkoyytp",
    "eibuipa", "lhpwxsrgq", "qweweqwe", "tmduldg", "kgetgnop",
    "cmkktxig", "plusbye", "qxqgajte",
    "6a4mpy",  # 博彩
    "leapvpn", "lemonki",  # VPN/无关
    "1688.com", "alibaba",  # 电商
    "sj.qq.com", "apps.apple.com", "appsupports.co",  # 应用商店
    "gemini.google.com", "kimi.com",  # AI 工具
    "youtube.com", "dzen.ru", "kitau.ru",  # 外网
    "mint-wireless", "usccstrategy",  # 无关
    "wearesellers",  # 亚马逊卖家
    "bbs.wforum",  # 论坛
    "startup.aliyun",  # 云服务
    "zmtzn.com",  # 自媒体垃圾站
    "st-guanjia.com",  # 无关
    "dh.ally.ren",  # 导航站
    "qizansea.com",  # SEO
    "bbc.com",  # 外媒
}

JUNK_KEYWORDS = [
    "吃瓜", "黑料", "福利姬", "探花", "约炮", "性爱", "淫秽",
    "OnlyFans", "onlyfans", "下海", "揉奶", "抠逼", "口活",
    "嫖", "妓", "做爱", "巨屌", "肉棒", "嫩穴", "自慰",
    "VPN", "翻墙", "博彩", "赌博", "彩票", "赌场",
    "裸", "露点", "偷拍", "泄密",
    "Google LLC", "© 2026 Google",
    "Работа в Китае", "русских", "Китае",
    "Mint Mobile", "加密货币",
    "阿里1688首页", "阿里巴巴（1688.com）",
    "Kimi AI", "Gemini",
    "LeapVPN", "博彩网站",
    "亚马逊卖家", "Mint Mobile",
    "отзывы", "Дзен",
    "加密货币", "比特币",
]

# 允许的域名模式（白名单优先）
TRUSTED_DOMAINS = [
    "zhipin.com", "51job.com", "zhaopin.com", "liepin.com",
    "shixiseng.com", "nowcoder.com",
    "zhihu.com", "weibo.com", "bilibili.com", "xiaohongshu.com",
    "douyin.com", "mp.weixin.qq.com",
    "36kr.com", "huxiu.com", "donews.com",
    "jiemian.com", "jiemodui.com", "tmtpost.com",
    "eastmoney.com", "sina.com.cn", "163.com", "sohu.com",
    "thepaper.cn", "qq.com", "ifeng.com",
    "lanjing.com", "stockstar.com", "10jqka.com", "stcn.com",
    "ithome.com", "gitcode.com", "iheima.com", "cyzone.cn",
    "ketangjie.com", "juejin.cn", "cnblogs.com",
    "moonfox.cn", "nacshr.org", "hrtechchina.com",
    "futunn.com", "itiger.com", "zhitongcaijing.com",
    "moomoo.com", "investing.com",
    "career.muc.edu.cn", "news.guilinlife.com",
]

# ── 搜索配置（增加公众号和小红书博主方向） ──────────
PLATFORM_QUERIES = [
    ("BOSS直聘", [
        "BOSS直聘 大学生 付费 求职 2026",
        "BOSS直聘 应届生 付费 会员 知乎",
        "BOSS直聘 付费 争议 学生 投诉 site:zhihu.com",
        "BOSS直聘 校招 付费 公众号 site:mp.weixin.qq.com",
    ]),
    ("智联招聘", [
        "智联招聘 大学生 付费 会员",
        "智联招聘 应届生 求职 付费 知乎",
        "智联招聘 校招 付费 小红书",
    ]),
    ("前程无忧", [
        "前程无忧 51job 大学生 付费 会员",
        "前程无忧 应届生 求职 付费 知乎",
        "前程无忧 校招 付费 site:mp.weixin.qq.com",
    ]),
    ("同道猎聘", [
        "猎聘 大学生 应届生 付费 知乎",
        "猎聘 校招 付费 会员 小红书",
        "猎聘 付费 实习 公众号 site:mp.weixin.qq.com",
    ]),
    ("海马职加", [
        "海马职加 付费 内推 留学生 知乎",
        "付费求职 大学生 应届生 小红书",
        "付费内推 实习 避坑 公众号 site:mp.weixin.qq.com",
    ]),
    ("实习僧", [
        "实习僧 大学生 付费 会员 知乎",
        "实习僧 付费 实习 内推 小红书",
        "实习僧 应届生 付费 公众号 site:mp.weixin.qq.com",
    ]),
    ("牛客网", [
        "牛客网 大学生 付费 笔试 面试 知乎",
        "牛客网 校招 付费 会员 小红书",
        "牛客网 应届生 付费 公众号 site:mp.weixin.qq.com",
    ]),
]

CROSS_PLATFORM_QUERIES = [
    "大学生 求职 付费内推 避坑 知乎 2026",
    "应届生 招聘平台 付费 对比 小红书",
    "大学生 求职 付费服务 投诉 公众号 site:mp.weixin.qq.com",
    "校招 付费内推 骗局 知乎 微博",
    "应届生 付费简历优化 面试辅导 小红书 2026",
    "大学生 求职 APP 会员 付费 值不值 知乎",
]


def is_junk(item: dict) -> bool:
    """内容质量筛查：过滤垃圾域名、敏感关键词、无关职位帖"""
    url = item.get("url", "")
    title = item.get("title", "")
    snippet = item.get("snippet", "")
    text = f"{title} {snippet}".lower()

    # 域名黑名单
    for domain in JUNK_DOMAINS:
        if domain in url:
            return True

    # 关键词黑名单
    for kw in JUNK_KEYWORDS:
        if kw.lower() in text:
            return True

    # 过滤单个职位帖子（来自招聘平台官网的单个岗位）
    job_post_patterns = [
        r'「.+招聘信息」-BOSS直聘',
        r'「.+招聘信息」-智联',
        r'招聘信息页介绍',
        r'相关热门职位',
    ]
    for pat in job_post_patterns:
        if re.search(pat, title):
            return True

    # 过滤简历模板/H5模板/营销推广页
    junk_title_patterns = [
        r'H5模板', r'免费制作', r'易企秀', r'模板',
        r'公众号迁移', r'成功后再付款',
        r'发发笔记月挣', r'不做图不发货',
        r'app-官方正版软件', r'应用宝官网',
        r'Apps Supports', r'mobile apps developer',
        r'2026届.*校园招聘',  # 校招公告本身不是付费情报
    ]
    for pat in junk_title_patterns:
        if re.search(pat, title):
            return True

    # 必须含中文（过滤纯外文结果）
    chinese_chars = len(re.findall(r'[一-鿿]', title + snippet))
    if chinese_chars < 8:
        return True

    # URL 必须有意义
    if not url or len(url) < 15:
        return True

    return False


def is_relevant(item: dict) -> bool:
    """检查内容是否与大学生求职付费主题相关"""
    title = item.get("title", "")
    snippet = item.get("snippet", "")
    text = f"{title} {snippet}"

    must_have = ["付费", "会员", "VIP", "订阅", "套餐", "收费", "内推", "价格", "投诉", "争议"]
    context = ["大学生", "应届生", "求职", "招聘", "校招", "实习", "简历", "面试",
               "秋招", "春招", "学生", "毕业生", "校园", "留学生"]

    has_paid = any(kw in text for kw in must_have)
    has_context = any(kw in text for kw in context)
    return has_paid and has_context


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
            wait = (attempt + 1) * 4
            print(f"  [ddgs] {query[:40]}... retry {attempt+1}/3: {str(e)[:60]}")
            time.sleep(wait)
    return []


def extract_date(item: dict) -> str:
    d = item.get("date", "")
    if d and len(d) >= 10:
        return d[:10]
    text = item.get("title", "") + item.get("snippet", "")
    m = re.search(r'(\d{4}-\d{2}-\d{2})', text)
    if m:
        return m.group(1)
    m = re.search(r'(\d{4}年\d{1,2}月\d{1,2}日)', text)
    if m:
        return m.group(1)
    return ""


def classify_source(url: str) -> str:
    """识别来源平台类型"""
    mapping = [
        ("mp.weixin.qq.com", "微信公众号"),
        ("zhihu.com", "知乎"),
        ("weibo.com", "微博"),
        ("xiaohongshu.com", "小红书"),
        ("douyin.com", "抖音"),
        ("bilibili.com", "B站"),
        ("zhipin.com", "BOSS直聘官网"),
        ("51job.com", "前程无忧官网"),
        ("zhaopin.com", "智联招聘官网"),
        ("liepin.com", "猎聘官网"),
        ("shixiseng.com", "实习僧官网"),
        ("nowcoder.com", "牛客网官网"),
        ("36kr.com", "36氪"),
        ("huxiu.com", "虎嗅"),
        ("jiemian.com", "界面新闻"),
        ("jiemodui.com", "芥末堆"),
        ("tmtpost.com", "钛媒体"),
        ("eastmoney.com", "东方财富"),
        ("thepaper.cn", "澎湃新闻"),
        ("ithome.com", "IT之家"),
        ("iheima.com", "i黑马"),
        ("lanjing.com", "蓝鲸财经"),
    ]
    for key, label in mapping:
        if key in url:
            return label
    return "综合媒体"


def load_recent_urls(days: int = 7) -> set:
    urls = set()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    for f in sorted(REPORTS_DIR.glob("*.md")):
        if f.stem < cutoff:
            continue
        for line in f.read_text().split("\n"):
            if "http" in line:
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


def generate_report(items_by_platform: dict, cross_items: list) -> str:
    lines = [
        "# 大学生求职竞品付费情报",
        "",
        f"> 生成日期：{TODAY}  ",
        "> 目标用户：大学生/应届生  ",
        "> 检索范围：BOSS直聘、智联招聘、前程无忧、猎聘、海马职加、实习僧、牛客网  ",
        "> 信息源：微信/微博/抖音/B站/知乎/小红书 + 公众号/各平台官网  ",
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
        elif hot_count >= 1 or len(items) >= 4:
            marker = " 🟡"
        else:
            marker = ""

        lines.append(f"## {marker} {platform_name}")
        lines.append("")

        if items:
            for item in items[:6]:
                title = item.get("title", "").replace("|", "-").strip()
                url = item.get("url", "")
                snippet = item.get("snippet", "").replace("\n", " ")[:200]
                date = extract_date(item) or TODAY
                source = classify_source(url)

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

    lines.append("## ⚪ 跨平台付费行为综合")
    lines.append("")
    if cross_items:
        for item in cross_items[:10]:
            title = item.get("title", "").replace("|", "-").strip()
            url = item.get("url", "")
            snippet = item.get("snippet", "").replace("\n", " ")[:200]
            date = extract_date(item) or TODAY
            source = classify_source(url)
            lines.append(f"- **{title}**")
            if snippet:
                lines.append(f"  {snippet}")
            lines.append(f"  📅 {date} · 来源：{source} · [查看原文]({url})")
            lines.append("")
    else:
        lines.append("> 本日未发现新的跨平台相关动态")
    lines.append("")

    day_total = total_items + len(cross_items)
    lines.append("---")
    lines.append(f"*本日共检索到 {day_total} 条相关信息，已通过内容筛查和去重后纳入报告。*")
    lines.append(f"*自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')} CST*")

    return "\n".join(lines)


def main():
    print(f"=== 招聘情报自动抓取 {TODAY} ===\n")

    recent_urls = load_recent_urls()
    recent_titles = load_recent_titles()
    print(f"[去重] 近7天历史 URL: {len(recent_urls)} 条\n")

    items_by_platform = {}
    total_kept = 0
    total_junk = 0

    for platform_name, queries in PLATFORM_QUERIES:
        print(f"[搜索] {platform_name}...")
        all_items = []
        seen = set()
        for q in queries:
            results = search_ddgs(q, max_results=5)
            for r in results:
                url = r.get("url", "")

                if url in recent_urls or url in seen:
                    continue
                if r.get("title", "")[:60] in recent_titles:
                    continue

                # 内容筛查
                if is_junk(r):
                    total_junk += 1
                    continue
                if not is_relevant(r):
                    total_junk += 1
                    continue

                seen.add(url)
                all_items.append(r)
            time.sleep(2)
        items_by_platform[platform_name] = all_items
        total_kept += len(all_items)
        print(f"  -> {len(all_items)} 条 (过滤垃圾: {total_junk} 累计)\n")

    print("[搜索] 跨平台综合...")
    cross_items = []
    cross_seen = set()
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
            cross_seen.add(url)
            cross_items.append(r)
        time.sleep(2)
    total_kept += len(cross_items)
    print(f"  -> {len(cross_items)} 条\n")

    print(f"[统计] 保留: {total_kept}, 过滤垃圾: {total_junk}")

    if total_kept == 0:
        print("[跳过] 今日无有效新信息")
        return

    report = generate_report(items_by_platform, cross_items)
    report_path = REPORTS_DIR / f"{TODAY}.md"
    report_path.write_text(report)

    # 保存原始数据供 AI 洞察
    insight_lines = []
    for name, items in items_by_platform.items():
        for item in items[:4]:
            insight_lines.append(f"[{name}] {item.get('title','')}: {item.get('snippet','')[:200]}")
    for item in cross_items[:5]:
        insight_lines.append(f"[行业] {item.get('title','')}: {item.get('snippet','')[:200]}")
    (DATA_DIR / "insight_data.txt").write_text("\n".join(insight_lines))

    print(f"[报告] 已保存: {report_path} ({len(report)} 字符)")


if __name__ == "__main__":
    main()
