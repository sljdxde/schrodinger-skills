#!/usr/bin/env python3
"""Memory Forge package builder.

Reads a JSON payload (see references/output-templates.md) and renders a
self-contained, offline HTML learning package, or a Markdown version.

Pure Python standard library. No third-party packages. No external CDNs:
all CSS, JS and SVG are inlined so the file works with no network.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Inline SVG icon set (Lucide, stroke style) — keeps the package fully offline.
# Each value is the inner <svg> content; icon() wraps it in a consistent shell.
# ---------------------------------------------------------------------------
ICONS = {
    "sprout": '<path d="M14 9.536V7a4 4 0 0 1 4-4h1.5a.5.5 0 0 1 .5.5V5a4 4 0 0 1-4 4 4 4 0 0 0-4 4c0 2 1 3 1 5a5 5 0 0 1-1 3"/><path d="M4 9a5 5 0 0 1 8 4 5 5 0 0 1-8-4"/><path d="M5 21h14"/>',
    "snowflake": '<path d="m10 20-1.25-2.5L6 18"/><path d="M10 4 8.75 6.5 6 6"/><path d="m14 20 1.25-2.5L18 18"/><path d="m14 4 1.25 2.5L18 6"/><path d="m17 21-3-6h-4"/><path d="m17 3-3 6 1.5 3"/><path d="M2 12h6.5L10 9"/><path d="m20 10-1.5 2 1.5 2"/><path d="M22 12h-6.5L14 15"/><path d="m4 10 1.5 2L4 14"/><path d="m7 21 3-6-1.5-3"/><path d="m7 3 3 6h4"/>',
    "target": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    "sunrise": '<path d="M12 2v8"/><path d="m4.93 10.93 1.41 1.41"/><path d="M2 18h2"/><path d="M20 18h2"/><path d="m19.07 10.93-1.41 1.41"/><path d="M22 22H2"/><path d="m8 6 4-4 4 4"/><path d="M16 18a4 4 0 0 0-8 0"/>',
    "shield": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
    "trophy": '<path d="M10 14.66V17a1 1 0 0 1-1 1 2 2 0 0 0-2 2v2"/><path d="M14 14.66V17a1 1 0 0 0 1 1 2 2 0 0 1 2 2v2"/><path d="M17.916 10H19.5A2.5 2.5 0 0 0 22 7.5V5a1 1 0 0 0-1-1h-3"/><path d="M4 22h16"/><path d="M6 9a6 6 0 0 0 12 0V3a1 1 0 0 0-1-1H7a1 1 0 0 0-1 1z"/><path d="M6.084 10H4.5A2.5 2.5 0 0 1 2 7.5V5a1 1 0 0 1 1-1h3"/>',
    "pen-line": '<path d="M13 21h8"/><path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/>',
    "sparkles": '<path d="M11.017 2.814a1 1 0 0 1 1.966 0l1.051 5.558a2 2 0 0 0 1.594 1.594l5.558 1.051a1 1 0 0 1 0 1.966l-5.558 1.051a2 2 0 0 0-1.594 1.594l-1.051 5.558a1 1 0 0 1-1.966 0l-1.051-5.558a2 2 0 0 0-1.594-1.594l-5.558-1.051a1 1 0 0 1 0-1.966l5.558-1.051a2 2 0 0 0 1.594-1.594z"/><path d="M20 2v4"/><path d="M22 4h-4"/><circle cx="4" cy="20" r="2"/>',
    "scroll": '<path d="M19 17V5a2 2 0 0 0-2-2H4"/><path d="M8 21h12a2 2 0 0 0 2-2v-1a1 1 0 0 0-1-1H11a1 1 0 0 0-1 1v1a2 2 0 1 1-4 0V5a2 2 0 1 0-4 0v2a1 1 0 0 0 1 1h3"/>',
    "compass": '<circle cx="12" cy="12" r="10"/><path d="m16.24 7.76-1.804 5.411a2 2 0 0 1-1.265 1.265L7.76 16.24l1.804-5.411a2 2 0 0 1 1.265-1.265z"/>',
    "medal": '<path d="M7.21 15 2.66 7.14a2 2 0 0 1 .13-2.2L4.4 2.8A2 2 0 0 1 6 2h12a2 2 0 0 1 1.6.8l1.6 2.14a2 2 0 0 1 .14 2.2L16.79 15"/><path d="M11 12 5.12 2.2"/><path d="m13 12 5.88-9.8"/><path d="M8 7h8"/><circle cx="12" cy="17" r="5"/><path d="M12 18v-2h-.5"/>',
    "book": '<path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H19a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H6.5a1 1 0 0 1 0-5H20"/>',
    "award": '<path d="m15.477 12.89 1.515 8.526a.5.5 0 0 1-.81.47l-3.58-2.687a1 1 0 0 0-1.197 0l-3.586 2.686a.5.5 0 0 1-.81-.469l1.514-8.526"/><circle cx="12" cy="8" r="6"/>',
    "package": '<path d="M11 21.73a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73z"/><path d="M12 22V12"/><polyline points="3.29 7 12 12 20.71 7"/><path d="m7.5 4.27 9 5.15"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    "square": '<rect width="18" height="18" x="3" y="3" rx="2"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "x": '<path d="M18 6 6 18"/><path d="M6 6l12 12"/>',
    "flame": '<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/>',
}


def icon(name: str, size: int = 18, cls: str = "") -> str:
    """Render an inline SVG icon. Unknown names fall back to 'medal'."""
    inner = ICONS.get(name) or ICONS["medal"]
    c = f' class="{cls}"' if cls else ""
    return (
        f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" fill="none" '
        f'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
        f'stroke-linejoin="round"{c} aria-hidden="true">{inner}</svg>'
    )


# ---------------------------------------------------------------------------
# Mind-map layout (left-to-right tidy tree)
# ---------------------------------------------------------------------------
def layout_tree(nodes: list[dict]) -> tuple[dict, int, int]:
    """Return {node_id: (x, y)} plus svg width/height for a left->right tree."""
    by_id: dict[str, dict] = {n["id"]: n for n in nodes}
    children: dict[str, list[str]] = {}
    root = None
    for n in nodes:
        pid = n.get("parent")
        if pid is None or pid not in by_id:
            root = n["id"]
        else:
            children.setdefault(pid, []).append(n["id"])

    next_leaf = [0]
    ypos: dict[str, float] = {}

    def assign(nid: str, depth: int) -> int:
        kids = children.get(nid, [])
        if not kids:
            ypos[nid] = next_leaf[0]
            next_leaf[0] += 1
        else:
            for k in kids:
                assign(k, depth + 1)
            ys = [ypos[k] for k in kids]
            ypos[nid] = sum(ys) / len(ys)
        return depth

    max_depth = assign(root, 0) if root else 0
    leaves = next_leaf[0]
    margin_x, margin_y = 30, 30
    x_gap, y_gap = 200, 64
    node_w, node_h = 150, 40
    coords: dict[str, tuple[float, float]] = {}
    for nid, y in ypos.items():
        depth = 0
        p = by_id[nid].get("parent")
        while p is not None and p in by_id:
            depth += 1
            p = by_id[p].get("parent")
        x = margin_x + depth * x_gap
        yy = margin_y + y * y_gap + node_h / 2
        coords[nid] = (x, yy)
    width = margin_x * 2 + (max_depth + 1) * x_gap
    height = margin_y * 2 + max(1, leaves) * y_gap
    return coords, int(width), int(height)


def render_mindmap(mindmap: dict) -> str:
    nodes = mindmap.get("nodes", [])
    root_label = html.escape(str(mindmap.get("root", "主题")))
    if not nodes:
        return ""
    coords, w, h = layout_tree(nodes)
    by_id = {n["id"]: n for n in nodes}
    parts = [
        f'<svg viewBox="0 0 {w} {h}" width="100%" class="mindmap-svg" '
        f'role="img" aria-label="mind map">'
    ]
    # connectors first
    for nid, (x, y) in coords.items():
        n = by_id[nid]
        pid = n.get("parent")
        if pid in coords:
            px, py = coords[pid]
            parts.append(
                f'<line x1="{px + 150}" y1="{py}" x2="{x}" y2="{y}" '
                f'class="mm-link"/>'
            )
    # nodes
    node_w = 150
    for nid, (x, y) in coords.items():
        is_root = by_id[nid].get("parent") is None
        cls = "mm-node mm-root" if is_root else "mm-node"
        label = html.escape(str(by_id[nid].get("label", "")))
        parts.append(
            f'<g class="{cls}">'
            f'<rect x="{x}" y="{y - 20}" width="{node_w}" height="40" rx="8" '
            f'class="mm-rect"/>'
            f'<text x="{x + node_w / 2}" y="{y + 5}" class="mm-text">{label}</text>'
            f"</g>"
        )
    parts.append("</svg>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Concept card / quiz / review rendering
# ---------------------------------------------------------------------------
def render_cards(concepts: list[dict]) -> str:
    out = []
    for i, c in enumerate(concepts):
        term = html.escape(str(c.get("term", f"概念{i+1}")))
        front = html.escape(str(c.get("card_front", term)))
        back = html.escape(str(c.get("card_back", "")))
        plain = c.get("plain", [])
        if isinstance(plain, str):
            plain = [plain]
        plain_html = "".join(f"<li>{html.escape(str(p))}</li>" for p in plain)
        story = html.escape(str(c.get("story", "")))
        mnemonic = html.escape(str(c.get("mnemonic", "")))
        feynman = html.escape(str(c.get("feynman", "")))
        web_source = html.escape(str(c.get("web_source", "")))
        visual = c.get("visual", {}) or {}
        svg = ""
        if visual.get("type") == "svg" and visual.get("svg"):
            svg = str(visual.get("svg"))
        quiz_html = render_quiz(c.get("quiz"))
        story_block = (
            f'<div class="story"><span class="tag">类比/故事</span>{story}</div>'
            if story else ""
        )
        mnemonic_block = (
            f'<div class="mnemonic"><span class="tag">口诀</span>{mnemonic}</div>'
            if mnemonic else ""
        )
        web_block = (
            f'<div class="websource">{icon("link", 12)} <span>{web_source}</span></div>'
            if web_source else ""
        )
        feynman_block = (
            f'<div class="feynman"><span class="tag">费曼</span>{feynman}'
            f'<span class="feynman-check" role="button" tabindex="0" '
            f'onkeydown="if(event.key===\'Enter\'||event.key===\' \')this.click()">'
            f'<span class="fchk-box">{icon("square", 14)}</span>'
            f'<span class="fchk-label">我用大白话讲了一遍</span></span></div>'
            if feynman else ""
        )
        visual_block = f'<div class="visual">{svg}</div>' if svg else ""
        out.append(
            f"""
<div class="card" id="card-{i}">
  <div class="card-head"><span class="card-no">{i+1}</span><h3>{term}</h3></div>
  <div class="flip" onclick="this.classList.toggle('flipped')" role="button" tabindex="0"
       onkeydown="if(event.key==='Enter'||event.key===' ')this.classList.toggle('flipped')">
    <div class="flip-inner">
      <div class="flip-front"><div class="q-label">先想想</div><div class="q-text">{front}</div>
        <div class="flip-hint">点击翻看答案</div></div>
      <div class="flip-back"><div class="a-label">大白话</div><div class="a-text">{back}</div>
        {('<ul class="plain">' + plain_html + '</ul>') if plain_html else ''}
      </div>
    </div>
  </div>
  {story_block}
  {mnemonic_block}
  {visual_block}
  {feynman_block}
  {quiz_html}
  {web_block}
</div>"""
        )
    return "\n".join(out)


def render_quiz(quiz: dict | None) -> str:
    if not quiz:
        return ""
    qid = abs(hash(json.dumps(quiz, sort_keys=True))) % 100000
    q = html.escape(str(quiz.get("q", "")))
    explain = html.escape(str(quiz.get("explain", "")))
    qtype = quiz.get("type", "mc")
    body = ""
    if qtype == "fill":
        answer = html.escape(str(quiz.get("answer", "")))
        body = (
            f'<input type="text" class="fill-input" data-ans="{answer}" '
            f'placeholder="输入答案，再点检查"/>'
        )
    else:
        options = quiz.get("options", [])
        answer = int(quiz.get("answer", 0))
        opts = []
        for idx, opt in enumerate(options):
            opts.append(
                f'<label class="opt"><input type="radio" name="q{qid}" value="{idx}"/>'
                f'<span>{html.escape(str(opt))}</span></label>'
            )
        body = "".join(opts)
        body += f'<span class="correct-hide" data-ans="{answer}"></span>'
    return (
        f'<div class="quiz" data-qid="{qid}">'
        f'<div class="quiz-q"><span class="tag quiz-tag">自测</span>{q}</div>'
        f'<div class="quiz-body">{body}</div>'
        f'<button class="quiz-check" type="button">检查</button>'
        f'<div class="quiz-feedback" hidden></div>'
        f'<div class="quiz-explain" hidden>解析：{explain}</div>'
        f"</div>"
    )


def render_review(concepts: list[dict], review: list[dict]) -> str:
    rows = []
    # map concept_id -> term
    term_by_id = {c.get("id"): c.get("term", "") for c in concepts}
    for r in review:
        cid = r.get("concept_id", "")
        term = html.escape(str(r.get("term") or term_by_id.get(cid, cid)))
        ef = float(r.get("ef", 2.5))
        intervals = r.get("intervals")
        if not intervals:
            intervals = [1, 6, 16, 40]
        first = intervals[0] if intervals else 1
        btns = "".join(
            f'<button type="button" class="rate" data-q="{q}">{q}</button>'
            for q in range(0, 6)
        )
        rows.append(
            f"""<tr data-ef="{ef}" data-n="0" data-last="{first}">
  <td class="rv-term">{term}</td>
  <td class="rv-next">+{first} 天</td>
  <td class="rv-rate">评分 {btns}</td>
</tr>"""
        )
    return (
        '<table class="review"><thead><tr><th>概念</th><th>下次复习</th>'
        '<th>回忆后评分（0 完全想不起 → 5 完美）</th></tr></thead><tbody>'
        + "".join(rows)
        + "</tbody></table>"
    )


# ---------------------------------------------------------------------------
# Gamification: levels / XP / badges / streak (offline, localStorage)
# ---------------------------------------------------------------------------
def default_gamification() -> dict:
    return {
        "levels": [
            {"level": 1, "title": "初心学徒", "min_xp": 0},
            {"level": 2, "title": "识字书生", "min_xp": 50},
            {"level": 3, "title": "博闻少年", "min_xp": 130},
            {"level": 4, "title": "通晓学子", "min_xp": 260},
            {"level": 5, "title": "满腹经纶", "min_xp": 450},
            {"level": 6, "title": "博学鸿儒", "min_xp": 700},
            {"level": 7, "title": "融会宗师", "min_xp": 1000},
        ],
        "xp_rules": {
            "flip_card": 3,
            "quiz_correct": 12,
            "quiz_wrong": 3,
            "review_rate": 10,
            "feynman_done": 8,
        },
        "badges": [
            {"id": "first_pack", "name": "启程", "icon": "sprout",
             "desc": "打开学习包即得", "trigger": "on_generate"},
            {"id": "first_quiz", "name": "破冰", "icon": "snowflake",
             "desc": "首次答对自测", "trigger": "quiz_correct_first"},
            {"id": "all_quiz", "name": "火眼金睛", "icon": "target",
             "desc": "本包自测全对", "trigger": "quiz_all_correct"},
            {"id": "first_review", "name": "温故知新", "icon": "sunrise",
             "desc": "首次复习自评", "trigger": "review_rate_first"},
            {"id": "iron_will", "name": "百炼成钢", "icon": "shield",
             "desc": "复习自评累计 10 次", "trigger": "review_count>=10"},
            {"id": "master_all", "name": "融会贯通", "icon": "trophy",
             "desc": "所有概念自评 ≥4", "trigger": "all_review_ge4"},
            {"id": "feynman_master", "name": "费曼小能手", "icon": "pen-line",
             "desc": "完成全部费曼自述", "trigger": "feynman_all"},
            {"id": "streak3", "name": "三日之约", "icon": "flame",
             "desc": "连续 3 天学习", "trigger": "streak>=3"},
            {"id": "streak7", "name": "一周不辍", "icon": "sparkles",
             "desc": "连续 7 天学习", "trigger": "streak>=7"},
            {"id": "level5", "name": "满腹经纶", "icon": "scroll",
             "desc": "等级达到「满腹经纶」", "trigger": "level>=5"},
            {"id": "knowledge_hunter", "name": "知识猎人", "icon": "compass",
             "desc": "包内含联网深潜讲解", "trigger": "web_deepdive>=1"},
        ],
    }


def compute_gamification(data: dict) -> dict:
    """Merge user payload with defaults, drop unobtainable badges, count totals."""
    user = data.get("gamification") or {}
    gam = default_gamification()
    if user.get("levels"):
        gam["levels"] = user["levels"]
    if user.get("xp_rules"):
        gam["xp_rules"] = user["xp_rules"]
    if user.get("badges"):
        # 追加式合并：默认勋章保留，用户提供同 id 覆盖、新 id 追加
        by_id = {b["id"]: b for b in gam["badges"]}
        for b in user["badges"]:
            by_id[b["id"]] = b
        gam["badges"] = list(by_id.values())

    concepts = data.get("concepts", [])
    quiz_total = sum(1 for c in concepts if c.get("quiz"))
    feynman_total = sum(1 for c in concepts if c.get("feynman"))
    review_total = len(data.get("review_schedule", []))
    has_web = any(str(c.get("web_source", "")).strip() for c in concepts)

    filtered = []
    for b in gam["badges"]:
        t = b.get("trigger", "")
        if t == "web_deepdive>=1" and not has_web:
            continue
        if t == "feynman_all" and feynman_total == 0:
            continue
        if t == "quiz_all_correct" and quiz_total == 0:
            continue
        filtered.append(b)
    gam["badges"] = filtered
    gam["_totals"] = {
        "quiz_total": quiz_total,
        "feynman_total": feynman_total,
        "review_total": review_total,
        "has_web": has_web,
    }
    return gam


def render_gamification(data: dict, gam: dict) -> tuple[str, str, str]:
    """Return (honor_bar_html, hall_of_fame_html, pkg_json_string)."""
    totals = gam.get("_totals", {})
    first_level = gam["levels"][0]["title"] if gam["levels"] else "初心学徒"
    honor_bar = f"""
<div class="honor-bar" id="honorBar">
  <div class="hb-level"><span class="hb-badge">{icon('award', 18)}</span><span id="hbLevelName">{html.escape(first_level)}</span>
    <span class="hb-lv" id="hbLevelNo">Lv.1</span></div>
  <div class="hb-xp"><div class="hb-xp-track"><div class="hb-xp-fill" id="hbXpFill"></div></div>
    <span class="hb-xp-text" id="hbXpText">0 XP</span></div>
  <div class="hb-streak"><span id="hbStreakIcon">{icon('flame', 16)}</span><span id="hbStreak">0</span> 天连续</div>
</div>"""

    cards = []
    for b in gam["badges"]:
        bicon = icon(str(b.get("icon", "medal")), 34, "bc-svg")
        name = html.escape(str(b.get("name", "")))
        desc = html.escape(str(b.get("desc", "")))
        bid = html.escape(str(b.get("id", "")))
        cards.append(
            f'<div class="badge-card locked" id="bg-{bid}" data-badge="{bid}" '
            f'title="{desc}"><span class="bc-check">{icon("check", 14)}</span>'
            f'<div class="bc-icon">{bicon}</div>'
            f'<div class="bc-name">{name}</div><div class="bc-desc">{desc}</div></div>'
        )
    hall = (
        '<div class="hall"><div class="hall-head">' + icon("trophy", 20)
        + '<span class="hall-title">荣誉殿堂</span></div>'
        '<div class="badge-grid">' + "".join(cards) + "</div>"
        '<div class="hall-hint">悬停每枚勋章看「如何获得」；进度自动存在本学习包（浏览器本地）。</div>'
        "</div>"
    )
    pkg = {
        "levels": gam["levels"],
        "xp_rules": gam["xp_rules"],
        "badges": [
            {"id": b["id"], "name": b["name"], "icon": b["icon"],
             "desc": b["desc"], "trigger": b["trigger"]}
            for b in gam["badges"]
        ],
        "totals": totals,
        "storageKey": "pk_" + str(abs(hash(data.get("title", "pkg"))) % 100000),
    }
    pkg_json = json.dumps(pkg, ensure_ascii=False)
    return honor_bar, hall, pkg_json


# ---------------------------------------------------------------------------
# HTML document
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Theme system. Two intentional visual directions, both fully offline
# (system font stacks only — no web-font CDNs). Selected via --theme.
#   editorial : warm paper + ink + serif display headlines + soft shadow + gold
#   swiss     : near-white + ink + single IKB accent + all-sans + right angles
# ---------------------------------------------------------------------------
CSS_COMMON = """
:root{
  --fs-h1:clamp(2.1rem,1.2rem + 3.4vw,3.1rem);
  --fs-h2:clamp(1.25rem,1.05rem + .9vw,1.6rem);
  --fs-lead:1.18rem; --fs-base:1rem; --fs-sm:.875rem; --fs-xs:.78rem;
  --lh:1.65; --measure:66ch;
  --r-card:14px; --r-sm:10px; --r-pill:999px;
  --shadow-sm:0 1px 2px rgba(0,0,0,.04),0 2px 6px rgba(0,0,0,.04);
  --shadow-md:0 6px 20px rgba(0,0,0,.07),0 2px 6px rgba(0,0,0,.05);
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;line-height:var(--lh);font-size:var(--fs-base);
  -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
.wrap{max-width:940px;margin:0 auto;padding:40px 22px 100px}
.muted{color:var(--muted);font-size:var(--fs-sm);line-height:1.5}

/* masthead */
header.pkg{margin-bottom:8px}
header.pkg h1{margin:0 0 10px;font-size:var(--fs-h1);line-height:1.08;letter-spacing:-.015em}
header.pkg .meta{font-size:var(--fs-sm);line-height:1.5}
.offline{display:inline-flex;align-items:center;gap:6px;margin-top:14px;font-size:var(--fs-xs);font-weight:600}
.offline svg{display:block}

/* sections */
section{margin-bottom:30px}
section h2{margin:0 0 18px;font-size:var(--fs-h2);font-weight:700;display:flex;align-items:center;gap:11px}
section h2 .badge{font-size:var(--fs-xs);padding:3px 11px;border-radius:var(--r-pill);font-weight:700;letter-spacing:.04em}
.narrative p{font-size:var(--fs-lead);margin:0;line-height:1.7;max-width:var(--measure)}

/* honor strip */
.honor-bar{display:flex;flex-wrap:wrap;gap:16px;align-items:center;margin:0 0 30px;padding:16px 20px}
.hb-level{display:flex;align-items:center;gap:9px;font-weight:800;font-size:15px}
.hb-badge{display:flex;align-items:center;justify-content:center;width:34px;height:34px}
.hb-badge svg{display:block}
.hb-lv{padding:2px 10px;border-radius:var(--r-pill);font-size:var(--fs-xs);font-weight:700}
.hb-xp{flex:1;min-width:170px;display:flex;align-items:center;gap:10px}
.hb-xp-track{flex:1;height:11px;border-radius:var(--r-pill);overflow:hidden}
.hb-xp-fill{height:100%;width:0;transition:width .5s cubic-bezier(.16,1,.3,1)}
.hb-xp-text{font-size:var(--fs-xs);white-space:nowrap;font-weight:600}
.hb-streak{display:flex;align-items:center;gap:6px;font-weight:800;font-size:14px}
#hbStreakIcon{display:flex;align-items:center}
#hbStreakIcon svg{display:block}
.hall-head{display:flex;align-items:center;gap:9px;font-size:17px;font-weight:800;margin-bottom:14px}
.hall-head svg{display:block}
.badge-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(118px,1fr));gap:14px}
.badge-card{position:relative;cursor:default;transition:transform .22s,box-shadow .22s,border-color .22s}
.bc-svg{display:block}
.bc-name{font-weight:700;font-size:14px;margin-top:10px}
.bc-desc{font-size:11px;margin-top:4px;line-height:1.4;color:var(--muted)}
.badge-card.just-unlocked{animation:pop .55s cubic-bezier(.34,1.4,.5,1)}
@keyframes pop{0%{transform:scale(.75);opacity:0}60%{transform:scale(1.1);opacity:1}100%{transform:scale(1)}}
.hall-hint{font-size:var(--fs-xs);margin-top:16px;color:var(--muted)}

/* concept card */
.card{margin-bottom:20px}
.card-head{display:flex;align-items:center;gap:11px;margin-bottom:13px}
.card-no{width:27px;height:27px;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:800}
.card-head h3{margin:0;font-size:17px;font-weight:800;letter-spacing:-.01em}

/* flip */
.flip{perspective:1200px;cursor:pointer;outline:none}
.flip-inner{position:relative;transition:transform .55s cubic-bezier(.4,0,.2,1);transform-style:preserve-3d;min-height:120px}
.flip.flipped .flip-inner{transform:rotateY(180deg)}
.flip-front,.flip-back{position:absolute;inset:0;backface-visibility:hidden;-webkit-backface-visibility:hidden;padding:17px 19px}
.flip-front{overflow:hidden}
.flip-back{transform:rotateY(180deg);overflow:auto}
.q-label,.a-label{font-size:11px;text-transform:uppercase;letter-spacing:.08em;font-weight:700;color:var(--muted)}
.q-text{font-size:17px;font-weight:700;margin-top:5px;line-height:1.5}
.flip-hint{position:absolute;bottom:11px;right:14px;font-size:11px;color:var(--muted)}
.a-text{font-size:15px;margin-top:5px;line-height:1.6}
.plain{margin:11px 0 0;padding-left:19px}
.plain li{margin:4px 0}
.tag{display:inline-block;font-size:11px;padding:2px 8px;margin-right:7px;font-weight:700}
.story,.mnemonic,.feynman{margin-top:11px;padding:10px 13px;font-size:14px;line-height:1.55}
.websource{margin-top:9px;font-size:12px;display:flex;align-items:center;gap:5px}
.websource svg{flex-shrink:0;display:block}
.visual{margin-top:13px}
.visual svg{max-width:100%;height:auto}
.mindmap-svg{width:100%;height:auto}
.mm-link{stroke-width:1.5}
.mm-rect{stroke-width:1.5}
.mm-text{font-size:13px;text-anchor:middle;font-family:inherit}
.mm-root .mm-text{font-weight:700}
.mm-link{stroke:var(--line-2)}

/* quiz */
.quiz{margin-top:13px;padding:14px 15px}
.quiz-q{font-size:14px;font-weight:700;margin-bottom:9px}
.opt{display:block;margin:5px 0;cursor:pointer;font-size:14px}
.opt input{margin-right:7px}
.fill-input{padding:8px 11px;width:220px;max-width:100%;font-size:14px}
.quiz-check{margin-top:9px;color:#fff;border:0;padding:8px 18px;cursor:pointer;font-size:13px;font-weight:700;transition:background .15s,transform .1s}
.quiz-check:active{transform:scale(.97)}
.quiz-feedback{margin-top:9px;font-weight:700;font-size:14px}
.quiz-feedback.ok{color:var(--good)} .quiz-feedback.no{color:var(--bad)}
.quiz-explain{margin-top:7px;font-size:13px;color:var(--muted);line-height:1.5}

/* review */
.review{width:100%;border-collapse:collapse;font-size:14px}
.review th,.review td{border-bottom:1px solid var(--line);padding:11px 9px;text-align:left}
.review th{font-size:12px;color:var(--muted);font-weight:700;letter-spacing:.03em}
.review tbody tr:last-child td{border-bottom:0}
.rate{margin:0 2px;width:31px;height:31px;background:#fff;cursor:pointer;font-size:13px;font-weight:600;color:var(--muted);transition:all .12s}
.rv-next{font-weight:800}
.rv-term{font-weight:600}
footer.pkg{text-align:center;font-size:var(--fs-xs);margin-top:14px;line-height:1.6;color:var(--muted)}

/* feynman check */
.feynman-check{margin-top:10px;display:inline-flex;align-items:center;gap:7px;font-size:13px;font-weight:600;cursor:pointer;user-select:none;transition:all .15s}
.feynman-check .fchk-box{display:flex;align-items:center}
.feynman-check.done{}

/* toast */
.toast{position:fixed;left:50%;bottom:32px;transform:translateX(-50%) translateY(24px);
  color:#fff;padding:13px 20px;border-radius:14px;font-size:14px;font-weight:600;
  display:flex;align-items:center;gap:9px;opacity:0;pointer-events:none;transition:opacity .3s,transform .3s;z-index:50;box-shadow:var(--shadow-md)}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
.toast .t-icon{display:flex;align-items:center}
.toast .t-icon svg{display:block}

@media (max-width:560px){
  .wrap{padding:24px 14px 72px}
  .badge-grid{grid-template-columns:repeat(auto-fill,minmax(96px,1fr));gap:10px}
  .honor-bar{gap:12px;padding:14px}
}
"""

CSS_EDITORIAL = """
:root{
  --paper:#f4f1ea; --paper-2:#ece6d8; --card:#fbf9f2;
  --ink:#1d1a14; --ink-2:#2c271e; --muted:#7a6f5b;
  --line:#ddd4c0; --line-2:#cdc1a6;
  --brand:#9a3b22; --brand-soft:#f3e7df; --brand-deep:#6f2a16;
  --accent:#a8442a; --gold:#bd8a2c;
  --good:#3f7d4f; --bad:#bf3b30; --warn:#c5791f;
  --serif:"Iowan Old Style",Georgia,"Times New Roman","Songti SC","Noto Serif SC","Source Han Serif SC",serif;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei","Hiragino Sans GB",sans-serif;
  --mono:"SF Mono",ui-monospace,"JetBrains Mono",Menlo,Consolas,monospace;
}
body{background:var(--paper);color:var(--ink);font-family:var(--sans)}
header.pkg h1{font-family:var(--serif);font-weight:600;color:var(--ink)}
header.pkg .meta{color:var(--muted)}
header.pkg:after{content:"";display:block;width:54px;height:3px;background:var(--accent);margin-top:16px}
.offline{border:1px solid var(--line-2);color:var(--muted);padding:4px 11px;border-radius:var(--r-pill);background:var(--card)}
.offline svg{display:block}

section{background:var(--card);border:1px solid var(--line);border-radius:var(--r-card);padding:24px 26px;box-shadow:var(--shadow-sm)}
section h2{font-family:var(--serif)}
section h2 .badge{background:var(--brand-soft);color:var(--brand)}

.honor-bar{background:var(--paper-2);border:1px solid var(--line);border-radius:var(--r-card);box-shadow:var(--shadow-sm)}
.hb-badge{background:var(--brand);color:#fff;border-radius:9px}
.hb-lv{background:var(--card);border:1px solid var(--line-2);color:var(--ink-2)}
.hb-xp-track{background:var(--line)}
.hb-xp-fill{background:linear-gradient(90deg,#e9c46a,#bd8a2c);box-shadow:0 0 10px rgba(189,138,44,.4)}
.hb-streak{color:var(--brand)}
#hbStreakIcon{color:var(--brand)}
.hall-head{color:var(--ink)}
.hall-head svg{color:var(--gold)}
.badge-card{border:1px solid var(--line);border-radius:var(--r-card);padding:16px 10px;text-align:center;background:var(--card)}
.badge-card:hover{transform:translateY(-3px);box-shadow:var(--shadow-md)}
.bc-icon{display:flex;align-items:center;justify-content:center;width:58px;height:58px;margin:0 auto;border-radius:50%;background:var(--brand-soft);color:var(--brand);transition:all .25s}
.badge-card.locked{filter:grayscale(.9);opacity:.4}
.badge-card.locked .bc-icon{background:var(--paper-2);color:var(--muted)}
.badge-card.unlocked{border-color:var(--gold);box-shadow:var(--shadow-md)}
.badge-card.unlocked .bc-icon{background:linear-gradient(135deg,#e9c46a,#bd8a2c);color:#fff;box-shadow:0 4px 14px rgba(189,138,44,.45)}
.bc-check{position:absolute;top:8px;right:10px;display:none;color:var(--good)}
.badge-card.unlocked .bc-check{display:flex}

.card{border:1px solid var(--line);border-radius:var(--r-card);padding:18px 20px;background:var(--card);box-shadow:var(--shadow-sm);transition:box-shadow .2s}
.card:hover{box-shadow:var(--shadow-md)}
.card-no{background:var(--brand);color:#fff;border-radius:9px}
.flip-front,.flip-back{border:1px solid var(--line);border-radius:var(--r-sm)}
.flip-front{background:var(--brand-soft)}
.flip-back{border-color:var(--brand);box-shadow:inset 0 0 0 1px var(--brand-soft)}
.tag{background:var(--brand-soft);color:var(--brand)}
.story{background:#faf3e6;border-left:3px solid var(--gold)}
.mnemonic{background:#eef5f0;border-left:3px solid var(--good)}
.feynman{background:#f1f7f2;border-left:3px solid var(--good)}
.mindmap-svg{background:var(--paper-2);border:1px solid var(--line);border-radius:var(--r-sm)}
.mm-rect{fill:var(--card);stroke:var(--brand)}
.mm-root .mm-rect{fill:var(--brand);stroke:var(--brand)}
.mm-text{fill:var(--ink)}
.mm-root .mm-text{fill:#fff}
.quiz{background:var(--brand-soft);border:1px dashed var(--line-2);border-radius:var(--r-sm)}
.quiz-tag{background:#f0e2da;color:var(--brand)}
.opt input{accent-color:var(--brand)}
.fill-input{border:1px solid var(--line);border-radius:8px;transition:border-color .15s,box-shadow .15s}
.fill-input:focus{outline:none;border-color:var(--brand);box-shadow:0 0 0 3px var(--brand-soft)}
.quiz-check{background:var(--brand)}
.quiz-check:hover{background:var(--ink-2)}
.rate{border:1px solid var(--line);border-radius:8px}
.rate:hover{background:var(--brand);color:#fff;border-color:var(--brand)}
.rv-next{color:var(--brand)}
.feynman-check{background:var(--card);border:1.5px solid var(--good);color:#1f6b39;border-radius:9px;padding:6px 12px}
.feynman-check:hover{background:#f1f7f2}
.feynman-check.done{background:var(--good);border-color:var(--good);color:#fff}
.toast{background:var(--ink)}
.toast .t-icon{color:var(--gold)}
"""

CSS_SWISS = """
:root{
  --paper:#fafaf8; --paper-2:#f0f0ee; --card:#ffffff;
  --ink:#0f0f0f; --ink-2:#2a2a29; --muted:#6f6f6c;
  --line:#d8d8d4; --line-2:#bcbcb6;
  --brand:var(--accent); --accent:#002FA7; --brand-soft:#eef0f6; --brand-deep:#001f6e;
  --good:#0a7d4f; --bad:#c0322b; --warn:#c5791f;
  --sans:"Helvetica Neue",Helvetica,"Arial","Inter","PingFang SC","Microsoft YaHei",system-ui,sans-serif;
  --mono:"SF Mono",ui-monospace,"JetBrains Mono",Menlo,Consolas,monospace;
}
body{background:var(--paper);color:var(--ink);font-family:var(--sans)}
header.pkg h1{font-family:var(--sans);font-weight:200;color:var(--ink);letter-spacing:-.02em}
header.pkg .meta{color:var(--muted);font-family:var(--mono)}
header.pkg:after{content:"";display:block;width:64px;height:6px;background:var(--accent);margin-top:18px}
.offline{border:1px solid var(--line-2);color:var(--muted);padding:4px 11px;font-family:var(--mono);text-transform:uppercase;letter-spacing:.08em}
.offline svg{display:block}

section{border-top:2px solid var(--ink);padding:26px 0 6px;margin-bottom:30px}
section:first-of-type{border-top:0;padding-top:0}
section h2{font-family:var(--sans);font-weight:600;text-transform:uppercase;letter-spacing:.04em}
section h2 .badge{background:var(--accent);color:#fff;border-radius:0}

.honor-bar{border-top:1px solid var(--ink);border-bottom:1px solid var(--ink);padding:18px 4px;gap:20px}
.hb-badge{background:var(--ink);color:#fff}
.hb-lv{background:#fff;border:1px solid var(--ink);color:var(--ink)}
.hb-xp-track{background:#fff;border:1px solid var(--line-2)}
.hb-xp-fill{background:var(--accent)}
.hb-streak{color:var(--ink)}
#hbStreakIcon{color:var(--accent)}
.hall-head{color:var(--ink);text-transform:uppercase;letter-spacing:.04em;font-weight:600}
.hall-head svg{color:var(--accent)}
.badge-card{border:1px solid var(--line);border-radius:0;padding:18px 8px 14px;text-align:center;background:#fff}
.badge-card:hover{transform:none;box-shadow:none;border-color:var(--ink)}
.bc-icon{display:flex;align-items:center;justify-content:center;width:46px;height:46px;margin:0 auto;color:var(--ink)}
.badge-card.locked{opacity:.34;filter:none}
.badge-card.locked .bc-icon{color:var(--muted)}
.badge-card.unlocked{border:2px solid var(--accent)}
.badge-card.unlocked .bc-icon{color:var(--accent)}
.bc-check{position:absolute;top:7px;right:9px;display:none;color:var(--accent)}
.badge-card.unlocked .bc-check{display:flex}
.badge-card.just-unlocked{animation:pop .5s cubic-bezier(.2,.8,.2,1)}

.card{border:0;border-bottom:1px solid var(--line);border-radius:0;padding:0 0 28px;background:transparent;margin-bottom:30px}
.card:hover{box-shadow:none}
.card-no{background:var(--accent);color:#fff;width:26px;height:26px;border-radius:0}
.flip-front,.flip-back{border:1px solid var(--line);border-radius:0}
.flip-front{background:var(--paper-2)}
.flip-back{border-color:var(--accent);box-shadow:inset 2px 0 0 var(--accent)}
.tag{background:transparent;border:1px solid var(--line-2);color:var(--ink);border-radius:0;text-transform:uppercase;letter-spacing:.05em;font-family:var(--mono)}
.story,.mnemonic,.feynman{background:transparent;border-left:2px solid var(--accent);border-radius:0;padding:2px 0 2px 13px}
.mnemonic{border-left-color:var(--good)}
.feynman{border-left-color:var(--good)}
.mindmap-svg{border:1px solid var(--line);border-radius:0;background:#fff}
.mm-rect{fill:#fff;stroke:var(--ink)}
.mm-root .mm-rect{fill:var(--accent);stroke:var(--accent)}
.mm-text{fill:var(--ink)}
.mm-root .mm-text{fill:#fff}
.quiz{border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:0;background:transparent}
.quiz-tag{background:var(--accent);color:#fff}
.opt input{accent-color:var(--accent)}
.fill-input{border:1px solid var(--line-2);border-radius:0;transition:border-color .15s,box-shadow .15s}
.fill-input:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 2px rgba(0,47,167,.15)}
.quiz-check{background:var(--accent);border-radius:0}
.quiz-check:hover{background:var(--ink)}
.rate{border:1px solid var(--line-2);border-radius:0}
.rate:hover{background:var(--accent);color:#fff;border-color:var(--accent)}
.rv-next{color:var(--accent)}
.feynman-check{background:#fff;border:1.5px solid var(--good);color:#0a7d4f;border-radius:0;padding:6px 12px}
.feynman-check:hover{background:#f3f8f5}
.feynman-check.done{background:var(--good);border-color:var(--good);color:#fff}
.toast{background:var(--ink);border-radius:0}
.toast .t-icon{color:var(--accent)}
@media (max-width:560px){
  section{border-top-width:2px}
}
"""

CSS = CSS_COMMON + CSS_EDITORIAL  # default; build_html picks per --theme


JS = r"""
function checkQuiz(btn){
  var q=btn.closest('.quiz');
  var fb=q.querySelector('.quiz-feedback');
  var ex=q.querySelector('.quiz-explain');
  var ok=false;
  var fill=q.querySelector('.fill-input');
  if(fill){
    ok = fill.value.trim()===fill.dataset.ans.trim();
  }else{
    var sel=q.querySelector('input[type=radio]:checked');
    var ans=parseInt(q.querySelector('.correct-hide').dataset.ans,10);
    if(!sel){fb.textContent='请先选择一个答案';fb.className='quiz-feedback no';fb.hidden=false;return;}
    ok = parseInt(sel.value,10)===ans;
  }
  fb.innerHTML = (ok?iconSvg('check',16)+'<span class="fb-ic">答对了！</span>'
                    :iconSvg('x',16)+'<span class="fb-ic">再想想</span>');
  fb.className = 'quiz-feedback '+(ok?'ok':'no');
  fb.hidden=false; ex.hidden=false;
  if(q.dataset.answered!=='1'){ q.dataset.answered='1';
    S.quizAnswered++; if(ok) S.quizCorrect++;
    grantXP(ok?PKG.xp_rules.quiz_correct:PKG.xp_rules.quiz_wrong);
    bumpStreak(); afterAction();
  }
}
function sm2(ef,n,q,last){
  ef = ef + (0.1 - (5-q)*(0.08 + (5-q)*0.02));
  if(ef<1.3) ef=1.3;
  if(q<3){return {ef:ef,n:0,interval:1};}
  n=n+1;
  var interval;
  if(n===1) interval=1;
  else if(n===2) interval=6;
  else interval=Math.round(last*ef);
  return {ef:ef,n:n,interval:interval};
}
function rate(btn){
  var row=btn.closest('tr');
  var q=parseInt(btn.dataset.q,10);
  var ef=parseFloat(row.dataset.ef);
  var n=parseInt(row.dataset.n,10);
  var last=parseFloat(row.dataset.last);
  var r=sm2(ef,n,q,last);
  row.dataset.ef=r.ef; row.dataset.n=r.n; row.dataset.last=r.interval;
  row.querySelector('.rv-next').textContent='+'+r.interval+' 天';
  if(row.dataset.rated!=='1'){ row.dataset.rated='1';
    if(q>=4) row.dataset.ge4='1';
    S.reviewCount++; grantXP(PKG.xp_rules.review_rate); bumpStreak(); afterAction();
  }
}

/* ===== Gamification engine ===== */
const PKG = __PKG__;
const ICONS = __ICONS__;
function iconSvg(name,size,cls){var inner=ICONS[name]||ICONS['medal'];return '<svg viewBox="0 0 24 24" width="'+(size||18)+'" height="'+(size||18)+'" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"'+(cls?(' class="'+cls+'"'):'')+'>'+inner+'</svg>';}
var LS_KEY = 'mf_' + (PKG.storageKey||'default');
function lsGet(){ try{return JSON.parse(localStorage.getItem(LS_KEY))||{};}catch(e){return {};} }
function lsSet(s){ try{localStorage.setItem(LS_KEY,JSON.stringify(s));}catch(e){} }
var S = Object.assign({xp:0,badges:[],reviewCount:0,quizCorrect:0,quizAnswered:0,feynmanDone:0,streak:0,lastDay:null,flips:{}}, lsGet());

function todayStr(){var d=new Date();return d.getFullYear()+'-'+(d.getMonth()+1)+'-'+d.getDate();}
function ydayStr(){var d=new Date(Date.now()-86400000);return d.getFullYear()+'-'+(d.getMonth()+1)+'-'+d.getDate();}
function bumpStreak(){var t=todayStr(); if(S.lastDay===t)return; if(S.lastDay===ydayStr())S.streak+=1; else S.streak=1; S.lastDay=t;}

function levelFor(xp){var lv=PKG.levels[0];for(var i=0;i<PKG.levels.length;i++){if(xp>=PKG.levels[i].min_xp)lv=PKG.levels[i];}return lv;}
function nextLevel(xp){for(var i=0;i<PKG.levels.length;i++){if(xp<PKG.levels[i].min_xp)return PKG.levels[i];}return null;}
function allReviewedGe4(){ if(!PKG.totals.review_total)return false;
  var rows=document.querySelectorAll('.review tr[data-ef]'); if(!rows.length)return false;
  for(var i=0;i<rows.length;i++){ if(rows[i].dataset.ge4!=='1')return false; } return true; }

function evaluateBadges(){
  var newly=[];
  PKG.badges.forEach(function(b){
    if(S.badges.indexOf(b.id)>=0)return;
    var t=b.trigger, ok=false;
    if(t==='on_generate') ok=true;
    else if(t==='quiz_correct_first') ok=S.quizCorrect>=1;
    else if(t==='quiz_all_correct') ok=(PKG.totals.quiz_total>0 && S.quizAnswered>=PKG.totals.quiz_total && S.quizCorrect===PKG.totals.quiz_total);
    else if(t==='review_rate_first') ok=S.reviewCount>=1;
    else if(t==='all_review_ge4') ok=allReviewedGe4();
    else if(t==='feynman_all') ok=(PKG.totals.feynman_total>0 && S.feynmanDone>=PKG.totals.feynman_total);
    else if(t.indexOf('>=')>=0){var m=t.match(/^(\w+)>=(\d+)$/); if(m){var key=m[1],val=+m[2];var map={review_count:S.reviewCount,streak:S.streak,level:levelFor(S.xp).level};ok=(map[key]||0)>=val;}}
    if(ok){S.badges.push(b.id);newly.push(b);}
  });
  return newly;
}
function renderHonor(){
  var lv=levelFor(S.xp), nxt=nextLevel(S.xp);
  var n=document.getElementById('hbLevelName'); if(n)n.textContent=lv.title;
  var no=document.getElementById('hbLevelNo'); if(no)no.textContent='Lv.'+lv.level;
  var pct=100; if(nxt){var span=nxt.min_xp-lv.min_xp; pct=Math.max(0,Math.min(100,Math.round((S.xp-lv.min_xp)/span*100)));}
  var f=document.getElementById('hbXpFill'); if(f)f.style.width=pct+'%';
  var xt=document.getElementById('hbXpText'); if(xt)xt.textContent=S.xp+' XP'+(nxt?(' / '+nxt.min_xp):' · 满级');
  var st=document.getElementById('hbStreak'); if(st)st.textContent=S.streak;
  var si=document.getElementById('hbStreakIcon'); if(si){si.innerHTML=iconSvg('flame',16); si.style.opacity=S.streak>0?'1':'0.35';}
}
function renderHall(){
  PKG.badges.forEach(function(b){
    var el=document.getElementById('bg-'+b.id); if(!el)return;
    if(S.badges.indexOf(b.id)>=0){el.classList.add('unlocked');el.classList.remove('locked');}
    else{el.classList.add('locked');el.classList.remove('unlocked');}
  });
}
function toast(msg,icon){
  var t=document.getElementById('mfToast');
  if(!t){t=document.createElement('div');t.id='mfToast';t.className='toast';document.body.appendChild(t);}
  t.innerHTML='<span class="t-icon">'+iconSvg(icon||'medal',16)+'</span>'+msg;
  t.classList.add('show'); clearTimeout(t._tm); t._tm=setTimeout(function(){t.classList.remove('show');},2600);
}
function grantXP(n){ S.xp+=n; }
function afterAction(){
  var beforeLv=levelFor(S.xp).level;
  var newly=evaluateBadges();
  lsSet(S); renderHonor(); renderHall();
  var afterLv=levelFor(S.xp).level;
  if(afterLv>beforeLv) toast('升级！'+levelFor(S.xp).title,'sparkles');
  newly.forEach(function(b){
    var el=document.getElementById('bg-'+b.id);
    if(el){el.classList.add('just-unlocked');setTimeout(function(){el.classList.remove('just-unlocked');},600);}
    toast('解锁勋章：'+b.name, b.icon);
  });
}
function onFlip(flipEl){
  var card=flipEl.closest('.card'); if(!card)return;
  var idx=card.id; if(S.flips[idx])return; S.flips[idx]=1;
  grantXP(PKG.xp_rules.flip_card); bumpStreak(); afterAction();
}
function onFeynman(fc){
  if(fc.classList.contains('done'))return;
  fc.classList.add('done');
  var box=fc.querySelector('.fchk-box'); if(box)box.innerHTML=iconSvg('check',14);
  var lab=fc.querySelector('.fchk-label'); if(lab)lab.textContent='已复述';
  S.feynmanDone++; grantXP(PKG.xp_rules.feynman_done); bumpStreak(); afterAction();
}
document.addEventListener('click',function(e){
  if(e.target.classList.contains('quiz-check')) checkQuiz(e.target);
  if(e.target.classList.contains('rate')) rate(e.target);
  var flip=e.target.closest('.flip'); if(flip) onFlip(flip);
  var fc=e.target.closest('.feynman-check'); if(fc) onFeynman(fc);
});
(function init(){
  evaluateBadges(); lsSet(S); renderHonor(); renderHall();
})();
"""

PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
<div class="wrap">
<header class="pkg">
  <h1>{title}</h1>
  <div class="meta">来源：{source} ｜ 受众：{audience} ｜ 生成：{generated_at}</div>
  <div class="offline">{offline_icon} 离线自包含 · 无需联网</div>
</header>

{honor_bar}

<section>
  <h2><span class="badge">养成</span> 荣誉殿堂</h2>
  {hall_of_fame}
</section>

<section>
  <h2><span class="badge">总览</span> 一句话故事</h2>
  <div class="narrative"><p>{narrative}</p></div>
</section>

<section>
  <h2><span class="badge">结构</span> 知识脑图</h2>
  {mindmap}
</section>

<section>
  <h2><span class="badge">记忆</span> 知识卡片（点击翻转）</h2>
  {cards}
</section>

<section>
  <h2><span class="badge">测验</span> 自测区</h2>
  <p class="muted">先答再点「检查」，看解析。错的回对应卡片复习。</p>
  {quizzes_intro}
</section>

<section>
  <h2><span class="badge">复习</span> 艾宾浩斯 / SM-2 复习计划</h2>
  <p class="muted">以今天为 D0。每次回忆后给自己 0–5 分，系统按 SM-2 即时算出下次间隔。</p>
  {review}
</section>

<footer class="pkg">由 Memory Forge 锻造 · 复习比重新读有效得多（测试效应）</footer>
</div>
<script>{js}</script>
</body>
</html>"""


def build_html(data: dict, theme: str = "editorial") -> str:
    title = html.escape(str(data.get("title", "学习包")))
    source = html.escape(str(data.get("source", "未注明")))
    audience = html.escape(str(data.get("audience", "通用")))
    generated_at = html.escape(str(data.get("generated_at", "")))
    narrative_obj = data.get("narrative", {}) or {}
    narrative = html.escape(
        str(narrative_obj.get("body", narrative_obj.get("title", "")))
    )
    concepts = data.get("concepts", [])
    cards_html = render_cards(concepts)
    mindmap_html = render_mindmap(data.get("mindmap", {}) or {})
    review_html = render_review(concepts, data.get("review_schedule", []))
    gam = compute_gamification(data)
    honor_bar, hall_of_fame, pkg_json = render_gamification(data, gam)
    # quizzes section: re-render quiz blocks collected (already inside cards);
    # provide a lightweight note that quizzes live on each card.
    quizzes_intro = (
        "下面每张卡片底部都带自测题；这里汇总提示：优先用「填空/自己举例」的方式回忆，"
        "比被动读记得牢（生成效应）。"
    )
    return PAGE.format(
        title=title,
        source=source,
        audience=audience,
        generated_at=generated_at,
        narrative=narrative,
        mindmap=mindmap_html or "<p class='muted'>（无脑图数据）</p>",
        cards=cards_html or "<p class='muted'>（无概念数据）</p>",
        quizzes_intro=quizzes_intro,
        review=review_html or "<p class='muted'>（无复习计划）</p>",
        honor_bar=honor_bar,
        hall_of_fame=hall_of_fame,
        offline_icon=icon("package", 12),
        js=JS.replace("__PKG__", pkg_json).replace("__ICONS__", json.dumps(ICONS, ensure_ascii=False)),
        css=(CSS_COMMON + CSS_SWISS) if theme == "swiss" else (CSS_COMMON + CSS_EDITORIAL),
    )


def build_md(data: dict) -> str:
    lines = [f"# {data.get('title', '学习包')}", ""]
    lines.append(f"- 来源：{data.get('source', '未注明')}")
    lines.append(f"- 受众：{data.get('audience', '通用')}")
    lines.append(f"- 生成：{data.get('generated_at', '')}")
    lines.append("")
    nar = data.get("narrative", {}) or {}
    if nar.get("body"):
        lines.append("## 一句话故事")
        lines.append(nar["body"])
        lines.append("")
    mm = data.get("mindmap", {}) or {}
    if mm.get("nodes"):
        lines.append("## 知识脑图")
        by_id = {n["id"]: n for n in mm["nodes"]}
        for n in mm["nodes"]:
            depth = 0
            p = n.get("parent")
            while p in by_id:
                depth += 1
                p = by_id[p].get("parent")
            lines.append(f"{'  ' * depth}- {n.get('label', '')}")
        lines.append("")
    for i, c in enumerate(data.get("concepts", []), 1):
        lines.append(f"## {i}. {c.get('term', '')}")
        lines.append(f"**先想想：** {c.get('card_front', '')}")
        lines.append(f"**大白话：** {c.get('card_back', '')}")
        plain = c.get("plain", [])
        if isinstance(plain, str):
            plain = [plain]
        for p in plain:
            lines.append(f"- {p}")
        if c.get("story"):
            lines.append(f"**类比/故事：** {c.get('story')}")
        if c.get("mnemonic"):
            lines.append(f"**口诀：** {c.get('mnemonic')}")
        quiz = c.get("quiz")
        if quiz:
            lines.append(f"**自测：** {quiz.get('q')}")
            if quiz.get("type") == "fill":
                lines.append(f"答案：{quiz.get('answer')}")
            else:
                for idx, opt in enumerate(quiz.get("options", [])):
                    mark = "✓" if idx == quiz.get("answer") else " "
                    lines.append(f"  {mark} {opt}")
            lines.append(f"解析：{quiz.get('explain', '')}")
        if c.get("feynman"):
            lines.append(f"**费曼：** {c.get('feynman')}")
        if c.get("web_source"):
            lines.append(f"> 来源：{c.get('web_source')}")
        lines.append("")
    rev = data.get("review_schedule", [])
    if rev:
        lines.append("## 复习计划（SM-2，以今天为 D0）")
        lines.append("| 概念 | 首次复习 |")
        lines.append("|---|---|")
        for r in rev:
            iv = r.get("intervals") or [1]
            lines.append(f"| {r.get('term', r.get('concept_id'))} | +{iv[0]} 天 |")
        lines.append("")

    # 荣誉体系（养成）
    gam = compute_gamification(data)
    if gam.get("levels"):
        lines.append("## 荣誉体系（养成）")
        lines.append("**等级（累计 XP）：**")
        for lv in gam["levels"]:
            lines.append(f"- Lv.{lv['level']} {lv['title']}（{lv['min_xp']} XP 起）")
        lines.append("")
        if gam.get("badges"):
            lines.append("**勋章（可解锁）：**")
            for b in gam["badges"]:
                lines.append(f"- **{b['name']}**：{b['desc']}")
            lines.append("")
        lines.append("> 进度自动存在导出的 HTML 学习包（浏览器本地），翻卡 / 自测 / 复习 / 费曼复述都会攒经验、点亮勋章。")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Render a Memory Forge learning package.")
    ap.add_argument("--in", dest="infile", required=True, help="Input JSON payload.")
    ap.add_argument("--out", dest="outfile", help="Output file path.")
    ap.add_argument("--format", dest="fmt", choices=["html", "md"], default="html",
                    help="Output format (default html).")
    ap.add_argument("--theme", dest="theme", choices=["editorial", "swiss"],
                    default="editorial",
                    help="Visual theme for HTML output: editorial (warm magazine) "
                         "or swiss (Swiss International / right angles). Default editorial.")
    args = ap.parse_args()

    payload = json.loads(Path(args.infile).read_text(encoding="utf-8"))
    if args.fmt == "md":
        content = build_md(payload)
        ext = ".md"
    else:
        content = build_html(payload, theme=args.theme)
        ext = ".html"

    out = args.outfile or (Path(args.infile).stem + "-package" + ext)
    Path(out).write_text(content, encoding="utf-8")
    print(f"wrote {out} ({len(content)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
