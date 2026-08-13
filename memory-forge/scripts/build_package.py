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
    "lightbulb": '<path d="M9 18h6"/><path d="M10 22h4"/><path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0 0 18 8 6 6 0 0 0 6 8c0 1 .23 2.23 1.5 3.5A4.61 4.61 0 0 1 8.91 14"/>',
    "layers": '<path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/><path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65"/><path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"/>',
    "repeat": '<path d="m17 2 4 4-4 4"/><path d="M3 11v-1a4 4 0 0 1 4-4h14"/><path d="m7 22-4-4 4-4"/><path d="M21 13v1a4 4 0 0 1-4 4H3"/>',
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
# Concept card / quiz / review rendering
# ---------------------------------------------------------------------------
def build_feynman_answer(c: dict) -> str:
    """Standard explanation shown when the learner clicks '复述 / 看标准讲解'.

    Prefers an explicit ``feynman_answer`` field; otherwise composes a
    reference from the card's own back-face + plain points + analogy so that
    packages built before this field existed still get a useful answer.
    """
    fa = c.get("feynman_answer")
    if fa:
        return f"<p>{html.escape(str(fa))}</p>"
    parts: list[str] = []
    back = html.escape(str(c.get("card_back", "")))
    if back:
        parts.append(f"<p>{back}</p>")
    plain = c.get("plain") or []
    if isinstance(plain, str):
        plain = [plain]
    if plain:
        items = "".join(f"<li>{html.escape(str(p))}</li>" for p in plain)
        parts.append(f"<ul class='plain'>{items}</ul>")
    story = html.escape(str(c.get("story", "")))
    if story:
        parts.append(f"<p class='fa-story'><strong>类比：</strong>{story}</p>")
    return "\n".join(parts) or "<p>（暂无标准讲解，参考卡片背面要点）</p>"


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
        # Feynman module: a "retell" button reveals the standard answer panel,
        # then a separate "I checked it" toggle records progress (XP + sync).
        feynman_block = ""
        if feynman:
            ans_html = build_feynman_answer(c)
            feynman_block = (
                f'<div class="feynman">'
                f'<span class="tag feynman-tag">费曼复述</span>'
                f'<div class="feynman-prompt">{feynman}</div>'
                f'<button class="feynman-retell" type="button" '
                f'onclick="onFeynmanRetell(this)">'
                f'{icon("pen-line", 15)} <span>复述 / 看标准讲解</span></button>'
                f'<div class="feynman-answer" hidden>'
                f'<div class="fa-title">{icon("check", 14)} 标准讲解（对照自评）</div>'
                f'<div class="fa-body">{ans_html}</div></div>'
                f'<span class="feynman-check" role="button" tabindex="0" '
                f'onclick="onFeynmanCheck(this)" '
                f'onkeydown="if(event.key===\'Enter\'||event.key===\' \')onFeynmanCheck(this)">'
                f'<span class="fchk-box">{icon("square", 14)}</span>'
                f'<span class="fchk-label">我已对照核对</span></span>'
                f'</div>'
            )
        visual_block = f'<div class="visual">{svg}</div>' if svg else ""
        out.append(
            f"""
<div class="card" id="card-{i}">
  <div class="card-head"><span class="card-no">{i+1}</span><h3>{term}</h3></div>
  <div class="flip" onclick="onFlip(this)" role="button" tabindex="0"
       onkeydown="if(event.key==='Enter'||event.key===' ')onFlip(this)">
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
        f'<button class="quiz-check" type="button" onclick="checkQuiz(this)">检查</button>'
        f'<div class="quiz-feedback" hidden></div>'
        f'<div class="quiz-explain" hidden>解析：{explain}</div>'
        f"</div>"
    )


def render_review(concepts: list[dict], review: list[dict]) -> str:
    rows = []
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
            f'<button type="button" class="rate" data-q="{q}" onclick="rate(this)">{q}</button>'
            for q in range(0, 6)
        )
        rows.append(
            f"""<tr data-ef="{ef}" data-n="0" data-last="{first}">
  <td class="rv-term">{term}</td>
  <td class="rv-next">+{first} 天</td>
  <td class="rv-rate">{btns}</td>
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
        by_id = {b["id"]: b for b in gam["badges"]}
        for b in user["badges"]:
            by_id[b["id"]] = b
        gam["badges"] = list(by_id.values())

    concepts = data.get("concepts", [])
    quiz_total = sum(1 for c in concepts if c.get("quiz"))
    feynman_total = sum(1 for c in concepts if c.get("feynman"))
    review_total = len(data.get("review_schedule", []))
    cards_total = len(concepts)
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
        "cards_total": cards_total,
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

    # Mini badge strip (lives inside the sticky honor bar, updates live)
    mini = []
    for b in gam["badges"]:
        mini.append(
            f'<span class="hb-mini locked" id="hb-badge-{b["id"]}" '
            f'title="{html.escape(b["name"])}：{html.escape(b["desc"])}">'
            f'{icon(str(b.get("icon", "medal")), 16)}</span>'
        )
    mini_html = "".join(mini)

    honor_bar = f"""
<div class="honor-bar" id="honorBar">
  <div class="hb-left">
    <div class="hb-level">
      <span class="hb-badge">{icon('award', 18)}</span>
      <div class="hb-lv-text"><span id="hbLevelName">{html.escape(first_level)}</span>
        <span class="hb-lv" id="hbLevelNo">Lv.1</span></div>
    </div>
    <div class="hb-xp">
      <div class="hb-xp-track"><div class="hb-xp-fill" id="hbXpFill"></div></div>
      <span class="hb-xp-text" id="hbXpText">0 XP</span>
    </div>
  </div>
  <div class="hb-stats">
    <div class="hb-stat"><span id="hbDoneCards">0/0</span><span class="hb-stat-label">卡片</span></div>
    <div class="hb-stat"><span id="hbDoneQuiz">0/0</span><span class="hb-stat-label">自测</span></div>
    <div class="hb-stat"><span id="hbDoneReview">0/0</span><span class="hb-stat-label">复习</span></div>
    <div class="hb-stat"><span id="hbDoneFeynman">0/0</span><span class="hb-stat-label">费曼</span></div>
    <div class="hb-stat"><span class="hb-streak" id="hbStreakIcon">{icon('flame', 16)}</span>'
        f'<span id="hbStreak">0</span><span class="hb-stat-label">天连续</span></div>
    <div class="hb-stat"><span id="hbBadgeCount">0/{len(gam["badges"])}</span>'
        f'<span class="hb-stat-label">勋章</span></div>
  </div>
  <div class="hb-badges" title="已解锁勋章（实时同步）">{mini_html}</div>
  <div class="hb-progress"><div class="hb-progress-fill" id="hbProgressFill"></div></div>
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
        + '<span class="hall-title">荣誉殿堂 · 徽章图鉴</span></div>'
        '<div class="badge-grid">' + "".join(cards) + "</div>"
        '<div class="hall-hint">悬停每枚勋章看「如何获得」；进度自动存在本学习包（浏览器本地）。'
        '完成上方任意操作，顶部荣誉墙会实时刷新。</div>'
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
# Unified design system. CSS_COMMON carries the DEFAULT (Claude Design) palette
# plus all structural/component styling. Theme variants (editorial / swiss)
# only override CSS custom properties (and a few flourishes), so every new
# component — sticky honor bar, feynman answer panel, live counters — works in
# all three themes without duplicated rules.
# ---------------------------------------------------------------------------
CSS_COMMON = """
:root{
  /* ---- Claude Design default palette (warm ivory + clay accent) ---- */
  --paper:#FBFAF7; --paper-2:#F4F0E9; --card:#FFFFFF;
  --ink:#211E1A; --ink-2:#3A352F; --muted:#7B766C;
  --line:#ECE6DB; --line-2:#DBD2C3;
  --accent:#D2693E; --accent-soft:#FBEDE6; --accent-deep:#A8472A;
  --good:#3E8E5A; --bad:#C0492F; --warn:#C5791F; --gold:#C99A3F;
  --grad-accent:linear-gradient(135deg,#E8915F,#D2693E);
  --grad-good:linear-gradient(135deg,#5BB47A,#3E8E5A);
  --ring:rgba(210,105,62,.32);
  --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,"Songti SC","Noto Serif SC","Source Han Serif SC",serif;
  --sans:system-ui,-apple-system,"Segoe UI","Helvetica Neue","PingFang SC","Microsoft YaHei","Hiragino Sans GB",sans-serif;
  --mono:"SF Mono",ui-monospace,"JetBrains Mono",Menlo,Consolas,monospace;

  /* ---- type scale ---- */
  --fs-h1:clamp(2.1rem,1.2rem + 3.4vw,3.1rem);
  --fs-h2:clamp(1.25rem,1.05rem + .9vw,1.6rem);
  --fs-lead:1.18rem; --fs-base:1rem; --fs-sm:.875rem; --fs-xs:.78rem;
  --lh:1.65; --measure:66ch;
  --r-card:16px; --r-sm:12px; --r-pill:999px;
  --shadow-sm:0 1px 2px rgba(33,30,26,.04),0 2px 8px rgba(33,30,26,.05);
  --shadow-md:0 10px 30px rgba(33,30,26,.09),0 4px 10px rgba(33,30,26,.05);
  --shadow-lg:0 18px 50px rgba(33,30,26,.14);
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth}
body{margin:0;line-height:var(--lh);font-size:var(--fs-base);
  background:var(--paper);color:var(--ink);font-family:var(--sans);
  -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
.wrap{max-width:960px;margin:0 auto;padding:40px 22px 110px}
.muted{color:var(--muted);font-size:var(--fs-sm);line-height:1.5}
:focus-visible{outline:3px solid var(--ring);outline-offset:2px;border-radius:6px}

/* masthead */
header.pkg{margin-bottom:8px}
header.pkg h1{margin:0 0 10px;font-size:var(--fs-h1);line-height:1.08;letter-spacing:-.015em;
  font-family:var(--serif);font-weight:600;color:var(--ink)}
header.pkg .meta{font-size:var(--fs-sm);line-height:1.5;color:var(--muted)}
header.pkg:after{content:"";display:block;width:50px;height:3px;border-radius:2px;background:var(--grad-accent);margin-top:16px}
.offline{display:inline-flex;align-items:center;gap:6px;margin-top:14px;font-size:var(--fs-xs);font-weight:600;
  border:1px solid var(--line-2);color:var(--muted);padding:5px 12px;border-radius:var(--r-pill);background:var(--card)}
.offline svg{display:block}

/* sections */
section{margin-bottom:30px;background:var(--card);border:1px solid var(--line);
  border-radius:var(--r-card);padding:26px 28px;box-shadow:var(--shadow-sm)}
section h2{margin:0 0 18px;font-size:var(--fs-h2);font-weight:700;display:flex;align-items:center;gap:11px;
  font-family:var(--serif);font-weight:600}
section h2 .badge{font-size:var(--fs-xs);padding:3px 11px;border-radius:var(--r-pill);font-weight:700;
  letter-spacing:.04em;background:var(--accent-soft);color:var(--accent)}
.narrative p{font-size:var(--fs-lead);margin:0;line-height:1.7;max-width:var(--measure)}

/* ============ sticky honor wall ============ */
.honor-bar{position:sticky;top:10px;z-index:40;display:flex;flex-wrap:wrap;gap:14px 20px;align-items:center;
  margin:0 0 30px;padding:14px 18px;border-radius:18px;
  background:rgba(251,250,247,.82);-webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px);
  border:1px solid var(--line);box-shadow:var(--shadow-md);overflow:hidden}
.hb-left{flex:1;min-width:250px;display:flex;flex-direction:column;gap:9px}
.hb-level{display:flex;align-items:center;gap:10px}
.hb-badge{display:flex;align-items:center;justify-content:center;width:36px;height:36px;border-radius:11px;
  background:var(--grad-accent);color:#fff;box-shadow:0 4px 12px var(--ring)}
.hb-lv-text{display:flex;flex-direction:column;line-height:1.15}
#hbLevelName{font-weight:800;font-size:15px;color:var(--ink)}
.hb-lv{font-size:11px;color:var(--muted);font-weight:700;margin-top:1px}
.hb-xp{display:flex;align-items:center;gap:11px}
.hb-xp-track{flex:1;height:11px;border-radius:var(--r-pill);background:var(--line);overflow:hidden;
  box-shadow:inset 0 1px 2px rgba(0,0,0,.06)}
.hb-xp-fill{height:100%;width:0;background:var(--grad-accent);border-radius:var(--r-pill);
  transition:width .6s cubic-bezier(.16,1,.3,1);box-shadow:0 0 12px var(--ring)}
.hb-xp-text{font-size:12px;font-weight:700;white-space:nowrap;color:var(--ink-2)}
.hb-stats{display:flex;gap:8px;flex-wrap:wrap}
.hb-stat{display:flex;flex-direction:column;align-items:center;justify-content:center;min-width:56px;
  padding:6px 11px;border-radius:13px;background:var(--card);border:1px solid var(--line);
  box-shadow:var(--shadow-sm);transition:transform .2s,box-shadow .2s}
.hb-stat:hover{transform:translateY(-2px);box-shadow:var(--shadow-md)}
.hb-stat>span:not(.hb-stat-label){font-weight:800;font-size:15px;color:var(--ink);display:flex;align-items:center;gap:3px}
.hb-streak{color:var(--accent)}
#hbStreakIcon{display:inline-flex;align-items:center}
#hbStreakIcon svg{display:block}
.hb-stat-label{font-size:10px;color:var(--muted);margin-top:3px;letter-spacing:.02em}
.hb-badges{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.hb-mini{width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  background:var(--paper-2);color:var(--muted);border:1px solid var(--line);transition:all .3s}
.hb-mini.unlocked{background:var(--grad-accent);color:#fff;border-color:transparent;box-shadow:0 3px 10px var(--ring);
  animation:pop .55s cubic-bezier(.34,1.4,.5,1)}
.hb-progress{position:absolute;left:0;right:0;bottom:0;height:3px;background:var(--line);overflow:hidden}
.hb-progress-fill{height:100%;width:0;background:var(--grad-accent);
  transition:width .6s cubic-bezier(.16,1,.3,1);box-shadow:0 0 8px var(--ring)}

/* hall of fame */
.hall-head{display:flex;align-items:center;gap:9px;font-size:17px;font-weight:800;margin-bottom:14px}
.hall-head svg{display:block;color:var(--accent)}
.badge-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(118px,1fr));gap:14px}
.badge-card{position:relative;cursor:default;transition:transform .22s,box-shadow .22s,border-color .22s;
  border:1px solid var(--line);border-radius:var(--r-card);padding:16px 10px;text-align:center;background:var(--card)}
.badge-card:hover{transform:translateY(-3px);box-shadow:var(--shadow-md)}
.bc-svg{display:block}
.bc-icon{display:flex;align-items:center;justify-content:center;width:58px;height:58px;margin:0 auto;border-radius:50%;
  background:var(--accent-soft);color:var(--accent);transition:all .25s}
.badge-card.locked{filter:grayscale(.85);opacity:.42}
.badge-card.locked .bc-icon{background:var(--paper-2);color:var(--muted)}
.badge-card.unlocked{border-color:var(--accent);box-shadow:var(--shadow-md)}
.badge-card.unlocked .bc-icon{background:var(--grad-accent);color:#fff;box-shadow:0 4px 14px var(--ring)}
.bc-check{position:absolute;top:8px;right:10px;display:none;color:var(--good)}
.badge-card.unlocked .bc-check{display:flex}
.bc-name{font-weight:700;font-size:14px;margin-top:10px;color:var(--ink)}
.bc-desc{font-size:11px;margin-top:4px;line-height:1.4;color:var(--muted)}
.badge-card.just-unlocked{animation:pop .6s cubic-bezier(.34,1.4,.5,1)}
.hall-hint{font-size:var(--fs-xs);margin-top:16px;color:var(--muted)}

/* concept card */
.card{margin-bottom:22px;border:1px solid var(--line);border-radius:var(--r-card);
  padding:18px 20px;background:var(--card);box-shadow:var(--shadow-sm);transition:box-shadow .2s,transform .2s}
.card:hover{box-shadow:var(--shadow-md)}
.card-head{display:flex;align-items:center;gap:11px;margin-bottom:13px}
.card-no{width:28px;height:28px;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:800;
  background:var(--accent);color:#fff;border-radius:10px}
.card-head h3{margin:0;font-size:17px;font-weight:800;letter-spacing:-.01em;color:var(--ink)}

/* flip */
.flip{perspective:1400px;cursor:pointer;outline:none}
.flip-inner{position:relative;transition:transform .6s cubic-bezier(.4,0,.2,1);transform-style:preserve-3d;min-height:120px}
.flip.flipped .flip-inner{transform:rotateY(180deg)}
.flip-front,.flip-back{position:absolute;inset:0;backface-visibility:hidden;-webkit-backface-visibility:hidden;
  padding:17px 19px;border-radius:var(--r-sm)}
.flip-front{overflow:hidden;background:var(--accent-soft);border:1px solid var(--line)}
.flip-back{transform:rotateY(180deg);overflow:auto;background:var(--card);border:1px solid var(--accent);
  box-shadow:inset 0 0 0 1px var(--accent-soft)}
.q-label,.a-label{font-size:11px;text-transform:uppercase;letter-spacing:.08em;font-weight:700;color:var(--muted)}
.q-text{font-size:17px;font-weight:700;margin-top:5px;line-height:1.5;color:var(--ink)}
.flip-hint{position:absolute;bottom:11px;right:14px;font-size:11px;color:var(--muted)}
.a-text{font-size:15px;margin-top:5px;line-height:1.6;color:var(--ink-2)}
.plain{margin:11px 0 0;padding-left:19px}
.plain li{margin:4px 0}
.tag{display:inline-flex;align-items:center;font-size:11px;padding:3px 9px;margin-right:7px;font-weight:700;
  background:var(--accent-soft);color:var(--accent);border-radius:var(--r-pill)}
.story,.mnemonic,.feynman{margin-top:12px;padding:12px 14px;font-size:14px;line-height:1.55;border-radius:var(--r-sm)}
.websource{margin-top:9px;font-size:12px;display:flex;align-items:center;gap:5px;color:var(--muted)}
.websource svg{flex-shrink:0;display:block}
.visual{margin-top:13px}
.visual svg{max-width:100%;height:auto}

/* feynman module */
.feynman{background:#F1F7F2;border-left:3px solid var(--good)}
.feynman-tag{background:#E4F1E8;color:var(--good)}
.feynman-prompt{font-size:14px;line-height:1.6;margin:8px 0 12px;color:var(--ink-2)}
.feynman-retell{display:inline-flex;align-items:center;gap:7px;background:var(--grad-good);color:#fff;border:0;
  padding:9px 16px;border-radius:11px;font-size:13px;font-weight:700;cursor:pointer;
  transition:transform .12s,box-shadow .15s,filter .15s;box-shadow:0 4px 12px rgba(62,142,90,.3)}
.feynman-retell:hover{filter:brightness(1.05);box-shadow:0 6px 16px rgba(62,142,90,.4)}
.feynman-retell:active{transform:scale(.97)}
.feynman-retell.active{background:var(--good)}
.feynman-answer{margin-top:12px;padding:14px 16px;border-radius:var(--r-sm);background:var(--card);
  border:1px solid var(--line);box-shadow:var(--shadow-sm);animation:fadeUp .35s ease}
.feynman-answer[hidden]{display:none}
.fa-title{font-size:12px;font-weight:800;color:var(--accent);text-transform:uppercase;letter-spacing:.06em;
  margin-bottom:9px;display:flex;align-items:center;gap:6px}
.fa-body{font-size:14px;line-height:1.65;color:var(--ink-2)}
.fa-body .plain{margin:8px 0 0;padding-left:18px}
.fa-story{margin-top:10px;color:var(--ink)}
.feynman-check{margin-top:13px;display:inline-flex;align-items:center;gap:7px;font-size:13px;font-weight:700;
  cursor:pointer;user-select:none;background:var(--card);border:1.5px solid var(--good);color:#2F7A53;
  border-radius:11px;padding:8px 14px;transition:all .15s}
.feynman-check:hover{background:#EAF4EE}
.feynman-check.done{background:var(--good);border-color:var(--good);color:#fff}
.feynman-check.done .fchk-box{color:#fff}

/* quiz */
.quiz{margin-top:13px;padding:14px 15px;background:var(--accent-soft);border:1px dashed var(--line-2);border-radius:var(--r-sm)}
.quiz-q{font-size:14px;font-weight:700;margin-bottom:9px;color:var(--ink)}
.quiz-tag{background:#F0DED4;color:var(--accent)}
.opt{display:block;margin:5px 0;cursor:pointer;font-size:14px;color:var(--ink-2)}
.opt input{margin-right:7px;accent-color:var(--accent)}
.fill-input{padding:8px 11px;width:240px;max-width:100%;font-size:14px;border:1px solid var(--line);border-radius:10px;
  transition:border-color .15s,box-shadow .15s}
.fill-input:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
.quiz-check{margin-top:9px;color:#fff;border:0;padding:9px 20px;cursor:pointer;font-size:13px;font-weight:700;
  border-radius:10px;background:var(--grad-accent);box-shadow:0 4px 12px var(--ring);transition:filter .15s,transform .1s}
.quiz-check:hover{filter:brightness(1.05)}
.quiz-check:active{transform:scale(.97)}
.quiz-feedback{margin-top:9px;font-weight:700;font-size:14px;display:flex;align-items:center;gap:6px}
.quiz-feedback.ok{color:var(--good)} .quiz-feedback.no{color:var(--bad)}
.quiz-feedback .fb-ic{display:inline-flex;align-items:center;gap:5px}
.quiz-explain{margin-top:7px;font-size:13px;color:var(--muted);line-height:1.5}

/* review */
.review{width:100%;border-collapse:collapse;font-size:14px}
.review th,.review td{border-bottom:1px solid var(--line);padding:11px 9px;text-align:left}
.review th{font-size:12px;color:var(--muted);font-weight:700;letter-spacing:.03em}
.review tbody tr:last-child td{border-bottom:0}
.rate{margin:0 2px;width:32px;height:32px;background:var(--card);cursor:pointer;font-size:13px;font-weight:600;
  color:var(--muted);border:1px solid var(--line);border-radius:9px;transition:all .12s}
.rate:hover{background:var(--accent);color:#fff;border-color:var(--accent)}
.rate.active{background:var(--accent-deep);color:#fff;border-color:var(--accent-deep)}
.rv-next{font-weight:800;color:var(--accent)}
.rv-term{font-weight:600;color:var(--ink)}
footer.pkg{text-align:center;font-size:var(--fs-xs);margin-top:14px;line-height:1.6;color:var(--muted)}

/* toast */
.toast{position:fixed;left:50%;bottom:32px;transform:translateX(-50%) translateY(24px);
  color:#fff;padding:13px 20px;border-radius:14px;font-size:14px;font-weight:600;
  display:flex;align-items:center;gap:9px;opacity:0;pointer-events:none;transition:opacity .3s,transform .3s;
  z-index:60;background:var(--ink);box-shadow:var(--shadow-lg)}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
.toast .t-icon{display:flex;align-items:center;color:var(--accent)}
.toast .t-icon svg{display:block}

@keyframes pop{0%{transform:scale(.7);opacity:0}60%{transform:scale(1.12);opacity:1}100%{transform:scale(1)}}
@keyframes fadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}

@media (max-width:560px){
  .wrap{padding:22px 14px 72px}
  .badge-grid{grid-template-columns:repeat(auto-fill,minmax(96px,1fr));gap:10px}
  .honor-bar{gap:10px 14px;padding:12px}
  section{padding:20px 16px}
}
@media (prefers-reduced-motion:reduce){
  *{animation-duration:.001ms!important;animation-iteration-count:1!important;
    transition-duration:.001ms!important;scroll-behavior:auto!important}
}
"""

# Theme variants: only override custom properties + a few flourishes.
CSS_EDITORIAL = """
:root{
  --paper:#f4f1ea; --paper-2:#ece6d8; --card:#fbf9f2;
  --ink:#1d1a14; --ink-2:#2c271e; --muted:#7a6f5b;
  --line:#ddd4c0; --line-2:#cdc1a6;
  --accent:#9a3b22; --accent-soft:#f3e7df; --accent-deep:#6f2a16;
  --good:#3f7d4f; --bad:#bf3b30; --gold:#bd8a2c;
  --grad-accent:linear-gradient(135deg,#c25a36,#9a3b22);
  --grad-good:linear-gradient(135deg,#5aa06a,#3f7d4f);
  --ring:rgba(154,59,34,.3);
}
body{background:var(--paper)}
header.pkg h1{font-family:var(--serif);font-weight:600}
"""

CSS_SWISS = """
:root{
  --paper:#fafaf8; --paper-2:#f0f0ee; --card:#ffffff;
  --ink:#0f0f0f; --ink-2:#2a2a29; --muted:#6f6f6c;
  --line:#d8d8d4; --line-2:#bcbcb6;
  --accent:#002FA7; --accent-soft:#eef0f6; --accent-deep:#001f6e;
  --good:#0a7d4f; --bad:#c0322b; --gold:#C99A3F;
  --grad-accent:linear-gradient(135deg,#244bc4,#002FA7);
  --grad-good:linear-gradient(135deg,#2a9b6c,#0a7d4f);
  --ring:rgba(0,47,167,.3);
  --serif:"Helvetica Neue",Helvetica,Arial,system-ui,"PingFang SC","Microsoft YaHei",sans-serif;
}
body{background:var(--paper)}
header.pkg h1{font-family:var(--serif);font-weight:700;letter-spacing:-.02em}
.honor-bar{border-radius:0;border:0;border-top:2px solid var(--ink);border-bottom:1px solid var(--line)}
.hb-badge{border-radius:0;background:var(--ink)}
.hb-mini{border-radius:0}
.hb-stat,.card,.flip-front,.flip-back,.feynman-answer,.quiz{border-radius:0}
.feynman-retell,.quiz-check,.feynman-check{border-radius:0}
"""


JS = r"""
/* ===== Gamification engine (shared, live-synced state) ===== */
const PKG = __PKG__;
const ICONS = __ICONS__;
function iconSvg(name,size,cls){var inner=ICONS[name]||ICONS['medal'];return '<svg viewBox="0 0 24 24" width="'+(size||18)+'" height="'+(size||18)+'" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"'+(cls?(' class="'+cls+'"'):'')+'>'+inner+'</svg>';}
function setText(id,t){var e=document.getElementById(id);if(e)e.textContent=t;}
function setWidth(id,w){var e=document.getElementById(id);if(e)e.style.width=w+'%';}
function clamp(v){return Math.max(0,Math.min(100,v));}

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

/* single source of truth for the on-screen honor wall */
function renderHonor(){
  var lv=levelFor(S.xp), nxt=nextLevel(S.xp);
  setText('hbLevelName', lv.title);
  setText('hbLevelNo','Lv.'+lv.level);
  var pct=100; if(nxt){var span=nxt.min_xp-lv.min_xp; pct=clamp((S.xp-lv.min_xp)/span*100);}
  setWidth('hbXpFill', pct);
  setText('hbXpText', S.xp+' XP'+(nxt?(' / '+nxt.min_xp):' · 满级'));
  setText('hbStreak', S.streak);
  var si=document.getElementById('hbStreakIcon'); if(si)si.style.opacity=S.streak>0?'1':'0.35';
  var dc=Object.keys(S.flips).length;
  setText('hbDoneCards', dc+'/'+(PKG.totals.cards_total||0));
  setText('hbDoneQuiz', S.quizAnswered+'/'+(PKG.totals.quiz_total||0));
  setText('hbDoneReview', S.reviewCount+'/'+(PKG.totals.review_total||0));
  setText('hbDoneFeynman', S.feynmanDone+'/'+(PKG.totals.feynman_total||0));
  setText('hbBadgeCount', S.badges.length+'/'+(PKG.badges.length||0));
  var total=(PKG.totals.cards_total||0)+(PKG.totals.quiz_total||0)+(PKG.totals.review_total||0)+(PKG.totals.feynman_total||0);
  var done=dc+S.quizAnswered+S.reviewCount+S.feynmanDone;
  setWidth('hbProgressFill', total? clamp(done/total*100):0);
}
function paintBadge(id, unlocked){
  ['bg-'+id,'hb-badge-'+id].forEach(function(pid){
    var el=document.getElementById(pid); if(!el)return;
    if(unlocked){el.classList.add('unlocked');el.classList.remove('locked');}
    else{el.classList.add('locked');el.classList.remove('unlocked');}
  });
}
function renderHall(){
  PKG.badges.forEach(function(b){ paintBadge(b.id, S.badges.indexOf(b.id)>=0); });
}
function toast(msg,ic){
  var t=document.getElementById('mfToast');
  if(!t){t=document.createElement('div');t.id='mfToast';t.className='toast';document.body.appendChild(t);}
  t.innerHTML='<span class="t-icon">'+iconSvg(ic||'medal',16)+'</span>'+msg;
  t.classList.add('show'); clearTimeout(t._tm); t._tm=setTimeout(function(){t.classList.remove('show');},2600);
}
function grantXP(n){ S.xp+=n; }
function refresh(){ renderHonor(); renderHall(); }
function afterAction(){
  var beforeLv=levelFor(S.xp).level;
  var newly=evaluateBadges();
  lsSet(S); refresh();
  var afterLv=levelFor(S.xp).level;
  if(afterLv>beforeLv) toast('升级！'+levelFor(S.xp).title,'sparkles');
  newly.forEach(function(b){
    var el=document.getElementById('bg-'+b.id);
    paintBadge(b.id,true);
    if(el){el.classList.add('just-unlocked');setTimeout(function(){el.classList.remove('just-unlocked');},600);}
    toast('解锁勋章：'+b.name, b.icon);
  });
}

/* ===== Quiz ===== */
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
    if(!sel){fb.innerHTML=iconSvg('x',16)+'<span class="fb-ic">请先选择一个答案</span>';fb.className='quiz-feedback no';fb.hidden=false;return;}
    ok = parseInt(sel.value,10)===ans;
  }
  fb.innerHTML = (ok?iconSvg('check',16)+'<span class="fb-ic">答对了！</span>'
                    :iconSvg('x',16)+'<span class="fb-ic">再想想</span>');
  fb.className = 'quiz-feedback '+(ok?'ok':'no');
  fb.hidden=false; ex.hidden=false;
  if(ok && !q.dataset.correctMarked){ q.dataset.correctMarked='1'; S.quizCorrect++; }
  if(q.dataset.answered!=='1'){ q.dataset.answered='1';
    S.quizAnswered++; grantXP(ok?PKG.xp_rules.quiz_correct:PKG.xp_rules.quiz_wrong);
    bumpStreak(); afterAction();
  }
}

/* ===== SM-2 review ===== */
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
  // highlight selected rating
  row.querySelectorAll('.rate').forEach(function(b){b.classList.remove('active');});
  btn.classList.add('active');
  if(row.dataset.rated!=='1'){ row.dataset.rated='1';
    if(q>=4) row.dataset.ge4='1';
    S.reviewCount++; grantXP(PKG.xp_rules.review_rate); bumpStreak(); afterAction();
  }
}

/* ===== Flip card ===== */
function onFlip(flipEl){
  flipEl.classList.toggle('flipped');
  var card=flipEl.closest('.card'); if(!card)return;
  var idx=card.id; if(S.flips[idx])return; S.flips[idx]=1;
  grantXP(PKG.xp_rules.flip_card); bumpStreak(); afterAction();
}

/* ===== Feynman module ===== */
function onFeynmanRetell(btn){
  var wrap=btn.closest('.feynman');
  var ans=wrap.querySelector('.feynman-answer');
  if(ans.hidden){ ans.hidden=false; btn.classList.add('active'); }
  else { ans.hidden=true; btn.classList.remove('active'); }
}
function onFeynmanCheck(fc){
  if(fc.classList.contains('done'))return;
  fc.classList.add('done');
  var box=fc.querySelector('.fchk-box'); if(box)box.innerHTML=iconSvg('check',14);
  var lab=fc.querySelector('.fchk-label'); if(lab)lab.textContent='已对照核对 ✓';
  S.feynmanDone++; grantXP(PKG.xp_rules.feynman_done); bumpStreak(); afterAction();
}

/* ===== init ===== */
(function init(){
  evaluateBadges(); lsSet(S); refresh();
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
  <h2><span class="badge">养成</span> 荣誉殿堂 · 徽章图鉴</h2>
  {hall_of_fame}
</section>

<section>
  <h2><span class="badge">总览</span> 一句话故事</h2>
  <div class="narrative"><p>{narrative}</p></div>
</section>

<section>
  <h2><span class="badge">记忆</span> 知识卡片（点击翻转）</h2>
  {cards}
</section>

<section>
  <h2><span class="badge">测验</span> 自测区</h2>
  <p class="muted">先答再点「检查」，看解析。错的回对应卡片复习。进度实时同步到顶部荣誉墙。</p>
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


def build_html(data: dict, theme: str = "claude") -> str:
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
    review_html = render_review(concepts, data.get("review_schedule", []))
    gam = compute_gamification(data)
    honor_bar, hall_of_fame, pkg_json = render_gamification(data, gam)
    quizzes_intro = (
        "下面每张卡片底部都带自测题；这里汇总提示：优先用「填空/自己举例」的方式回忆，"
        "比被动读记得牢（生成效应）。"
    )
    theme_css = {"claude": "", "editorial": CSS_EDITORIAL, "swiss": CSS_SWISS}.get(theme, "")
    css = CSS_COMMON + theme_css
    return PAGE.format(
        title=title,
        source=source,
        audience=audience,
        generated_at=generated_at,
        narrative=narrative,
        cards=cards_html or "<p class='muted'>（无概念数据）</p>",
        quizzes_intro=quizzes_intro,
        review=review_html or "<p class='muted'>（无复习计划）</p>",
        honor_bar=honor_bar,
        hall_of_fame=hall_of_fame,
        offline_icon=icon("package", 12),
        js=JS.replace("__PKG__", pkg_json).replace("__ICONS__", json.dumps(ICONS, ensure_ascii=False)),
        css=css,
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
        if c.get("feynman"):
            lines.append(f"**费曼复述：** {c.get('feynman')}")
            fa = c.get("feynman_answer")
            if fa:
                lines.append(f"**标准讲解：** {fa}")
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
    ap.add_argument("--theme", dest="theme", choices=["claude", "editorial", "swiss"],
                    default="claude",
                    help="Visual theme for HTML output: claude (default, Claude Design warm "
                         "ivory + clay accent + serif display), editorial (warm magazine), or "
                         "swiss (Swiss International / right angles, klein blue).")
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
