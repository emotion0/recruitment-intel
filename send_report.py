#!/usr/bin/env python3
"""发送最新情报报告邮件，含细粒度去重逻辑。
每天与过去 7 天的报告逐条比对，只发送真正新的信息。
"""

import smtplib
import hashlib
import json
import sys
import re
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


def load_json(path, default=None):
    if path.exists():
        return json.loads(path.read_text())
    return default if default is not None else {}


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def extract_sections(content):
    """提取报告中每个 ## 和 ### 段落，返回 [(标题, 内容hash), ...]"""
    sections = []
    current_title = ""
    current_lines = []
    for line in content.split("\n"):
        if line.startswith("## ") or line.startswith("### "):
            if current_lines:
                text = "\n".join(current_lines)
                h = hashlib.md5(text.encode()).hexdigest()
                sections.append((current_title, h))
            current_title = line.strip()
            current_lines = []
        elif line.startswith("> 生成时间") or line.startswith("> 覆盖平台"):
            continue  # 跳过元数据行
        else:
            current_lines.append(line)
    if current_lines:
        text = "\n".join(current_lines)
        h = hashlib.md5(text.encode()).hexdigest()
        sections.append((current_title, h))
    return sections


def check_duplicates(report_path, lookback_days=7):
    """检查报告中各段落是否与历史报告重复。
    返回 (全新段落数, 重复段落数, 重复标题列表)"""
    content = report_path.read_text()
    new_sections = extract_sections(content)

    # 收集历史报告的段落 hash
    history_hashes = set()
    cutoff = datetime.now() - timedelta(days=lookback_days)
    for f in sorted(REPORTS_DIR.glob("*.md")):
        if f.name == report_path.name:
            continue
        try:
            date_str = f.stem
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
            if file_date < cutoff:
                continue
        except ValueError:
            pass
        for _, h in extract_sections(f.read_text()):
            history_hashes.add(h)

    fresh = 0
    dup = 0
    dup_titles = []
    for title, h in new_sections:
        if h in history_hashes:
            dup += 1
            dup_titles.append(title)
        else:
            fresh += 1

    return fresh, dup, dup_titles


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


def section_importance(title, body_lines):
    """根据标题和内容判断重要程度: 🔴hot / 🟡important / 🟢normal / ⚪meta"""
    text = title + "\n" + "\n".join(body_lines)

    # 显式标记优先
    if "🔴" in title:
        return "hot"
    if "🟡" in title:
        return "important"
    if "🟢" in title:
        return "normal"
    if "⚪" in title:
        return "meta"

    # 自动检测
    hot_keywords = ["营收", "净利润", "财报", "亿元", "上市", "融资", "收购", "监管", "处罚", "暴涨", "大跌"]
    important_keywords = ["合作", "战略", "趋势", "用户来源", "付费企业客户", "MAU", "占比", "收入构成"]
    meta_keywords = ["来源汇总", "总结", "总览", "行业竞争格局", "商业模式图谱"]

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


# 热度级别对应的样式
CARD_STYLES = {
    "hot": {
        "border": "#e74c3c",
        "bg": "#fef5f5",
        "badge": '<span style="background:#e74c3c;color:#fff;font-size:11px;padding:2px 8px;border-radius:10px;margin-left:8px;">HOT</span>',
        "label": "🔥 热门"
    },
    "important": {
        "border": "#f39c12",
        "bg": "#fffdf5",
        "badge": '<span style="background:#f39c12;color:#fff;font-size:11px;padding:2px 8px;border-radius:10px;margin-left:8px;">重点</span>',
        "label": "📌 重点"
    },
    "normal": {
        "border": "#3498db",
        "bg": "#f8fafe",
        "badge": "",
        "label": ""
    },
    "meta": {
        "border": "#95a5a6",
        "bg": "#fafafa",
        "badge": "",
        "label": ""
    },
}


def md_to_html(md_path):
    content = md_path.read_text()
    lines = content.split("\n")

    # ---------- 解析阶段：按 ## 分块 ----------
    blocks = []  # [(heading_level, heading_text, body_lines)]
    current_heading = None
    current_body = []
    in_meta = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            # 一级标题 - 报告主标题
            if current_heading is not None:
                blocks.append(current_heading)
            blocks.append(("h1", stripped[2:], []))
            current_heading = None
            continue

        if stripped.startswith("## "):
            if current_heading is not None:
                blocks.append(current_heading)
            current_heading = ("h2", stripped[3:], [])
            current_body = []
            continue

        if stripped.startswith("### "):
            if current_body:
                # 将前面的内容作为 h2 的附属
                pass
            if current_heading is not None:
                # 子标题作为 body 的一部分保留
                current_heading[2].append(line)
            continue

        if stripped == "---":
            if current_heading is not None:
                blocks.append(current_heading)
                current_heading = None
            blocks.append(("hr", "", []))
            continue

        if current_heading is not None:
            current_heading[2].append(line)
        elif stripped:
            # 一级标题后的导语
            if blocks and blocks[-1][0] == "h1":
                blocks[-1][2].append(line)

    if current_heading is not None:
        blocks.append(current_heading)

    # ---------- 渲染阶段 ----------
    html = []

    # 全局样式
    html.append("""<style>
    .email-body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif; max-width: 720px; margin: 0 auto; color: #2c3e50; line-height: 1.7; }
    .card { border-radius: 8px; margin: 16px 0; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
    .card-header { padding: 12px 18px; font-size: 17px; font-weight: 700; display: flex; align-items: center; }
    .card-body { padding: 8px 18px 16px; }
    .card-body p { margin: 6px 0; }
    .card-body ul { margin: 6px 0; padding-left: 20px; }
    .card-body li { margin: 4px 0; }
    table.data-table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 14px; }
    table.data-table th { background: #f0f4f8; color: #2c3e50; font-weight: 700; padding: 10px 14px; text-align: left; border-bottom: 2px solid #d0d7de; }
    table.data-table td { padding: 8px 14px; border-bottom: 1px solid #e8ecf0; }
    table.data-table tr:nth-child(even) td { background: #fafbfc; }
    table.data-table tr:hover td { background: #f0f4ff; }
    blockquote.warn { border-left: 4px solid #e67e22; background: #fef9f0; margin: 10px 0; padding: 10px 14px; color: #8a5d1a; border-radius: 0 6px 6px 0; }
    blockquote.info { border-left: 4px solid #3498db; background: #f0f7fd; margin: 10px 0; padding: 10px 14px; color: #1a5276; border-radius: 0 6px 6px 0; }
    .section-badge { font-size: 11px; padding: 2px 8px; border-radius: 10px; margin-left: 8px; font-weight: 600; }
    hr.divider { border: none; border-top: 1px solid #e0e0e0; margin: 24px 0; }
    a { color: #2980b9; text-decoration: underline; }
    .footer { margin-top: 32px; padding: 16px; background: #f5f6f8; border-radius: 8px; font-size: 13px; color: #888; text-align: center; }
</style>""")

    html.append('<div class="email-body">')

    for block in blocks:
        btype = block[0]

        if btype == "h1":
            title = block[1]
            subtitle = "\n".join(block[2]).strip()
            html.append(f'''
            <div style="text-align:center;padding:24px 0 8px;">
                <h1 style="font-size:22px;color:#1a1a2e;margin:0 0 8px;font-weight:800;">{title}</h1>
                <p style="color:#888;font-size:13px;margin:0;">{subtitle}</p>
            </div>''')
            continue

        if btype == "hr":
            html.append('<hr class="divider">')
            continue

        if btype == "h2":
            title = block[1]
            body_lines = block[2]
            body_text = "\n".join(body_lines)
            importance = section_importance(title, body_lines)
            style = CARD_STYLES[importance]

            # ------ 渲染卡片内容 ------
            body_html = []
            in_table = False
            in_list = False
            paragraphs = []

            for line in body_lines:
                stripped = line.strip()

                # 空行
                if not stripped:
                    if in_table:
                        body_html.append("</table>")
                        in_table = False
                    if in_list:
                        body_html.append("</ul>")
                        in_list = False
                    continue

                # 表格
                if "|" in stripped and stripped.startswith("|"):
                    if not in_table:
                        in_table = True
                        body_html.append('<table class="data-table">')
                    if all(c in "|-: " for c in stripped):
                        continue
                    cells = [c.strip() for c in stripped.split("|")[1:-1]]
                    is_first_row = body_html and body_html[-1].startswith("<table")
                    tag = "th" if is_first_row else "td"
                    body_html.append(
                        "<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>"
                    )
                    continue
                else:
                    if in_table:
                        body_html.append("</table>")
                        in_table = False

                # 列表
                if stripped.startswith("- ") or stripped.startswith("* "):
                    if not in_list:
                        in_list = True
                        body_html.append('<ul style="margin:6px 0;padding-left:20px;">')
                    item = stripped[2:]
                    # 解析粗体
                    item = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', item)
                    body_html.append(f"<li>{item}</li>")
                    continue
                else:
                    if in_list:
                        body_html.append("</ul>")
                        in_list = False

                # 引用
                if stripped.startswith("> "):
                    quote_class = "warn" if ("⚠" in stripped or "风险" in stripped or "警惕" in stripped or "争议" in stripped) else "info"
                    body_html.append(f'<blockquote class="{quote_class}">{stripped[2:]}</blockquote>')
                    continue

                # 普通段落
                text = stripped
                text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
                text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
                body_html.append(f"<p style='margin:4px 0;'>{text}</p>")

            if in_table:
                body_html.append("</table>")
            if in_list:
                body_html.append("</ul>")

            # ------ 组装卡片 ------
            badge_html = style["badge"]
            html.append(f'''
            <div class="card" style="border-left:4px solid {style['border']};background:{style['bg']};">
                <div class="card-header" style="color:{style['border']};background:rgba(255,255,255,0.6);">
                    {title}{badge_html}
                </div>
                <div class="card-body">
                    {"".join(body_html) if body_html else "<p style='color:#999;'>暂无详细信息</p>"}
                </div>
            </div>''')

    # 页脚
    html.append(f'''
    <div class="footer">
        本报告由 Claude 自动生成 · {datetime.now().strftime("%Y-%m-%d %H:%M")}<br>
        基于公开信息整理，仅供内部参考
    </div>''')

    html.append("</div>")
    return "\n".join(html)


def main():
    report = get_latest_report()
    content = report.read_text()

    # 细粒度去重：逐段与近 7 天报告比对
    fresh, dup, dup_titles = check_duplicates(report, lookback_days=7)

    print(f"[去重] 全新段落: {fresh}, 重复段落: {dup}")
    if dup_titles:
        print(f"[去重] 重复的段落: {dup_titles}")

    # 如果完全没有新内容，跳过发送
    if fresh == 0 and dup > 0:
        print("所有内容均已出现在前 7 天报告中，跳过发送")
        sys.exit(0)

    # 如果重复率超过 80%，在邮件标题中标注
    total = fresh + dup
    dup_rate = dup / total if total > 0 else 0
    subject = f"【招聘/教育私域付费情报】{report.stem}"
    if dup_rate > 0.8:
        subject += "（增量更新）"

    html_body = md_to_html(report)
    send_email(subject, html_body)


if __name__ == "__main__":
    main()
