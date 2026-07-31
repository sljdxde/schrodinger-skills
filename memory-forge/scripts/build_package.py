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
            f'<div class="websource">🔗 {web_source}</div>' if web_source else ""
        )
        feynman_block = (
            f'<div class="feynman"><span class="tag">费曼</span>{feynman}'
            f'<span class="feynman-check" role="button" tabindex="0" '
            f'onkeydown="if(event.key===\'Enter\'||event.key===\' \')this.click()">'
            f'<span class="fchk-box">☐</span>'
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
            {"id": "first_pack", "name": "启程", "icon": "🌱",
             "desc": "打开学习包即得", "trigger": "on_generate"},
            {"id": "first_quiz", "name": "破冰", "icon": "❄️",
             "desc": "首次答对自测", "trigger": "quiz_correct_first"},
            {"id": "all_quiz", "name": "火眼金睛", "icon": "🎯",
             "desc": "本包自测全对", "trigger": "quiz_all_correct"},
            {"id": "first_review", "name": "温故知新", "icon": "🌅",
             "desc": "首次复习自评", "trigger": "review_rate_first"},
            {"id": "iron_will", "name": "百炼成钢", "icon": "🛡️",
             "desc": "复习自评累计 10 次", "trigger": "review_count>=10"},
            {"id": "master_all", "name": "融会贯通", "icon": "🏆",
             "desc": "所有概念自评 ≥4", "trigger": "all_review_ge4"},
            {"id": "feynman_master", "name": "费曼小能手", "icon": "✍️",
             "desc": "完成全部费曼自述", "trigger": "feynman_all"},
            {"id": "streak3", "name": "三日之约", "icon": "🔥",
             "desc": "连续 3 天学习", "trigger": "streak>=3"},
            {"id": "streak7", "name": "一周不辍", "icon": "🌟",
             "desc": "连续 7 天学习", "trigger": "streak>=7"},
            {"id": "level5", "name": "满腹经纶", "icon": "📜",
             "desc": "等级达到「满腹经纶」", "trigger": "level>=5"},
            {"id": "knowledge_hunter", "name": "知识猎人", "icon": "🧭",
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
  <div class="hb-level"><span class="hb-badge">🎖️</span><span id="hbLevelName">{html.escape(first_level)}</span>
    <span class="hb-lv" id="hbLevelNo">Lv.1</span></div>
  <div class="hb-xp"><div class="hb-xp-track"><div class="hb-xp-fill" id="hbXpFill"></div></div>
    <span class="hb-xp-text" id="hbXpText">0 XP</span></div>
  <div class="hb-streak"><span id="hbStreakIcon">💤</span><span id="hbStreak">0</span> 天连续</div>
</div>"""

    cards = []
    for b in gam["badges"]:
        icon = html.escape(str(b.get("icon", "🏅")))
        name = html.escape(str(b.get("name", "")))
        desc = html.escape(str(b.get("desc", "")))
        bid = html.escape(str(b.get("id", "")))
        cards.append(
            f'<div class="badge-card locked" id="bg-{bid}" data-badge="{bid}" '
            f'title="{desc}"><div class="bc-icon">{icon}</div>'
            f'<div class="bc-name">{name}</div><div class="bc-desc">{desc}</div></div>'
        )
    hall = (
        '<div class="hall"><div class="hall-head">🏅 荣誉殿堂</div>'
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
CSS = """
:root{
  --bg:#f7f8fa; --card:#ffffff; --ink:#1f2430; --muted:#6b7280;
  --brand:#4f46e5; --brand-soft:#eef2ff; --good:#16a34a; --bad:#dc2626;
  --line:#e5e7eb; --accent:#0ea5e9;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
  line-height:1.6}
.wrap{max-width:920px;margin:0 auto;padding:28px 20px 80px}
header.pkg{background:linear-gradient(135deg,#4f46e5,#0ea5e9);color:#fff;
  border-radius:16px;padding:26px 28px;margin-bottom:24px}
header.pkg h1{margin:0 0 6px;font-size:24px}
header.pkg .meta{opacity:.92;font-size:13px}
.offline{display:inline-block;margin-top:10px;background:rgba(255,255,255,.18);
  padding:4px 10px;border-radius:999px;font-size:12px}
section{background:var(--card);border:1px solid var(--line);border-radius:14px;
  padding:20px 22px;margin-bottom:22px}
section h2{margin:0 0 14px;font-size:19px;display:flex;align-items:center;gap:8px}
section h2 .badge{font-size:12px;background:var(--brand-soft);color:var(--brand);
  padding:2px 9px;border-radius:999px;font-weight:600}
.narrative p{font-size:16px}
.card{border:1px solid var(--line);border-radius:14px;padding:16px 18px;margin-bottom:18px;
  background:#fff}
.card-head{display:flex;align-items:center;gap:10px;margin-bottom:12px}
.card-no{background:var(--brand);color:#fff;width:26px;height:26px;border-radius:8px;
  display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:700}
.flip{perspective:1200px;cursor:pointer;outline:none}
.flip-inner{position:relative;transition:transform .5s;transform-style:preserve-3d;
  min-height:120px}
.flip.flipped .flip-inner{transform:rotateY(180deg)}
.flip-front,.flip-back{position:absolute;inset:0;backface-visibility:hidden;
  border-radius:12px;padding:16px 18px;border:1px solid var(--line)}
.flip-front{background:var(--brand-soft)}
.flip-back{background:#fff;transform:rotateY(180deg);overflow:auto;
  border-color:var(--brand)}
.q-label,.a-label{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
.q-text{font-size:17px;font-weight:600;margin-top:4px}
.flip-hint{position:absolute;bottom:10px;right:14px;font-size:11px;color:var(--muted)}
.a-text{font-size:15px;margin-top:4px}
.plain{margin:10px 0 0;padding-left:18px}
.plain li{margin:3px 0}
.tag{display:inline-block;background:#fff3e0;color:#b45309;font-size:11px;
  padding:1px 7px;border-radius:6px;margin-right:6px;font-weight:600}
.story,.mnemonic,.feynman{margin-top:10px;padding:9px 12px;background:#fffbeb;
  border-left:3px solid #f59e0b;border-radius:8px;font-size:14px}
.mnemonic{background:#ecfeff;border-left-color:#06b6d4}
.feynman{background:#f0fdf4;border-left-color:#22c55e}
.websource{margin-top:8px;font-size:12px;color:var(--muted)}
.visual{margin-top:12px}
.visual svg{max-width:100%;height:auto}
.mindmap-svg{background:#fafafa;border:1px solid var(--line);border-radius:10px}
.mm-link{stroke:#cbd5e1;stroke-width:1.5}
.mm-rect{fill:#fff;stroke:var(--brand);stroke-width:1.5}
.mm-root .mm-rect{fill:var(--brand);stroke:var(--brand)}
.mm-text{font-size:13px;fill:var(--ink);text-anchor:middle;font-family:inherit}
.mm-root .mm-text{fill:#fff;font-weight:700}
.quiz{margin-top:12px;padding:12px 14px;background:#f8fafc;border:1px dashed var(--line);
  border-radius:10px}
.quiz-q{font-size:14px;font-weight:600;margin-bottom:8px}
.quiz-tag{background:#ede9fe;color:#6d28d9}
.opt{display:block;margin:4px 0;cursor:pointer}
.fill-input{padding:7px 10px;border:1px solid var(--line);border-radius:8px;width:200px;
  font-size:14px}
.quiz-check{margin-top:8px;background:var(--brand);color:#fff;border:0;padding:7px 16px;
  border-radius:8px;cursor:pointer;font-size:13px}
.quiz-feedback{margin-top:8px;font-weight:700}
.quiz-feedback.ok{color:var(--good)} .quiz-feedback.no{color:var(--bad)}
.quiz-explain{margin-top:6px;font-size:13px;color:var(--muted)}
.review{width:100%;border-collapse:collapse;font-size:14px}
.review th,.review td{border-bottom:1px solid var(--line);padding:10px 8px;text-align:left}
.review th{font-size:12px;color:var(--muted)}
.rate{margin:0 2px;width:30px;height:30px;border:1px solid var(--line);background:#fff;
  border-radius:8px;cursor:pointer;font-size:13px}
.rate:hover{background:var(--brand-soft);border-color:var(--brand)}
.rv-next{font-weight:700;color:var(--brand)}
footer.pkg{text-align:center;color:var(--muted);font-size:12px;margin-top:10px}

/* ---- gamification: honor bar / badges / streak / toast ---- */
.honor-bar{display:flex;flex-wrap:wrap;gap:14px;align-items:center;
  background:rgba(255,255,255,.16);border-radius:12px;padding:12px 16px;margin-top:14px;color:#fff}
.hb-level{display:flex;align-items:center;gap:8px;font-weight:700}
.hb-badge{font-size:18px}
.hb-lv{background:rgba(255,255,255,.25);padding:1px 8px;border-radius:999px;font-size:12px}
.hb-xp{flex:1;min-width:160px;display:flex;align-items:center;gap:8px}
.hb-xp-track{flex:1;height:10px;background:rgba(255,255,255,.25);border-radius:999px;overflow:hidden}
.hb-xp-fill{height:100%;width:0;background:linear-gradient(90deg,#fde047,#f59e0b);transition:width .4s}
.hb-xp-text{font-size:12px;white-space:nowrap}
.hb-streak{font-weight:700;font-size:14px}
.hall-head{font-size:17px;font-weight:700;margin-bottom:12px}
.badge-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:12px}
.badge-card{border:1px solid var(--line);border-radius:12px;padding:12px 10px;text-align:center;
  background:#fff;transition:transform .2s,box-shadow .2s;position:relative;cursor:default}
.badge-card .bc-icon{font-size:30px;line-height:1.2}
.badge-card .bc-name{font-weight:700;font-size:14px;margin-top:4px}
.badge-card .bc-desc{font-size:11px;color:var(--muted);margin-top:3px}
.badge-card.locked{filter:grayscale(1);opacity:.45}
.badge-card.unlocked{border-color:var(--brand);box-shadow:0 4px 14px rgba(79,70,229,.18)}
.badge-card.unlocked:after{content:"✓";position:absolute;top:6px;right:8px;color:var(--good);font-weight:800}
.badge-card.just-unlocked{animation:pop .5s}
@keyframes pop{0%{transform:scale(.8)}60%{transform:scale(1.12)}100%{transform:scale(1)}}
.hall-hint{font-size:12px;color:var(--muted);margin-top:12px}
.feynman-check{margin-top:8px;display:inline-flex;align-items:center;gap:6px;font-size:13px;
  background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:4px 10px;cursor:pointer;user-select:none}
.feynman-check.done{background:#16a34a;color:#fff;border-color:#16a34a}
.toast{position:fixed;left:50%;bottom:30px;transform:translateX(-50%) translateY(20px);
  background:#1f2430;color:#fff;padding:12px 18px;border-radius:12px;font-size:14px;
  opacity:0;pointer-events:none;transition:opacity .3s,transform .3s;z-index:50;box-shadow:0 8px 30px rgba(0,0,0,.3)}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
.toast .t-icon{margin-right:8px}
"""


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
  fb.textContent = ok?'✓ 答对了！':'✗ 再想想';
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
  var si=document.getElementById('hbStreakIcon'); if(si)si.textContent=S.streak>0?'🔥':'💤';
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
  t.innerHTML='<span class="t-icon">'+(icon||'🏅')+'</span>'+msg;
  t.classList.add('show'); clearTimeout(t._tm); t._tm=setTimeout(function(){t.classList.remove('show');},2600);
}
function grantXP(n){ S.xp+=n; }
function afterAction(){
  var beforeLv=levelFor(S.xp).level;
  var newly=evaluateBadges();
  lsSet(S); renderHonor(); renderHall();
  var afterLv=levelFor(S.xp).level;
  if(afterLv>beforeLv) toast('升级！'+levelFor(S.xp).title+' 🎉','🎉');
  newly.forEach(function(b){
    var el=document.getElementById('bg-'+b.id);
    if(el){el.classList.add('just-unlocked');setTimeout(function(){el.classList.remove('just-unlocked');},600);}
    toast('解锁勋章：'+b.name+' '+b.icon, b.icon);
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
  var box=fc.querySelector('.fchk-box'); if(box)box.textContent='☑';
  var lab=fc.querySelector('.fchk-label'); if(lab)lab.textContent='已复述 ✓';
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
  <div class="offline">📦 离线自包含 · 无需联网</div>
  {honor_bar}
</header>

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


def build_html(data: dict) -> str:
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
        js=JS.replace("__PKG__", pkg_json),
        css=CSS,
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
            lines.append(f"🔗 {c.get('web_source')}")
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
                lines.append(f"- {b['icon']} {b['name']}：{b['desc']}")
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
    args = ap.parse_args()

    payload = json.loads(Path(args.infile).read_text(encoding="utf-8"))
    if args.fmt == "md":
        content = build_md(payload)
        ext = ".md"
    else:
        content = build_html(payload)
        ext = ".html"

    out = args.outfile or (Path(args.infile).stem + "-package" + ext)
    Path(out).write_text(content, encoding="utf-8")
    print(f"wrote {out} ({len(content)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
