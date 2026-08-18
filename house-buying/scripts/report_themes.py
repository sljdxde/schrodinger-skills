#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""报告主题（样式）中心 · 参考 awesome-claude-design 五大美学族系。

职责：
  - 集中存放各套 HTML 主题 CSS（editorial / warm / cinematic / data / glass / olive）。
  - 提供统一的报告骨架渲染 render_report_html(analysis, theme_key)，
    所有主题共用同一套正文 HTML，仅替换 <style> 主题，保证「同样的内容、不同的皮」。
  - 提供主题选择机制：list_themes() 列候选、resolve_theme() 解析（参数 > 已存偏好 > 默认）、
    save_theme() 持久化用户偏好（house-buying/.cache/report_theme.txt）。

用法（被 gen_styled_report.py / build_report.py 调用）：
  from report_themes import render_report_html, list_themes, resolve_theme, save_theme
"""
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import data_sources as ds  # noqa: E402

STATE_FILE = ROOT / ".cache" / "report_theme.txt"
DEFAULT_THEME = "warm"  # 默认皮肤改为 Warm Editorial（暖色调编辑风）

BASE_REPORT_CSS = """
.cite-ref{font-size:.82em;vertical-align:super;font-weight:600;text-decoration:none}
.cite-ref:hover{text-decoration:underline}
/* 通用数据表（data_sources 渲染的 class='d'，6 套主题共用，靠主题变量自适应） */
table.d{width:100%;border-collapse:collapse;margin:16px 0;font-size:14px;
  background:var(--surface,#fff);border:1px solid var(--line,#e3e3e3);
  border-radius:var(--radius,8px);overflow:hidden}
table.d th{text-align:left;background:var(--surface,#fff);color:var(--muted,#666);
  font-weight:600;padding:10px 12px;border-bottom:2px solid var(--accent,#c96442)}
table.d td{padding:10px 12px;border-bottom:1px solid var(--line,#e3e3e3);vertical-align:top}
table.d tr:last-child td{border-bottom:none}
table.d td.num,table.d .num{text-align:right;font-variant-numeric:tabular-nums}
/* 小注（表格/板块下方说明） */
.note{font-size:12.5px;color:var(--muted,#666);margin:10px 0 0;line-height:1.65}
/* 图表容器（render_*_chart 经 _chart_block 包裹） */
.chartbox{margin:18px 0;padding:14px;background:var(--surface,#fff);
  border:1px solid var(--line,#e3e3e3);border-radius:var(--radius,8px)}
.chartbox svg{display:block;width:100%;height:auto;margin:0}
.caption{font-size:12.5px;color:var(--muted,#666);margin-top:10px;text-align:center;line-height:1.5}
/* 成交明细 / 最近成交模块容器 */
.tx-detail{margin:14px 0}
.tx-detail .card{background:var(--surface,#fff);border:1px solid var(--line,#e3e3e3);
  border-radius:var(--radius,8px);padding:14px 16px;margin:10px 0}
.recent-tx h3{margin:18px 0 8px;font-size:17px}
"""

# --------------------------------------------------------------------------- #
# 五大美学族系 CSS（与 awesome-claude-design 对齐；均规避 AI 默认指纹：
# 不用青色强调 / 紫色渐变 / 闪烁点）
# --------------------------------------------------------------------------- #
_THEME_CSS = {
    "editorial": """
:root{
  --bg:#ffffff; --surface:#ffffff; --text:#0f0f14; --muted:#6b7280;
  --accent:#5e6ad2; --line:#e6e7eb; --radius:2px;
  --serif:"Space Grotesk",-apple-system,"Helvetica Neue",sans-serif;
  --sans:"Archivo",-apple-system,"Helvetica Neue",Arial,sans-serif;
  --mono:"Space Grotesk",ui-monospace,monospace;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:var(--sans);
  line-height:1.7;font-size:16px;-webkit-font-smoothing:antialiased;
  font-feature-settings:"tnum" 1}
.doc{max-width:760px;margin:0 auto;padding:72px 28px 96px}
.flair{height:3px;background:var(--accent);border-radius:2px;margin-bottom:40px}
.doc-head h1{font-family:var(--serif);font-weight:600;font-size:38px;
  letter-spacing:-.02em;line-height:1.15}
.kicker{font-family:var(--mono);font-size:12px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--accent);margin-top:14px}
.conclusion{margin:34px 0;padding:22px 24px;border-left:3px solid var(--accent);
  background:#fafafe;font-size:17px;border-radius:var(--radius)}
.meta{color:var(--muted);font-size:13px;border-top:1px solid var(--line);
  border-bottom:1px solid var(--line);padding:14px 0;margin:26px 0 8px}
section{margin:46px 0}
h2{font-family:var(--serif);font-size:23px;font-weight:600;letter-spacing:-.01em;
  padding-bottom:10px;border-bottom:1px solid var(--line);margin-bottom:18px}
ul{list-style:none}
li{padding:7px 0 7px 18px;position:relative}
li::before{content:"";position:absolute;left:0;top:16px;width:6px;height:6px;
  background:var(--accent);border-radius:1px}
b{font-weight:600}
.muted{color:var(--muted);font-size:13px;margin-top:14px}
a{color:var(--accent);text-decoration:none;border-bottom:1px solid rgba(94,106,210,.3)}
a:hover{border-bottom-color:var(--accent)}
.recent-tx h3{font-family:var(--serif);font-size:18px;margin-bottom:12px}
.tx-table{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:13.5px}
.tx-table th{text-align:left;color:var(--muted);font-weight:600;
  border-bottom:2px solid var(--line);padding:9px 10px;font-size:12px;
  letter-spacing:.04em;text-transform:uppercase}
.tx-table td{padding:10px;border-bottom:1px solid var(--line)}
.tx-table td:nth-child(3),.tx-table td:nth-child(4){text-align:right}
.tx-table tbody tr:hover{background:#fafafe}
.cites{list-style:none;counter-reset:c}
.cites li{counter-increment:c;padding:8px 0 8px 30px;position:relative;
  font-size:13.5px;color:var(--muted);border-bottom:1px solid var(--line)}
.cites li::before{content:"["counter(c)"]";position:absolute;left:0;top:8px;
  color:var(--accent);font-family:var(--mono);font-weight:600}
.refs h2{margin-top:56px}
""",
    "warm": """
:root{
  --bg:#f4f3ee; --surface:#fffdf9; --text:#191817; --muted:#6f6a63;
  --accent:#c96442; --line:#e3ddd2; --radius:10px;
  --serif:"Fraunces",Georgia,"Times New Roman",serif;
  --sans:"Spectral",Georgia,serif;
  --mono:"Spectral",ui-monospace,monospace;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:var(--sans);
  line-height:1.8;font-size:16.5px}
.doc{max-width:740px;margin:0 auto;padding:70px 30px 94px}
.flair{height:4px;background:linear-gradient(90deg,var(--accent),#e0a06a);
  border-radius:3px;margin-bottom:38px}
.doc-head h1{font-family:var(--serif);font-weight:600;font-size:40px;
  letter-spacing:-.01em;line-height:1.18}
.kicker{font-family:var(--mono);font-size:12.5px;letter-spacing:.12em;
  text-transform:uppercase;color:var(--accent);margin-top:14px}
.conclusion{margin:34px 0;padding:24px 26px;background:var(--surface);
  border:1px solid var(--line);border-radius:var(--radius);
  box-shadow:0 1px 0 rgba(25,24,23,.03);font-size:17px}
.meta{color:var(--muted);font-size:13px;font-style:italic;
  border-top:1px solid var(--line);padding-top:14px;margin:26px 0 6px}
section{margin:48px 0}
h2{font-family:var(--serif);font-size:25px;font-weight:600;
  padding-bottom:8px;margin-bottom:18px}
ul{list-style:none}
li{padding:8px 0 8px 22px;position:relative}
li::before{content:"—";position:absolute;left:0;top:8px;color:var(--accent);font-weight:700}
b{font-weight:600;color:#3a2a22}
.muted{color:var(--muted);font-size:13px;margin-top:14px;font-style:italic}
a{color:var(--accent);text-decoration:none;border-bottom:1px solid rgba(201,100,66,.35)}
a:hover{border-bottom-color:var(--accent)}
.recent-tx h3{font-family:var(--serif);font-size:19px;margin-bottom:12px}
.tx-table{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:13.5px}
.tx-table th{text-align:left;color:var(--muted);font-weight:600;
  border-bottom:2px solid var(--accent);padding:10px;font-size:12px}
.tx-table td{padding:11px 10px;border-bottom:1px solid var(--line)}
.tx-table td:nth-child(3),.tx-table td:nth-child(4){text-align:right}
.tx-table tbody tr:hover{background:var(--surface)}
.cites{list-style:none;padding-top:6px}
.cites li{padding:9px 0 9px 26px;position:relative;font-size:13.5px;
  color:var(--muted);border-bottom:1px solid var(--line)}
.cites li::before{content:"♦";position:absolute;left:0;top:9px;color:var(--accent)}
.refs h2{margin-top:56px;font-family:var(--serif)}
""",
    "cinematic": """
:root{
  --bg:#0b0d14; --surface:#141925; --text:#e8eaf0; --muted:#8b93a7;
  --accent:#3b82f6; --line:#232a3a; --radius:3px;
  --serif:"Space Grotesk",-apple-system,sans-serif;
  --sans:"IBM Plex Sans",-apple-system,sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,monospace;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:var(--sans);
  line-height:1.7;font-size:16px;-webkit-font-smoothing:antialiased}
.doc{max-width:780px;margin:0 auto;padding:0 28px 96px}
.flair{height:120px;margin:0 -28px 40px;
  background:linear-gradient(135deg,#0b0d14 0%,#15233f 60%,#1c69d4 220%);
  border-bottom:1px solid var(--line);position:relative}
.flair::after{content:"";position:absolute;left:28px;bottom:24px;width:54px;
  height:3px;background:var(--accent)}
.doc-head{padding-top:8px}
.doc-head h1{font-family:var(--serif);font-weight:600;font-size:40px;
  letter-spacing:-.02em;line-height:1.15}
.kicker{font-family:var(--mono);font-size:12px;letter-spacing:.16em;
  text-transform:uppercase;color:var(--accent);margin-top:14px}
.conclusion{margin:34px 0;padding:22px 24px;border-left:3px solid var(--accent);
  background:var(--surface);font-size:16.5px;border-radius:var(--radius)}
.meta{color:var(--muted);font-size:12.5px;border-top:1px solid var(--line);
  border-bottom:1px solid var(--line);padding:13px 0;margin:26px 0 8px;
  font-family:var(--mono)}
section{margin:46px 0}
h2{font-family:var(--serif);font-size:22px;font-weight:600;letter-spacing:.01em;
  padding-bottom:10px;border-bottom:1px solid var(--line);margin-bottom:18px;
  color:#f3f5fb}
ul{list-style:none}
li{padding:8px 0 8px 20px;position:relative}
li::before{content:"";position:absolute;left:0;top:16px;width:7px;height:7px;
  background:var(--accent);border-radius:50%}
b{font-weight:600;color:#fff}
.muted{color:var(--muted);font-size:12.5px;margin-top:14px;font-family:var(--mono)}
a{color:var(--accent);text-decoration:none;border-bottom:1px solid rgba(59,130,246,.35)}
a:hover{border-bottom-color:var(--accent)}
.recent-tx h3{font-family:var(--serif);font-size:18px;margin-bottom:12px;color:#f3f5fb}
.tx-table{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:13px}
.tx-table th{text-align:left;color:var(--muted);font-weight:600;
  border-bottom:2px solid var(--accent);padding:9px 10px;font-size:11.5px;
  letter-spacing:.05em;text-transform:uppercase}
.tx-table td{padding:10px;border-bottom:1px solid var(--line)}
.tx-table td:nth-child(3),.tx-table td:nth-child(4){text-align:right}
.tx-table tbody tr:hover{background:var(--surface)}
.cites{list-style:none;counter-reset:c}
.cites li{padding:8px 0 8px 28px;position:relative;font-size:13px;
  color:var(--muted);border-bottom:1px solid var(--line);counter-increment:c}
.cites li::before{content:"[" counter(c) "]";position:absolute;left:0;top:8px;
  color:var(--accent);font-family:var(--mono);font-weight:600}
.refs h2{margin-top:56px}
""",
    "data": """
:root{
  --bg:#0e1014; --surface:#161a21; --text:#d7dbe3; --muted:#7d8595;
  --accent:#ffd400; --accent2:#4f8cff; --line:#262c38; --radius:0px;
  --serif:"IBM Plex Sans",-apple-system,sans-serif;
  --sans:"IBM Plex Sans",-apple-system,sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,monospace;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:var(--sans);
  line-height:1.65;font-size:15px}
.doc{max-width:840px;margin:0 auto;padding:40px 24px 80px}
.flair{display:flex;gap:8px;margin-bottom:26px}
.flair span{height:6px;flex:1;background:var(--accent);opacity:.85}
.flair span:nth-child(2){background:var(--accent2);opacity:.7}
.flair span:nth-child(3){background:var(--muted);opacity:.5}
.doc-head h1{font-family:var(--mono);font-weight:600;font-size:26px;
  letter-spacing:-.01em;text-transform:uppercase}
.kicker{font-family:var(--mono);font-size:11.5px;letter-spacing:.1em;
  text-transform:uppercase;color:var(--accent);margin-top:10px}
.conclusion{margin:24px 0;padding:16px 18px;border-left:3px solid var(--accent);
  background:var(--surface);font-size:14.5px}
.meta{color:var(--muted);font-size:11.5px;font-family:var(--mono);
  border:1px solid var(--line);padding:10px 12px;margin:20px 0 4px;
  background:var(--surface)}
section{margin:30px 0}
h2{font-family:var(--mono);font-size:14px;font-weight:600;letter-spacing:.08em;
  text-transform:uppercase;color:var(--accent);padding:10px 12px;
  background:var(--surface);border:1px solid var(--line);border-left:3px solid var(--accent);
  margin-bottom:16px}
ul{list-style:none}
li{padding:7px 0 7px 16px;position:relative;font-size:14.5px}
li::before{content:"▸";position:absolute;left:0;top:7px;color:var(--accent2);font-size:12px}
b{font-weight:600;color:#fff;font-family:var(--mono)}
.muted{color:var(--muted);font-size:11.5px;margin-top:12px;font-family:var(--mono)}
a{color:var(--accent2);text-decoration:none;border-bottom:1px solid rgba(79,140,255,.4)}
a:hover{border-bottom-color:var(--accent2)}
.recent-tx h3{font-family:var(--mono);font-size:13px;text-transform:uppercase;
  letter-spacing:.06em;color:var(--accent);margin-bottom:10px}
.tx-table{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:12.5px}
.tx-table th{text-align:left;color:var(--muted);font-weight:600;
  background:var(--surface);border:1px solid var(--line);padding:8px 9px;font-size:11px;
  letter-spacing:.05em;text-transform:uppercase}
.tx-table td{padding:8px 9px;border:1px solid var(--line)}
.tx-table td:nth-child(3),.tx-table td:nth-child(4){text-align:right;color:#fff}
.tx-table tbody tr:nth-child(odd){background:rgba(255,255,255,.02)}
.tx-table tbody tr:hover{background:rgba(255,212,0,.06)}
.cites{list-style:none;counter-reset:c;font-family:var(--mono)}
.cites li{padding:7px 0 7px 26px;position:relative;font-size:12px;
  color:var(--muted);border-bottom:1px solid var(--line);counter-increment:c}
.cites li::before{content:"[" counter(c) "]";position:absolute;left:0;top:7px;
  color:var(--accent);font-weight:600}
.refs h2{margin-top:36px}
""",
    "glass": """
:root{
  --bg:#eef2ff; --surface:rgba(255,255,255,.62); --text:#1f2430; --muted:#6b7280;
  --accent:#6d5efc; --line:rgba(255,255,255,.7); --radius:18px;
  --serif:"Plus Jakarta Sans",-apple-system,sans-serif;
  --sans:"Plus Jakarta Sans",-apple-system,sans-serif;
  --mono:"Plus Jakarta Sans",ui-monospace,monospace;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:
   radial-gradient(1200px 600px at 12% -8%,#ffe9f6 0%,transparent 55%),
   radial-gradient(1000px 560px at 96% 6%,#e3fbf4 0%,transparent 52%),
   radial-gradient(900px 700px at 50% 112%,#eaf0ff 0%,transparent 55%),
   var(--bg);
  color:var(--text);font-family:var(--sans);line-height:1.75;font-size:16px;
  min-height:100vh;padding:48px 0 90px}
.doc{max-width:760px;margin:0 auto;padding:0 26px}
.flair{height:90px;margin:0 -26px 34px;border-radius:0 0 26px 26px;
  background:linear-gradient(120deg,#6d5efc,#9b8bff 55%,#5ed1c4);
  box-shadow:0 10px 30px rgba(109,94,252,.18)}
.doc-head{padding:0 6px}
.doc-head h1{font-family:var(--serif);font-weight:700;font-size:38px;
  letter-spacing:-.02em;line-height:1.18}
.kicker{font-family:var(--mono);font-size:12px;letter-spacing:.1em;
  text-transform:uppercase;color:var(--accent);margin-top:14px}
.conclusion,.meta,section{background:var(--surface);backdrop-filter:blur(14px);
  -webkit-backdrop-filter:blur(14px);border:1px solid var(--line);
  border-radius:var(--radius);box-shadow:0 8px 28px rgba(31,36,48,.06);
  padding:24px 26px;margin:22px 0}
.meta{font-size:12.5px;color:var(--muted);font-style:italic;padding:14px 22px}
h2{font-family:var(--serif);font-size:22px;font-weight:700;
  padding-bottom:8px;margin-bottom:14px;color:#2a2740}
ul{list-style:none}
li{padding:7px 0 7px 22px;position:relative}
li::before{content:"";position:absolute;left:0;top:15px;width:8px;height:8px;
  border-radius:50%;background:var(--accent);opacity:.8}
b{font-weight:700}
.muted{color:var(--muted);font-size:12.5px;margin-top:12px;font-style:italic}
a{color:var(--accent);text-decoration:none;border-bottom:1px solid rgba(109,94,252,.3)}
a:hover{border-bottom-color:var(--accent)}
.recent-tx h3{font-family:var(--serif);font-size:18px;font-weight:700;margin-bottom:12px}
.tx-table{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:13px}
.tx-table th{text-align:left;color:var(--muted);font-weight:600;
  border-bottom:2px solid var(--accent);padding:9px 10px;font-size:11.5px;
  text-transform:uppercase;letter-spacing:.04em}
.tx-table td{padding:10px;border-bottom:1px solid rgba(31,36,48,.08)}
.tx-table td:nth-child(3),.tx-table td:nth-child(4){text-align:right}
.tx-table tbody tr:hover{background:rgba(109,94,252,.05)}
.cites{list-style:none;counter-reset:c}
.cites li{padding:8px 0 8px 26px;position:relative;font-size:13px;
  color:var(--muted);border-bottom:1px solid rgba(31,36,48,.08);counter-increment:c}
.cites li::before{content:"[" counter(c) "]";position:absolute;left:0;top:8px;
  color:var(--accent);font-family:var(--mono);font-weight:700}
.refs{margin-top:8px}
""",
}


def _olive_theme_css() -> str:
    """经典「橄榄手记」主题：复用原 OLIVE_CSS，并补齐统一骨架所需的容器类。"""
    return ds.olive_theme_css() + """
/* 统一骨架适配（主题化后报告通用容器） */
.doc{max-width:860px;margin:0 auto;padding:32px 20px 80px}
.flair{height:4px;background:var(--olive);border-radius:3px;margin-bottom:28px}
.doc-head h1{margin:0 0 6px}
.kicker{font-size:12px;letter-spacing:.12em;text-transform:uppercase;
  color:var(--accent);margin:10px 0 0}
section{margin:40px 0}
.conclusion{background:var(--olive-soft);border:1px solid var(--olive);
  border-radius:14px;padding:18px 22px;margin:18px 0;font-size:15px;line-height:1.7}
.refs{margin-top:8px}
"""


# 主题元信息（key -> 展示名 / 描述），用于候选列表与用户选择 UI
THEME_META = {
    "editorial": ("Editorial Minimalism · Linear 风",
                  "白底靛蓝、发丝线分隔、Space Grotesk+Archivo，克制专业"),
    "warm": ("Warm Editorial · Claude 暖色",
             "暖纸赤陶、Fraunces+Spectral 衬线，温暖可信（个人置业首选）"),
    "cinematic": ("Cinematic Dark · BMW 风",
                  "近黑藏蓝、企业蓝、顶部电影感渐变 hero，戏剧留白"),
    "data": ("Data-Dense Pro · PostHog 风",
             "暗色仪表盘、等宽数字、密集边框表格、黄/蓝双强调，最突出数据"),
    "glass": ("Glass / Soft-Futurism · Apple 风",
              "毛玻璃 backdrop-blur、柔和粉彩渐变、圆润通透，轻盈 premium"),
    "olive": ("橄榄手记 · 经典",
              "浅色高对比、原报告品牌视觉（默认，未选型时沿用）"),
}

# 合并：自定义 5 套 + 经典 olive
THEMES = {}
for _k in ("editorial", "warm", "cinematic", "data", "glass"):
    THEMES[_k] = {"label": THEME_META[_k][0], "desc": THEME_META[_k][1],
                  "css": _THEME_CSS[_k]}
THEMES["olive"] = {"label": THEME_META["olive"][0], "desc": THEME_META["olive"][1],
                   "css": _olive_theme_css()}


# --------------------------------------------------------------------------- #
# 主题选择 / 持久化
# --------------------------------------------------------------------------- #
def list_themes():
    """返回 [(key, label, desc)]，按推荐顺序。"""
    order = ["warm", "editorial", "cinematic", "glass", "data", "olive"]
    return [(k, THEMES[k]["label"], THEMES[k]["desc"]) for k in order]


def load_theme():
    """读取已保存的用户偏好主题 key；未保存返回 None。"""
    try:
        if STATE_FILE.exists():
            return STATE_FILE.read_text(encoding="utf-8").strip() or None
    except OSError:
        pass
    return None


def save_theme(key: str) -> bool:
    """持久化用户偏好主题；非法 key 忽略并返回 False。"""
    if key not in THEMES:
        return False
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(key, encoding="utf-8")
        return True
    except OSError:
        return False


def resolve_theme(requested=None):
    """解析最终使用主题：请求参数 > 已存偏好 > 默认。"""
    key = requested or load_theme() or DEFAULT_THEME
    return key if key in THEMES else DEFAULT_THEME


# --------------------------------------------------------------------------- #
# 统一报告渲染（所有主题共用同一正文 HTML，仅替换 <style>）
# --------------------------------------------------------------------------- #
def render_report_html(analysis: dict, theme_key=None, kicker=None) -> str:
    """把 analysis 装配为单文件自包含 HTML，套用指定主题 CSS。

    analysis 结构见 build_report.generate_report。返回完整 HTML 字符串。
    正文 HTML 在所有主题间完全一致；引用 [N] 自动转可点击锚点，并做自包含校验。
    """
    key = resolve_theme(theme_key)
    theme = THEMES.get(key, THEMES[DEFAULT_THEME])
    if key not in THEMES:
        key = DEFAULT_THEME

    title = analysis.get("title", "购房分析报告")
    kicker = kicker or analysis.get("kicker", "")
    conclusion = analysis.get("conclusion", "")
    meta = analysis.get("meta", "")
    sections = analysis.get("sections", [])
    cites = analysis.get("cites", [])
    extra_css = analysis.get("extra_css", "")

    parts = ['<div class="flair"></div>']
    parts.append('<header class="doc-head">')
    parts.append(f'<h1>{title}</h1>')
    if kicker:
        parts.append(f'<p class="kicker">{kicker}</p>')
    parts.append('</header>')
    if conclusion:
        parts.append(f'<div class="conclusion">{conclusion}</div>')
    if meta:
        parts.append(f'<div class="meta">{meta}</div>')
    for sec in sections:
        parts.append(f'<section><h2>{sec.get("title", "")}</h2>'
                     f'{sec.get("html", "")}</section>')
    cites_html = ds.render_citations(cites)
    parts.append(f'<section class="refs"><h2>参考资料</h2>'
                 f'<ol class="cites">{cites_html}</ol></section>')
    body = "\n".join(parts)

    full = ("<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{title} · {theme['label']}</title>"
            f"<style>{BASE_REPORT_CSS}{theme['css']}{extra_css}</style></head>"
            f"<body><div class='doc'>{body}</div></body></html>")

    # [N] -> 可点击锚点 <a href="#cite-N" class="cite-ref">
    def repl_sup(m):
        nums = re.findall(r"\d+", m.group(1))
        return "".join(
            f'<a href="#cite-{n}" class="cite-ref">[{n}]</a>' for n in nums)
    full = re.sub(r"\[(\d+)(?:,\s*\d+)*\]", repl_sup, full)

    # 自包含校验
    leftover = re.findall(r"\[(\d+)\](?!\s*</a>)", full)
    assert not leftover, f"仍有未转换的引用标记: {leftover[:5]}"
    assert not re.findall(r"<sup>", full), "仍有未转换的 <sup> 引用"
    assert "__" not in full, "存在未替换占位符"
    ref_nums = set(re.findall(r'href="#cite-(\d+)"', full))
    id_nums = set(re.findall(r'id="cite-(\d+)"', full))
    missing = ref_nums - id_nums
    assert not missing, f"锚点缺失对应 id: {missing}"
    assert "<img" not in full, "不应有外链/本地图片"
    assert re.search(r'src="(?!#)', full) is None, "不应有非锚点 src"
    return full
