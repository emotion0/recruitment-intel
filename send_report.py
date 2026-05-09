#!/usr/bin/env python3
"""
发送招聘情报邮件，含：
- AI 每日洞察摘要（邮件顶部）
- 热度颜色标注（🔴红=财报/监管 🟡橙=战略/趋势 🔵蓝=常规）
- 细粒度去重（逐段对比近7天报告）
"""

import smtplib
import hashlib
import json
import sys
import os
import re
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
REPORTS_DIR = PROJECT_DIR / "reports"
DATA_DIR = PROJECT_DIR / "data"

SMTP_CONFIG = {
    "host": os.environ.get("SMTP_HOST", "smtp.163.com"),
    "port": int(os.environ.get("SMTP_PORT", "465")),
    "user": os.environ.get("SMTP_USER", "13844808163@163.com"),
    "password": os.environ.get("SMTP_PASS", "QQgQKpnZNZhhKT52"),
    "from_addr": os.environ.get("SMTP_USER", "13844808163@163.com"),
    "to_addr": os.environ.get("SMTP_TO", "13844808163@163.com, xiaocheng.song@51job.com"),
}

AI_API_KEY = os.environ.get("AI_API_KEY", "")


# ── AI 洞察生成 ─────────────────────────────────

def generate_ai_insight(report_content: str) -> str:
    """调用 DeepSeek API 生成当日最热信息汇总分析（中文）"""
    if not AI_API_KEY:
        return ""

    # 提取每条标题和摘要
    items = []
    for line in report_content.split("\n"):
        if line.startswith("- **"):
            items.append(line.strip())
    if len(items) < 2:
        return ""

    items_text = "\n".join(items[:30])

    prompt = f"""你是招聘和教育行业的资深分析师。以下是今天行业的最新动态标题。请用中文写一段200-350字的分析，分3-4条要点：

1. 提炼今日最值得关注的1-2条核心动态（涉及具体数据的优先）
2. 分析付费相关行为趋势（用户付费意愿、定价变化、新付费产品等）
3. 指出值得关注的舆论或争议点
4. 如果多平台有联动或竞争迹象，点出来

用专业、简练的语气，每条要点前加 🔥 或 📊 或 ⚠️ 或 🤝 等emoji。不需要开头寒暄，直接进入内容。

今日动态：
{items_text}"""

    try:
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {AI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 600,
                "temperature": 0.7,
            },
            timeout=45,
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"  [AI] 洞察生成失败: {e}")
    return ""


# ── 去重逻辑 ─────────────────────────────────────

def extract_sections(content):
    sections = []
    current_title = ""
    current_lines = []
    for line in content.split("\n"):
        if line.startswith("## ") or line.startswith("### "):
            if current_lines:
                h = hashlib.md5("\n".join(current_lines).encode()).hexdigest()
                sections.append((current_title, h))
            current_title = line.strip()
            current_lines = []
        elif line.startswith("> 生成日期") or line.startswith("> 检索范围") or line.startswith("> 信息源限定"):
            continue
        else:
            current_lines.append(line)
    if current_lines:
        h = hashlib.md5("\n".join(current_lines).encode()).hexdigest()
        sections.append((current_title, h))
    return sections


def check_duplicates(report_path, lookback_days=7):
    content = report_path.read_text()
    new_sections = extract_sections(content)
    history_hashes = set()
    cutoff = datetime.now() - timedelta(days=lookback_days)
    for f in sorted(REPORTS_DIR.glob("*.md")):
        if f.name == report_path.name:
            continue
        try:
            if datetime.strptime(f.stem, "%Y-%m-%d") < cutoff:
                continue
        except ValueError:
            pass
        for _, h in extract_sections(f.read_text()):
            history_hashes.add(h)

    fresh, dup, dup_titles = 0, 0, []
    for title, h in new_sections:
        if h in history_hashes:
            dup += 1
            dup_titles.append(title)
        else:
            fresh += 1
    return fresh, dup, dup_titles


# ── 邮件发送 ─────────────────────────────────────

def get_latest_report():
    reports = sorted(REPORTS_DIR.glob("*.md"), reverse=True)
    if not reports:
        print("No report found")
        sys.exit(1)
    return reports[0]


def send_email(subject, html_body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_CONFIG["from_addr"]
    msg["To"] = SMTP_CONFIG["to_addr"]
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    with smtplib.SMTP_SSL(SMTP_CONFIG["host"], SMTP_CONFIG["port"]) as s:
        s.login(SMTP_CONFIG["user"], SMTP_CONFIG["password"])
        s.send_message(msg)
    print(f"Email sent: {subject}")


# ── 热度检测 ─────────────────────────────────────

def section_importance(title, body_lines):
    text = title + "\n" + "\n".join(body_lines)
    if "🔴" in title:
        return "hot"
    if "🟡" in title:
        return "important"
    if "⚪" in title:
        return "meta"

    hot_keywords = ["营收", "净利润", "财报", "亿元", "上市", "融资", "收购", "监管", "处罚", "暴涨", "大跌"]
    important_keywords = ["合作", "战略", "趋势", "用户来源", "付费企业客户", "MAU", "占比", "收入构成", "争议"]
    meta_keywords = ["来源汇总", "总结", "总览", "综合", "跨平台"]

    for kw in meta_keywords:
        if kw in title:
            return "meta"
    for kw in hot_keywords:
        if kw in text[:500]:
            return "hot"
    for kw in important_keywords:
        if kw in title or kw in text[:300]:
            return "important"
    return "normal"


CARD_STYLES = {
    "hot": {
        "border": "#e74c3c",
        "bg": "#fef5f5",
        "badge": '<span style="background:#e74c3c;color:#fff;font-size:11px;padding:2px 8px;border-radius:10px;margin-left:8px;">热门</span>',
    },
    "important": {
        "border": "#f39c12",
        "bg": "#fffdf5",
        "badge": '<span style="background:#f39c12;color:#fff;font-size:11px;padding:2px 8px;border-radius:10px;margin-left:8px;">重点</span>',
    },
    "normal": {
        "border": "#3498db",
        "bg": "#f8fafe",
        "badge": "",
    },
    "meta": {
        "border": "#95a5a6",
        "bg": "#fafafa",
        "badge": "",
    },
}


# ── Markdown → 邮件 HTML ─────────────────────────

def md_to_html(md_path, ai_insight=""):
    content = md_path.read_text()
    lines = content.split("\n")

    blocks = []
    current_heading = None

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("# ") and not stripped.startswith("## "):
            if current_heading is not None:
                blocks.append(current_heading)
            blocks.append(("h1", stripped[2:], []))
            current_heading = None
            continue

        if stripped.startswith("## "):
            if current_heading is not None:
                blocks.append(current_heading)
            current_heading = ("h2", stripped[3:], [])
            continue

        if stripped == "---":
            if current_heading is not None:
                blocks.append(current_heading)
                current_heading = None
            blocks.append(("hr", "", []))
            continue

        if current_heading is not None:
            current_heading[2].append(line)
        elif stripped and blocks and blocks[-1][0] == "h1":
            blocks[-1][2].append(line)

    if current_heading is not None:
        blocks.append(current_heading)

    # ── 渲染 HTML ──
    html = []
    html.append("""<style>
    .email-body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif; max-width: 720px; margin: 0 auto; color: #2c3e50; line-height: 1.7; }
    .insight-box { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: #e8e8e8; border-radius: 12px; margin: 20px 0; padding: 24px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
    .insight-box h2 { color: #ffd700; font-size: 19px; margin: 0 0 16px; border-bottom: 1px solid rgba(255,215,0,0.3); padding-bottom: 10px; }
    .insight-box p { font-size: 15px; margin: 8px 0; line-height: 1.8; }
    .card { border-radius: 8px; margin: 16px 0; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
    .card-header { padding: 12px 18px; font-size: 17px; font-weight: 700; display: flex; align-items: center; }
    .card-body { padding: 8px 18px 16px; }
    .card-body p { margin: 6px 0; }
    .card-body ul { margin: 6px 0; padding-left: 20px; }
    .card-body li { margin: 6px 0; }
    .meta-row { font-size: 13px; color: #888; margin: 2px 0 8px; }
    .meta-row a { color: #2980b9; }
    table.data-table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 14px; }
    table.data-table th { background: #f0f4f8; font-weight: 700; padding: 10px 14px; text-align: left; border-bottom: 2px solid #d0d7de; }
    table.data-table td { padding: 8px 14px; border-bottom: 1px solid #e8ecf0; }
    table.data-table tr:nth-child(even) td { background: #fafbfc; }
    hr.divider { border: none; border-top: 1px solid #e0e0e0; margin: 24px 0; }
    a { color: #2980b9; text-decoration: underline; }
    .footer { margin-top: 32px; padding: 16px; background: #f5f6f8; border-radius: 8px; font-size: 13px; color: #888; text-align: center; }
</style>""")

    html.append('<div class="email-body">')

    for block in blocks:
        btype = block[0]

        if btype == "h1":
            title = block[1]
            subtitle = "\n".join(block[2]).strip().replace("> ", "")
            html.append(f'''
            <div style="text-align:center;padding:24px 0 8px;">
                <h1 style="font-size:22px;color:#1a1a2e;margin:0 0 8px;font-weight:800;">{title}</h1>
                <p style="color:#888;font-size:13px;margin:0;">{subtitle}</p>
            </div>''')

            # ── AI 洞察插入在标题下方 ──
            if ai_insight:
                insight_html = ai_insight.replace("\n", "<br>")
                html.append(f'''
            <div class="insight-box">
                <h2>🤖 AI 今日洞察</h2>
                <p>{insight_html}</p>
            </div>''')
            continue

        if btype == "hr":
            html.append('<hr class="divider">')
            continue

        if btype == "h2":
            title = block[1]
            body_lines = block[2]
            importance = section_importance(title, body_lines)
            style = CARD_STYLES[importance]

            body_html = []
            in_table = False
            in_list = False

            for line in body_lines:
                stripped = line.strip()
                if not stripped:
                    if in_table:
                        body_html.append("</table>")
                        in_table = False
                    if in_list:
                        body_html.append("</ul>")
                        in_list = False
                    continue

                if "|" in stripped and stripped.startswith("|"):
                    if not in_table:
                        in_table = True
                        body_html.append('<table class="data-table">')
                    if all(c in "|-: " for c in stripped):
                        continue
                    cells = [c.strip() for c in stripped.split("|")[1:-1]]
                    is_first = body_html and body_html[-1].startswith("<table")
                    tag = "th" if is_first else "td"
                    body_html.append("<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>")
                    continue
                else:
                    if in_table:
                        body_html.append("</table>")
                        in_table = False

                if stripped.startswith("- ") or stripped.startswith("* "):
                    if not in_list:
                        in_list = True
                        body_html.append('<ul style="margin:2px 0;padding-left:20px;">')
                    item = stripped[2:]
                    item = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', item)
                    # 来源行特殊样式
                    if "📅" in item:
                        item = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', item)
                        body_html.append(f'<li style="color:#555;font-size:13px;list-style:none;margin-left:-16px;">{item}</li>')
                    else:
                        body_html.append(f"<li>{item}</li>")
                    continue
                else:
                    if in_list:
                        body_html.append("</ul>")
                        in_list = False

                if stripped.startswith("> "):
                    quote_class = "warn" if any(kw in stripped for kw in ["⚠", "风险", "警惕", "争议"]) else "info"
                    body_html.append(f'<blockquote class="{quote_class}">{stripped[2:]}</blockquote>')
                    continue

                text = stripped
                text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
                text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
                # 元数据行
                if text.startswith("📅"):
                    text = f'<span class="meta-row">{text}</span>'
                body_html.append(f"<p>{text}</p>")

            if in_table:
                body_html.append("</table>")
            if in_list:
                body_html.append("</ul>")

            badge_html = style["badge"]
            html.append(f'''
            <div class="card" style="border-left:4px solid {style['border']};background:{style['bg']};">
                <div class="card-header" style="color:{style['border']};background:rgba(255,255,255,0.6);">
                    {title}{badge_html}
                </div>
                <div class="card-body">
                    {"".join(body_html) if body_html else "<p>暂无详细信息</p>"}
                </div>
            </div>''')

    html.append(f'''
    <div class="footer">
        本报告自动生成 · {datetime.now().strftime("%Y-%m-%d %H:%M")} CST<br>
        信息源：微信/微博/抖音/B站/知乎/小红书 + 各平台官网<br>
        基于公开信息整理，仅供内部参考
    </div>''')

    html.append("</div>")
    return "\n".join(html)


# ── 主流程 ───────────────────────────────────────

def main():
    report = get_latest_report()
    content = report.read_text()

    fresh, dup, dup_titles = check_duplicates(report, lookback_days=7)
    print(f"[去重] 全新段落: {fresh}, 重复段落: {dup}")
    if dup_titles:
        print(f"[去重] 重复: {dup_titles}")

    if fresh == 0 and dup > 0:
        print("所有内容均已出现，跳过发送")
        sys.exit(0)

    # 生成 AI 洞察
    print("[AI] 生成今日洞察...")
    ai_insight = generate_ai_insight(content)
    if ai_insight:
        print(f"  -> 洞察 {len(ai_insight)} 字符")
    else:
        print("  -> 跳过（API 不可用或条目不足）")

    total = fresh + dup
    dup_rate = dup / total if total > 0 else 0
    subject = f"【招聘/教育私域付费情报】{report.stem}"
    if dup_rate > 0.8:
        subject += "（增量更新）"

    html_body = md_to_html(report, ai_insight)
    send_email(subject, html_body)


if __name__ == "__main__":
    main()
