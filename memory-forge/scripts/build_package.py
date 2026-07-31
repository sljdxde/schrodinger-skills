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
            f'<div class="feynman"><span class="tag">费曼</span>{feynman}</div>'
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
"""


JS = """
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
}
document.addEventListener('click',function(e){
  if(e.target.classList.contains('quiz-check')) checkQuiz(e.target);
  if(e.target.classList.contains('rate')) rate(e.target);
});
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
</header>

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
        js=JS,
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
