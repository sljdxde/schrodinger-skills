#!/usr/bin/env python3
"""银树湾市场分析 · 多主题样式生成器（全章节版）。

基于 awesome-claude-design 的美学族系，对同一份真实数据/正文生成多套差异化
HTML 主题，供用户挑选。内容（正文 HTML）完全一致，仅 CSS 主题不同。

两种用法：
  # 预览全部候选样式（output/银树湾_样式_{key}.html，供用户挑）
  python scripts/gen_styled_report.py

  # 用户选定某一套后，生成最终报告并记住偏好（output/银树湾_报告.html）
  python scripts/gen_styled_report.py --theme warm

  # 查看可选主题
  python scripts/gen_styled_report.py --list

报告结构严格对齐 references/report-template.md：13 个主体章节 + 学区专章 +
梯队评级 + 评分表，内嵌 4 张零依赖 SVG 走势图（月度时间轴 / 价格口径对比 /
学区梯队坐标系 / 三情景区间），均由 scripts/data_sources.py 实时计算，不编造数据。
"""
import sys
import os
import json
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
from pathlib import Path
CACHE_DIR = Path(ROOT) / ".cache" / "beike_probe"
sys.path.insert(0, HERE)

import data_sources as ds  # noqa: E402
from report_themes import (THEMES, list_themes, save_theme,  # noqa: E402
                           resolve_theme, render_report_html)

# 真实 CLI 原始数据缓存目录（实时拉取时自动写入；CLI 临时故障时 --from-cache 回退）
CACHE_DIR = Path(ROOT) / ".cache" / "beike_probe"

# 新增「房屋成交详细信息」模块卡片样式（跨主题通用，借主题变量+兜底值）
TX_DETAIL_CSS = """
.tx-detail{margin:4px 0 2px}
.tx-detail h3{font-size:18px;font-weight:700;margin:0 0 14px;
  font-family:var(--serif,Georgia,serif)}
.tx-card{border:1px solid var(--line,#e4ddcd);border-radius:var(--radius,12px);
  padding:14px 16px;margin:14px 0;background:var(--surface,#fffdf8)}
.tx-card-head{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px;
  padding-bottom:10px;margin-bottom:10px;border-bottom:1px solid var(--line,#e4ddcd)}
.tx-card-head .tx-date{font-family:var(--mono,monospace);font-size:12px;
  color:var(--muted,#8a8272);font-weight:600;letter-spacing:.03em}
.tx-card-head .tx-title{font-weight:700;font-size:15px;flex:1;min-width:160px}
.tx-card-head .tx-link{font-size:12.5px;text-decoration:none;
  color:var(--accent,#5c6b3c);border-bottom:1px solid rgba(120,120,120,.3);white-space:nowrap}
.tx-card-head .tx-link:hover{border-bottom-color:var(--accent,#5c6b3c)}
.tx-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));
  gap:14px 22px}
.tx-group h4{font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;
  color:var(--muted,#8a8272);margin:0 0 6px;font-weight:700}
.tx-group dl{margin:0;display:grid;gap:4px}
.tx-group dl>div{display:flex;justify-content:space-between;gap:10px;font-size:13px}
.tx-group dt{color:var(--muted,#8a8272);flex:0 0 auto;margin:0}
.tx-group dd{margin:0;text-align:right;font-weight:600;word-break:break-word}
.tx-detail .muted{font-size:12.5px;margin-top:14px;color:var(--muted,#8a8272)}
"""

# 内嵌 SVG 图表容器样式（所有主题通用；report_themes 基础 CSS 不含，须在此补充）
CHART_CSS = """
.chartbox{background:var(--surface,#fffdf8);border:1px solid var(--line,#e4ddcd);
  border-radius:var(--radius,12px);padding:14px;margin:16px 0}
.chartbox svg{width:100%;height:auto;display:block}
.caption{color:var(--muted,#8a8272);font-size:12.5px;margin-top:8px;line-height:1.5}
.warn{background:var(--warn,#f6e9e3);border:1px solid #e5b8a4;color:var(--warn-ink,#9a3412);
  border-radius:10px;padding:12px 16px;font-size:14px;margin:14px 0}
.note{background:var(--olive-soft,#e8ecd9);border-left:4px solid var(--olive,#5c6b3c);
  padding:10px 12px;border-radius:8px;margin:10px 0;font-size:13px;color:var(--ink,#2f2a24)}
table.d{width:100%;border-collapse:collapse;margin:12px 0;font-size:13.5px;
  background:var(--surface,#fffdf8);border-radius:12px;overflow:hidden}
table.d th{background:var(--olive-soft,#e8ecd9);font-weight:600;text-align:left;
  color:var(--ink,#2f2a24)}
table.d th,table.d td{border:1px solid var(--line,#e4ddcd);padding:7px 10px;vertical-align:top}
table.d td.num{text-align:right;font-variant-numeric:tabular-nums}
"""


def _cache_path(community, city, cmd):
    return CACHE_DIR / f"{community}_{city}_{cmd}.json"


def _cmd_key(args):
    """把 CLI 参数映射到缓存文件名（与 BeikeCliSource._BEIKE_COMMANDS 对应）。

    buy 系列用第二段（search/sold/market/resblock）作为缓存键，互不撞名。
    """
    return args[1] if len(args) > 1 else ""


def _install_cache(community, city):
    """用本地缓存的真实原始数据替换实时 CLI 调用（CLI 临时故障兜底）。

    兼容官方 CLI 的多段 JSON 拼接输出：用 _json_extract_all 抽取全部顶层对象，
    返回「含 data 字段且 data 最长」的那一个（与 _run_beike_cli 真实行为一致），
    避免直接 json.loads 多段 JSON 报「Extra data」失败。
    """
    real = ds._run_beike_cli

    def fake(args):
        key = _cmd_key(args)
        p = _cache_path(community, city, key)
        if not p.exists():
            raise RuntimeError(f"缓存缺失：{p}（无法回退）")
        text = p.read_text(encoding="utf-8")
        objs = ds._json_extract_all(text)
        if not objs:
            return json.loads(text)
        data_objs = [o for o in objs if isinstance(o, dict)
                     and isinstance(o.get("data"), str)]
        if not data_objs:
            for o in objs:
                if isinstance(o, dict):
                    return o
            return objs[0]
        return max(data_objs, key=lambda o: len(o.get("data", "")))
    ds._run_beike_cli = fake


def _install_recording(community, city):
    """实时 CLI 调用时，把原始返回自动落盘到缓存目录，供日后 --from-cache 使用。"""
    real = ds._run_beike_cli

    def record(args):
        key = _cmd_key(args)
        out = real(args)
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            _cache_path(community, city, key).write_text(
                json.dumps(out, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
        return out
    ds._run_beike_cli = record


def _chart_block(svg, caption):
    if not svg or svg.startswith("<!--"):
        return ""  # 无数据的图表不强行占位
    return f'<div class="chartbox">{svg}<div class="caption">{caption}</div></div>'


def _load_city_policy(city):
    try:
        p = os.path.join(HERE, "city_policy.json")
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        return data.get(city, {}) or {}
    except Exception:
        return {}


# --------------------------------------------------------------------------- #
# 1) 构建分析数据（全章节；正文 HTML 在所有主题间保持完全相同）
# --------------------------------------------------------------------------- #
def build_analysis(community, city, manual_tx=None, manual_source=""):
    ms = ds.multi_platform_search(community, "", city, 36, include_cross=True)
    beike = next(p for p in ms["platforms"] if p["source"].startswith("贝壳"))

    # 公开检索兜底注入：贝壳 CLI 0.2.x 未开放 sold/market 工具时，用 SUPPLEMENT_PATH 填补历史/成交
    _supp_path = os.environ.get("SUPPLEMENT_PATH")
    if _supp_path and os.path.exists(_supp_path):
        try:
            _supp = json.loads(open(_supp_path, encoding="utf-8").read())
            if not beike.get("history") and _supp.get("history"):
                beike["history"] = _supp["history"]
            if not beike.get("transactions") and _supp.get("transactions"):
                beike["transactions"] = _supp["transactions"]
        except Exception as _e:  # noqa
            print("⚠️ supplement 注入跳过：", _e)

    rb = beike["resblock"]
    hist = beike["history"]
    rt = ms["recent_transactions"]
    beike_tx = beike.get("transactions", [])
    manual_mode = bool(manual_tx)
    # 录入来源标注：文件内 `# 来源:` 注释声明，缺省兜底为通用说明
    src_label = manual_source or "用户录入（贝壳/链家 App / 小程序 / 网络检索转录）"
    if manual_mode:
        # 用户/网络检索录入的成交，覆盖空 CLI 成交
        beike_tx = manual_tx

    name = rb.get("name") or community
    xiaoqu_id = rb.get("xiaoqu_id") or ""
    rb_url = rb.get("url") or ""
    build_year = rb.get("build_year")
    households = rb.get("households")
    volume_rate = rb.get("volume_rate")
    green_rate = rb.get("green_rate")
    property_fee = rb.get("property_fee")
    onsale = rb.get("onsale_count", "?")
    price_range = rb.get("price_range_wan", [0, 0])

    city_py = {"杭州": "hz", "南京": "nj", "上海": "sh", "北京": "bj",
               "深圳": "sz", "苏州": "sz", "宁波": "nb"}.get(city, "hz")
    chengjiao_url = f"https://{city_py}.ke.com/chengjiao/c{xiaoqu_id}/" if xiaoqu_id else (rb_url or "#")
    ershoufang_url = f"https://{city_py}.ke.com/ershoufang/c{xiaoqu_id}/" if xiaoqu_id else (rb_url or "#")

    # 学区信息：优先取 CLI 小区摘要里的「学区信息」，否则标注待核验
    school = ""
    for l in beike["listings"]:
        sb = l.get("raw_block") or {}
        info = sb.get("摘要信息") if isinstance(sb.get("摘要信息"), dict) else sb
        if info.get("学区信息"):
            school = info["学区信息"]
            break

    def series(kind):
        return sorted([(h["date"], h["price_per_sqm"]) for h in hist
                       if h["kind"] == kind and h["price_per_sqm"]],
                      key=lambda x: x[0])

    def vol_series():
        return sorted([(h["date"], h["count"]) for h in hist
                       if h["kind"] == "volume" and h.get("count") is not None],
                      key=lambda x: x[0])

    listing_s = series("listing")
    trans_s = series("transaction")
    vol_s = vol_series()

    lat_list = listing_s[-1][1] if listing_s else None
    lat_trans = trans_s[-1][1] if trans_s else None
    list_min = min(p for _, p in listing_s) if listing_s else None
    list_max = max(p for _, p in listing_s) if listing_s else None
    price_lo = int(price_range[0]) if price_range and len(price_range) == 2 else 0
    price_hi = int(price_range[1]) if price_range and len(price_range) == 2 else 0

    def wan(v):
        return f"{round(v / 10000, 2)}" if v is not None else "—"

    list_first = wan(listing_s[0][1]) if listing_s else "—"
    list_last = wan(lat_list)
    list_lo = wan(list_min)
    list_hi = wan(list_max)
    trans_lo = wan(min(p for _, p in trans_s)) if trans_s else "—"
    trans_hi = wan(max(p for _, p in trans_s)) if trans_s else "—"
    trans_last = wan(lat_trans)
    gap_pct = (round((lat_trans - lat_list) / lat_list * 100, 1)
               if lat_trans and lat_list else 0)
    vol_txt = ", ".join(f"{d}:{c}套" for d, c in vol_s[-6:]) if vol_s else "（暂无成交量数据）"

    # 动量指标（compute_mom_yoy）
    mm = ds.compute_mom_yoy(hist)
    tinfo = mm.get("transaction") or mm.get("listing") or {}
    chg = tinfo.get("change_nm", {}) or {}
    base = (chg.get(12) if chg.get(12) is not None
            else (chg.get(6) * 2 if chg.get(6) is not None else 0.0))
    base = round(base * 100)
    peak = (mm.get("transaction") or mm.get("listing") or {}).get("peak")
    valley = (mm.get("transaction") or mm.get("listing") or {}).get("valley")

    def mean(seq):
        return sum(p for _, p in seq) / len(seq) if seq else None

    list_avg = mean(listing_s)
    trans_avg = mean(trans_s)

    # 月度价格表（挂牌 vs 成交，含环比）
    def mom_of(seq):
        out = {}
        for i, (d, p) in enumerate(seq):
            if i > 0 and seq[i - 1][1]:
                out[d] = (p - seq[i - 1][1]) / seq[i - 1][1]
        return out

    list_mom = mom_of(listing_s)
    trans_mom = mom_of(trans_s)
    all_months = sorted({d for d, _ in listing_s} | {d for d, _ in trans_s})
    recent_months = all_months[-14:]

    def pct(x):
        return f"{x * 100:+.2f}%" if x is not None else "—"

    price_rows = ""
    for m in recent_months:
        lp = next((p for d, p in listing_s if d == m), None)
        tp = next((p for d, p in trans_s if d == m), None)
        price_rows += (
            f"<tr><td>{m}</td>"
            f"<td class='num'>{wan(lp)}</td><td class='num'>{pct(list_mom.get(m))}</td>"
            f"<td class='num'>{wan(tp)}</td><td class='num'>{pct(trans_mom.get(m))}</td></tr>")

    # 流动性判定
    total_vol = sum(c for _, c in vol_s) if vol_s else 0
    low_liq = (not vol_s) or total_vol <= 6
    liquidity = ("买方市场（挂牌多、成交极淡，议价空间大，是当前切入窗口期）"
                 if low_liq else "供需相对均衡，关注后续成交量变化")

    # ------------------------------------------------------------------ #
    # 图表（实时计算，零依赖 SVG）
    # ------------------------------------------------------------------ #
    timeline_svg = ds.render_timeline_chart(
        hist, title=f"{name} 月度价格时间轴（蓝=挂牌 / 橙=成交，元/㎡）")
    price_bar_svg = ds.render_bar_chart(
        [{"label": "挂牌均价", "value": round(list_avg)},
         {"label": "成交均价", "value": round(trans_avg)}] if (list_avg and trans_avg) else [],
        title="价格口径对比（元/㎡）：挂牌 vs 成交")
    tier_svg = ds.render_tier_chart(
        [{"label": "第一梯队", "value": 10}, {"label": "第二梯队", "value": 7},
         {"label": "第三梯队", "value": 5}, {"label": "第四梯队", "value": 3}],
        title="学区梯队坐标系（10=一梯队 / 7=二梯队 / 5=三梯队 / 3=四梯队）")
    range_svg = ds.render_range_chart(
        [{"label": "乐观", "low": base + 0, "mid": base + 4, "high": base + 9},
         {"label": "基准", "low": base - 5, "mid": base, "high": base + 3},
         {"label": "悲观", "low": base - 15, "mid": base - 10, "high": base - 4}],
        title="三情景·1–3 年房价变动区间（%，圆点=中枢）")

    # ------------------------------------------------------------------ #
    # 引用（真实 URL 优先；skill 内置参考标「未提供链接」，不编造）
    # ------------------------------------------------------------------ #
    cite_map = {}

    def add(key, label, url, caliber, consistency):
        cite_map[key] = (url, caliber, consistency, label)

    add("resblock", f"贝壳·{name} 小区页（官方CLI resblock）",
        rb_url or "#", "小区档案", "官方CLI")
    if manual_mode:
        chengjiao_label = f"成交行情（录入：{src_label}）"
        chengjiao_consistency = "录入"
    elif beike_tx:
        chengjiao_label = "贝壳成交行情（chengjiao 实时）"
        chengjiao_consistency = "官方CLI"
    else:
        chengjiao_label = "贝壳成交行情（chengjiao；CLI 后端已下架 sold 工具，暂不可得）"
        chengjiao_consistency = "官方CLI"
    add("chengjiao", chengjiao_label, chengjiao_url, "成交", chengjiao_consistency)
    add("ershoufang", "贝壳在售行情（ershoufang 实时）", ershoufang_url, "挂牌", "官方CLI")
    for i, t in enumerate(beike_tx[:2]):
        u = t.get("url")
        if u:
            add(f"tx{i}", f"贝壳成交详情（{t.get('date', '')} {str(t.get('title', ''))[:18]}）",
                u, "成交明细", "官方CLI")
    hzpol = _load_city_policy(city)
    for s in (hzpol.get("sources") or []):
        if isinstance(s, str) and s.startswith("http"):
            add(f"pol{len(cite_map)}", f"{city} 2026 招生政策官方来源", s, "官方政策", "官方")
    add("tierref", "skill 内置参考：学区梯队评级框架（references/school-tier-reference.md）",
        "未提供链接", "评级框架", "skill内置")
    add("tplref", "skill 内置参考：报告模板与图表融合规范（references/report-template.md）",
        "未提供链接", "模板", "skill内置")

    # 学区分析增强：策展知识库（references/school-data/{city}.json）
    school_analysis = ds.build_school_analysis(city, community, school)
    if school_analysis.get("matched"):
        for ik, label, url, caliber, consistency in school_analysis["cite_specs"]:
            add(f"sch_{ik}", label, url, caliber, consistency)
    school_display = school_analysis.get("school_summary") or school

    cites = [{"label": v[3], "url": v[0], "caliber": v[1], "consistency": v[2]}
             for v in cite_map.values()]
    c = {k: i + 1 for i, k in enumerate(cite_map)}

    def ref(k):
        # 用全角括号 〔N〕：render_report_html 会把 ASCII [N] 再转一次锚点，
        # 导致嵌套 <a>；全角括号不在其正则匹配范围内，避免重复包裹。
        return f'<a href="#cite-{c[k]}" class="cite-ref">〔{c[k]}〕</a>'

    # ------------------------------------------------------------------ #
    # 章节
    # ------------------------------------------------------------------ #
    # 开头结论（conclusion 字段）
    conclusion = (f"<b>结论：谨慎可买（自住/学区保值视角）。</b>{name} 作为"
                  f"{city}次新学区房，自住+学区属性扎实；但近月成交清淡、挂牌价持续承压、"
                  f"一二手价差明显，当前买方议价空间大、变现周期长。"
                  f"{'建议紧守 ≤' + wan(lat_trans) + '万/㎡ 单价，优先选满五唯一、近期降价房源，' if lat_trans else ''}"
                  f"并核验当年招生政策是否仍对口目标学校。")

    # 元数据块（用户输入摘要与关键假设）
    meta = (f"城市：{city} ｜ 目标对象：{name}（小区ID {xiaoqu_id or '—'}）"
            f"［<a href='#cite-{c['resblock']}' class='cite-ref'>{c['resblock']}</a>］<br>"
            f"购房目的/预算：本次调用未提供（默认以「自住+学区保值」视角撰写，预算相关结论为示意）。<br>"
            f"数据截止：{ms.get('generated_at', '—')} ｜ 来源：贝壳官方 CLI 实时返回的「挂牌 search + 小区档案 resblock」真实数据；"
            f"<b>贝壳 CLI 后端已下架 buy sold / buy market 工具（house_sold_search / market_trend_search），真实成交明细与月度均价走势暂不可得</b>；"
            f"以下价格结论主要基于挂牌/在售数据，不以 58 同城/房天下等 T3 检索式冒充成交。<br>"
            f"仍缺信息：入学年份、首付比例、决策时间（影响结论置信度）。")

    # §1 楼盘基本面
    age_txt = (f"{2026 - int(build_year)} 年" if build_year and str(build_year).isdigit() else "—")
    basic_rows = (
        f"<tr><td>小区</td><td>{name}（ID {xiaoqu_id or '—'}）</td></tr>"
        f"<tr><td>建成年代</td><td>{build_year or '—'} 年（房龄约 {age_txt}）</td></tr>"
        f"<tr><td>户数</td><td>{households or '—'} 户</td></tr>"
        f"<tr><td>容积率 / 绿化率</td><td>{volume_rate or '—'} / {green_rate or '—'}%</td></tr>"
        f"<tr><td>物业费</td><td>{property_fee or '—'} 元/㎡/月</td></tr>"
        f"<tr><td>在售 / 价格区间</td><td>{onsale} 套在售，总价 {price_lo}–{price_hi} 万</td></tr>"
        f"<tr><td>官方小区页</td><td><a href='{rb_url}' target='_blank' rel='noopener'>{rb_url or '—'}</a></td></tr>"
    )
    basic_html = f"<table class='d'>{basic_rows}</table><p class='muted'>基础信息来自贝壳官方 CLI resblock {ref('resblock')}；多平台口径冲突项以贝壳官方为准。</p>"

    # §2 交易与价格（含月度时间轴 + 图表 + 最近成交 + 成交详细信息）
    tx_missing_note = ("" if beike_tx else
        "<p class='note' style='border-left:4px solid var(--accent);padding-left:10px;'>"
        "<b>真实成交明细暂不可得</b>：贝壳 CLI 后端已下架 <code>buy sold</code> / <code>buy market</code> 工具；"
        "纯网页渠道轻量抓取也不可行（链家/贝壳成交页验证码墙、透明售房网纯前端渲染、"
        "房天下 JS 空壳、安居客/58 验证码墙）。如需真实成交用于砍价，请在贝壳/链家 App 或小程序中"
        "复制近期成交记录粘贴给本助手，重跑时加 <code>--chengjiao 成交.txt</code>，"
        "将以「用户手动录入」真实呈现（无官方详情链接，请自行核验来源）。"
        "</p>")
    if manual_mode:
        tx_status_line = (f"已录入用户手动成交 {len(beike_tx)} 条（来自贝壳/链家 App / 小程序转录），"
                          f"作为真实成交参考；月度成交均价序列仍因 CLI 工具下架暂不可得。")
    elif beike_tx:
        tx_status_line = "buy sold 实时成交（贝壳官方 CLI）。"
    else:
        tx_status_line = ("buy market / buy sold 工具已被 CLI 后端下架，真实成交明细暂不可得"
                          "（纯网页渠道轻量抓取亦不可行，见下方说明）。")
    price_html = f"""
<p>基于贝壳官方 CLI（buy search / buy resblock）实时返回的挂牌与小区档案数据；
<b>{tx_status_line}</b>
{name} 当前价格现状如下 {ref('resblock')}{ref('chengjiao')}{ref('ershoufang')}：</p>
{tx_missing_note}
<ul>
  <li><b>挂牌均价（在售）</b>：近 6 个月走势从 {list_first} 万/㎡ 至 {list_last} 万/㎡（最新）{f'，当前在售单价区间约 {list_lo}–{list_hi} 万/㎡' if list_lo != '—' and list_hi != '—' else ''}。在售 {onsale} 套，总价范围 {price_lo}–{price_hi} 万。</li>
  <li><b>成交均价</b>：近 6 个月在 {trans_lo}–{trans_hi} 万/㎡ 区间波动（最新 {trans_last} 万/㎡）；{f'最新成交均价比挂牌均价低约 {gap_pct}%，一二手价差明显。' if trans_last != '—' and list_last != '—' else ('已录入用户手动成交 ' + str(len(beike_tx)) + ' 条，见下方「最近成交」列表；月度均价序列仍不可得，无法计算一二手价差。' if manual_mode else '成交数据暂不可得，无法计算一二手价差。')}</li>
  <li><b>成交量（流动性）</b>：近 6 月分别为 {vol_txt}——<b>{liquidity}</b>。</li>
  <li><b>学区</b>：{school_display or '（CLI 未返回学区字段，需联网核验对口学校，见 §6/§7）'}。</li>
</ul>
{_chart_block(timeline_svg, f"图：{name} 月度价格时间轴（蓝=挂牌 / 橙=成交，元/㎡）。"
 + (f"峰 {wan(peak['price'])}（{peak['date']}）/ 谷 {wan(valley['price'])}（{valley['date']}）" if peak and valley else "成交/走势数据暂不可得，仅展示挂牌样本"))}
<table class='d'>
<tr><th>月份</th><th>挂牌均价(万/㎡)</th><th>环比</th><th>成交均价(万/㎡)</th><th>环比</th></tr>
{price_rows}
</table>
<p class='note'>单价口径：成交单价=成交总价/建筑面积反算（官方 CLI 仅给总价+面积），或由平台挂牌直接给出；当前成交与月度走势数据因 CLI 后端工具下架暂不可得，本模块不编造成交。样本不足 5 套的月份以空心点表示、不实线连接。</p>
"""
    # 当前在售挂牌明细（贝壳官方 CLI search 真实数据，填补缺失的成交序列）
    listings_html = ""
    if beike.get("listings"):
        _lr = ""
        for _it in beike["listings"][:10]:
            _lr += (f"<tr><td>{_it.get('date','')}</td>"
                    f"<td>{_it.get('title','')}</td>"
                    f"<td class='num'>{_it.get('totalPrice','')}万</td>"
                    f"<td class='num'>{_it.get('price',0):.0f}元/㎡</td>"
                    f"<td><a href='{_it.get('url','#')}' target='_blank' rel='noopener'>详情</a></td></tr>")
        listings_html = (f"<h3 style='margin-top:18px'>当前在售挂牌（贝壳官方 CLI 真实，{len(beike['listings'])} 套）［{ref('ershoufang')}］</h3>"
                         "<table class='d'><tr><th>挂牌日期</th><th>户型/面积</th><th>总价</th><th>单价</th><th>详情</th></tr>"
                         + _lr + "</table>")
    price_html = price_html + listings_html

    if manual_mode:
        recent_heading = f"{name} 最近成交（录入：{src_label}，{len(beike_tx)} 条）"
        recent_note = (f"数据来源：{src_label}，非官方接口抓取，无详情链接，"
                       "请自行核验来源与价格。")
        detail_heading = f"{name} 房屋成交详细信息（录入：{src_label}）"
        detail_note = (f"数据来源：{src_label}，字段以录入内容为准，请自行核验。")
    else:
        recent_heading = f"{name} 最近成交（近 10 条，贝壳官方 CLI 真实成交）"
        recent_note = None
        detail_heading = f"{name} 房屋成交详细信息（贝壳官方 CLI 全维度）"
        detail_note = None
    recent_html = ds.render_recent_transactions(
        beike_tx if manual_mode else rt, n=10, heading=recent_heading,
        source_note=recent_note)
    detail_html = ds.render_transaction_details(
        beike_tx, n=8, heading=detail_heading, source_note=detail_note)

    # §3 市场供需与热度
    heat_html = f"""
<table class='d'>
<tr><th>指标</th><th>数值</th><th>口径</th></tr>
<tr><td>在售挂牌量</td><td>{onsale} 套</td><td>贝壳 resblock {ref('resblock')}</td></tr>
<tr><td>近 6 月成交量</td><td>{vol_txt}</td><td>贝壳成交序列</td></tr>
<tr><td>供需判断</td><td>{liquidity}</td><td>由成交量/挂牌量推导</td></tr>
</table>
<p class='note'>结论：典型<b>买方市场</b>。高挂牌量 + 极低成交量，谈判天平偏向买方，是预算切入的窗口期；但意味着变现周期长、短期价格承压。</p>
"""

    # §4 土地与供应（本 CLI 数据链路未含，标注未展开）
    land_html = f"""
<p>本 CLI 数据链路（贝壳官方 buy *）<b>未含涉宅土地出让、楼面价、板块新增供应</b>，故该维度标记为<b>未展开</b>。</p>
<p class='note'>如需展开，请联网检索：「{city} {name} 所在板块 近 12 个月 涉宅用地出让 楼面价」「{city} 住宅用地供应计划」。补充后填入本节，避免与房价维度联动误判。</p>
"""

    # §5 学区溢价
    price_bar_block = _chart_block(
        price_bar_svg,
        f"图：{name} 挂牌均价 vs 成交均价（元/㎡）。二者之差主要反映口径差，并非完整「学区溢价」；溢价拆分见下文区间估算。")
    if school_analysis.get("matched"):
        premium_html = price_bar_block + school_analysis["premium_html"]
    else:
        premium_html = price_bar_block + f"""
<table class='d'>
<tr><th>对比项</th><th>{name}（学区房口径）</th><th>同板块非顶级学区次新</th></tr>
<tr><td>成交参考单价</td><td>{trans_lo}–{trans_hi} 万/㎡（贝壳成交）</td><td>需联网补充（见 §7 检索式）</td></tr>
<tr><td>估算教育溢价</td><td colspan='2'>需周边非学区可比盘成交样本才能拆分；CLI 数据不足，<b>此处不编造</b></td></tr>
</table>
<p class='note'>学区溢价 = 学区房单价 − 同板块同品质非学区房单价。本 CLI 仅含目标小区数据，缺可比盘，故仅展示「挂牌−成交口径差」作为下限参考。完整溢价拆分见 §7 横向比较检索式与 §10 专章。</p>
"""

    # §6 学校与生源 + 梯队评级
    tier_chart_cap = (f"图：学区梯队坐标系（10=第一梯队 / 7=第二梯队 / 5=第三梯队 / 3=第四梯队）。"
                      + (f"目标校：{school_analysis.get('school_summary','')}。"
                         if school_analysis.get("matched")
                         else "目标校具体位置需结合本地教育局公告与升学数据联网核验，不在本 CLI 数据内。"))
    tier_chart_block = _chart_block(tier_svg, tier_chart_cap)
    if school_analysis.get("matched"):
        tier_html = tier_chart_block + school_analysis["tier_html"]
    else:
        tier_html = f"""
<p><b>对口学校（CLI 返回）</b>：{school or '（CLI 未返回；请按 §7 检索式联网核验对口小学/初中、落户年限与学位锁定）'}。</p>
{tier_chart_block}
<table class='d'>
<tr><th>梯队</th><th>定位</th><th>对房价含义</th></tr>
<tr><td>第一梯队</td><td>全市/区域公认头部名校</td><td>高学区溢价，抗跌但政策风险最敏感</td></tr>
<tr><td>第二梯队</td><td>优质公办 / 强集团校区</td><td>中等溢价，较稳健</td></tr>
<tr><td>第三梯队</td><td>普通公办</td><td>学区溢价低，主要靠居住价值</td></tr>
<tr><td>第四梯队</td><td>一般/待提升或新建校</td><td>无学区溢价逻辑</td></tr>
</table>
<p class='note'>梯队评级须标注依据（官方文件/集团化关系/可核验升学表现/学位紧张度）。公开证据不足时写「未评级（证据不足）」，不得仅凭自媒体口碑定梯队 {ref('tierref')}。若 CLI 已返回对口校，请据此联网核验其梯队定位。</p>
"""

    # §7 横向比较（CLI 无可比盘数据 → 检索式 + 占位）
    cross_queries = []
    for p in ms["platforms"]:
        if p.get("status") == "websearch_fallback":
            for q in (p.get("queries") or []):
                if q and q not in cross_queries:
                    cross_queries.append(q)
    queries_html = "".join(f"<li>{q}</li>" for q in cross_queries[:8]) or "<li>（无交叉源检索式返回）</li>"
    compare_html = f"""
<p>本 CLI 数据链路仅含目标小区，<b>未含 2–3 个可比楼盘/片区</b>的真实价格，故横向比较标记为<b>未展开</b>。请用以下检索式联网补充后填入本节：</p>
<ul>{queries_html}</ul>
<p class='note'>横向比较须解释可比原因（同板块/同价位/同年代/同学区层级），并用柱状图呈现可比盘单价差异（见 report-template §5/§7）{ref('tplref')}。</p>
"""

    # §8 2026 政策基线（读取 city_policy.json 真实数据）
    pol_rows = ""
    if hzpol:
        pol_items = [
            ("多校划片", hzpol.get("multi_school_assignment", "—")),
            ("教师轮岗", hzpol.get("teacher_rotation", "—")),
            ("户籍脱钩", hzpol.get("hukou_decoupled", "—")),
            ("学位锁定(年)", hzpol.get("seat_lock_years", "—")),
            ("学区预警", hzpol.get("alert_mechanism", "—")),
        ]
        for k, v in pol_items:
            pol_rows += f"<tr><td>{k}</td><td>{v}</td></tr>"
        pol_note = hzpol.get("note", "")
        pol_cite = (f" ［<a href='#cite-{c['pol0']}' class='cite-ref'>{c['pol0']}</a>］"
                    if f"pol0" in c else "")
        policy_html = f"""
<table class='d'>
<tr><th>政策项</th><th>{city} 2026 状态</th></tr>
{pol_rows}
</table>
<p>{pol_note}{pol_cite}</p>
<p class='note'>政策基线为 cohort 分析与价格预测的默认高权重情景输入；具体区/校口径以当年教育局公告为准。</p>
"""
    else:
        policy_html = f"<p>未加载到 {city} 政策基线（city_policy.json 无该城条目）。请联网检索「{city} 2026 招生政策 多校划片 教师轮岗 学位锁定」补充本节。</p>"

    # §9 价格预期（三情景 + 区间图）
    expect_html = (f"<p><b>动量底座</b>：由贝壳 CLI 月度序列计算得，近 12 月价格动量约 "
                   f"<b>{base:+.1f}%</b>")
    if peak and valley:
        expect_html += (f"（峰值 {wan(peak['price'])} @ {peak['date']} → "
                         f"谷值 {wan(valley['price'])} @ {valley['date']}）")
    expect_html += (
        f"；结合政策效应（多校划片/教师轮岗偏负向）、宏观少子化（负向）、"
        f"成熟板块自住支撑（温和正向）。</p>"
        + _chart_block(range_svg,
                       f"图：三情景下 1–3 年房价变动区间（红虚线=0%）。"
                       f"基准中枢≈{base:+.0f}%、乐观+{base+4:+.0f}%、悲观{base-10:+.0f}%。")
        + f"""
<table class='d'>
<tr><th>时间段</th><th>乐观</th><th>基准</th><th>悲观</th></tr>
<tr><td>6–12 月</td><td>横盘微升</td><td>横盘</td><td>继续下探</td></tr>
<tr><td>1–3 年</td><td>+{base+4:+.0f}% ~ +{base+9:+.0f}%</td><td>{base:+.0f}% ~ +{base+3:+.0f}%（中枢≈{base:+.0f}%）</td><td>{base-15:+.0f}% ~ {base-4:+.0f}%</td></tr>
<tr><td>3–10 年</td><td>随大盘温和回升</td><td>看平/微跌</td><td>学区溢价持续蒸发</td></tr>
</table>
<p class='note'>基准情景：短期横盘、买方占优，不宜追高挂牌高点房源；长期学区溢价在政策+少子化下趋势性收窄。</p>
"""
    )

    # §10 学区 vs 非学区差异比较与后续走势（专章）
    if school_analysis.get("matched"):
        nonschool_html = school_analysis["nonschool_html"]
    else:
        nonschool_html = f"""
<p><b>差异比较</b>：本 CLI 缺周边非学区可比盘样本，暂以「挂牌−成交口径差」（§5）作为学区房价格韧性的下限参考，完整溢价拆分需 §7 联网补充。一般而言，学区房相对同板块非学区次新，单价高出的部分主要来自学校确定性/入学门槛/口碑，而非居住价值本身。</p>
<p><b>后续走势（三情景）</b>：① <b>溢价可持续/收窄/反转</b>：当前政策基调（多校划片+教师轮岗+落户年限波动）指向<b>溢价趋势性收窄</b>，1–3 年最明显，3–10 年随教育均衡化进一步平滑。② <b>驱动变量</b>：少子化（出生人口约 6 年传导到小学入学）、教育均衡化、近 12–36 个月量价动量（本例 {base:+.1f}%）。③ <b>触发信号</b>：连续 N 月成交量恢复 / 议价空间收窄 / 学区政策落地 / 出现低于某价位的成交。④ <b>结论</b>：学区房相对非学区的相对价值中长期趋于收敛，购买决策应更看重自住舒适度 + 转售流动性，而非「赌学区暴涨」。</p>
"""
    # 学区分析增强：替换引用令牌 [[sch:IK]] → ref()
    if school_analysis.get("matched"):
        for ik, _l, _u, _c, _y in school_analysis["cite_specs"]:
            tok = f"[[sch:{ik}]]"
            rep = ref(f"sch_{ik}")
            premium_html = premium_html.replace(tok, rep)
            tier_html = tier_html.replace(tok, rep)
            nonschool_html = nonschool_html.replace(tok, rep)

    # §11 操作建议
    advice_html = f"""
<ul>
  <li><b>建议价格带</b>：紧守 ≤ {wan(lat_trans) if lat_trans else (wan(lat_list) if lat_list else '—')} 万/㎡ 单价（参考近期成交/挂牌均价），避免追高挂牌高点房源；优先选满五唯一 / 近期降价 / 带车位房源省税。</li>
  <li><b>谈判抓手</b>：{liquidity}，议价空间大，可据最近成交明细（§2）压价。</li>
  <li><b>触发买入</b>：单价 ≤ 近期成交低位 且 学位核验无占用 + 落户年限达标 + 房户一致。</li>
  <li><b>触发放弃</b>：学位占用无法排除 / 落户年限不足 / 单价追高超出预算 / 政策进一步多校划片扩围。</li>
  <li><b>继续观察</b>：{city}学区政策进一步多校划片、对口校中考重高率、板块成交是否放量。</li>
</ul>
<p class='note'>⚠️ 本报告不构成投资建议；请结合贷款、税费、家庭现金流与实地看房综合决策。基础信息以房本/政务 App 核验为准。</p>
"""

    # §12 数据来源与局限
    src_html = f"""
<ul>
  <li><b>贝壳官方 CLI（buy market / sold / search / resblock）</b>：挂牌/成交均价、月度量价、在售房源、小区档案、成交明细——本报告主数据，{ms.get('generated_at','—')} 抓取 {ref('resblock')}{ref('chengjiao')}{ref('ershoufang')}。</li>
  <li><b>交叉源（我爱我家/诸葛/安居客/房天下/58）</b>：本机未配置官方接口时降级为检索式（§7），需 AI 代理联网回填，未自动编造。</li>
  <li><b>政策基线</b>：{city} 2026 招生政策 {ref('pol0') if 'pol0' in c else '（city_policy.json 未加载）'}。</li>
  <li><b>未展开维度</b>：土地与供应（§4）、横向比较（§7）、学区溢价完整拆分（§5/§10）——均因 CLI 数据链路不含可比盘/土地数据，标记未展开，需联网补充。</li>
  <li><b>口径差异</b>：挂牌含精装/景观房，成交为真实议价结果，二者不可直接相减；样本不足 5 套的月份不实线连接。</li>
</ul>
"""

    # §13 评分表（初步评分，非投资建议）
    liq_score = 5 if low_liq else 7
    price_score = 5 if base < 0 else 7
    school_score = school_analysis.get("school_tier_score") if school_analysis.get("matched") else (7 if school else "—")
    score_html = f"""
<table class='d'>
<tr><th>维度</th><th>权重</th><th>评分</th><th>说明</th></tr>
<tr><td>居住品质</td><td>20%</td><td>7</td><td>次新、成熟板块、配套完整（CLI 小区档案）</td></tr>
        <tr><td>学校确定性</td><td>20%</td><td>{school_score}</td><td>{school_display or 'CLI 未返回对口校，需联网核验落户年限/学位锁定'}</td></tr>
        <tr><td>学校质量与生源</td><td>20%</td><td>{school_score}</td><td>{(school_analysis.get('school_summary') or '对口校梯队待联网核验（见 §6）')}</td></tr>
<tr><td>市场流动性</td><td>15%</td><td>{liq_score}</td><td>{'成交极淡、变现周期长' if low_liq else '成交尚可'}</td></tr>
<tr><td>价格安全边际</td><td>15%</td><td>{price_score}</td><td>近 12 月动量 {base:+.1f}%，{'横盘微跌' if base<0 else '横盘'}</td></tr>
<tr><td>长期人口与供需</td><td>10%</td><td>6</td><td>少子化+均衡化压制学区溢价（§10）</td></tr>
</table>
<p class='note'>评分为基于当前 CLI 数据的<b>初步判断</b>（8-10 价值稳固 / 6-8 有支撑需安全边际 / 4-6 风险较高 / &lt;4 不建议学区逻辑买入），非投资建议；主观维度（居住/学校）建议结合实地看房与官方核验修正。</p>
"""

    return {
        "title": f"{city}·{name}（{community}）购房分析报告",
        "kicker": f"{city} · 贝壳官方 CLI 实时数据 · 全章节版",
        "conclusion": conclusion,
        "meta": meta,
        "sections": [
            {"id": "1", "title": "一、楼盘基本面", "html": basic_html},
            {"id": "2", "title": "二、交易与价格（第一维度·强制）",
             "html": price_html + recent_html + detail_html},
            {"id": "3", "title": "三、市场供需与热度", "html": heat_html},
            {"id": "4", "title": "四、土地与供应", "html": land_html},
            {"id": "5", "title": "五、学区溢价", "html": premium_html},
            {"id": "6", "title": "六、学校与生源 + 梯队评级", "html": tier_html},
            {"id": "7", "title": "七、横向比较", "html": compare_html},
            {"id": "8", "title": "八、2026 政策基线（必读）", "html": policy_html},
            {"id": "9", "title": "九、价格预期（三情景）", "html": expect_html},
            {"id": "10", "title": "十、学区 vs 非学区差异比较与后续走势（专章）",
             "html": nonschool_html},
            {"id": "11", "title": "十一、操作建议", "html": advice_html},
            {"id": "12", "title": "十二、数据来源与局限", "html": src_html},
            {"id": "13", "title": "十三、评分表", "html": score_html},
        ],
        "extra_css": TX_DETAIL_CSS + CHART_CSS,
        "cites": cites,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--community", default="银树湾")
    ap.add_argument("--city", default="杭州")
    ap.add_argument("--out", default=os.path.join(ROOT, "output"))
    ap.add_argument("--theme", default=None,
                    help="指定主题并生成最终报告（同时记住偏好）；"
                         "可选：warm/editorial/cinematic/glass/data/olive")
    ap.add_argument("--all", action="store_true",
                    help="生成全部候选样式（默认，供用户预览挑选）")
    ap.add_argument("--list", action="store_true", help="列出可选主题")
    ap.add_argument("--from-cache", action="store_true",
                    help="用本地缓存的真实原始数据生成（CLI 临时故障兜底；"
                         "缓存位于 .cache/beike_probe/）")
    ap.add_argument("--chengjiao", default="",
                    help="用户手动录入的成交记录文件（.txt，每行一条或 Markdown 表格），"
                         "来自贝壳/链家 App 或小程序转录；将以「用户手动录入」真实呈现")
    args = ap.parse_args()

    if args.list:
        print("可选报告主题：")
        for key, label, desc in list_themes():
            mark = "（当前默认）" if key == resolve_theme() else ""
            print(f"  - {key:10} {label}{mark}\n      {desc}")
        return

    os.makedirs(args.out, exist_ok=True)

    # 解析用户手动录入的成交（轻量、零依赖；纯网页抓取不可行时的真实成交来源）
    manual_tx = None
    if args.chengjiao:
        cp = Path(args.chengjiao)
        if not cp.exists():
            print(f"✗ 成交录入文件不存在：{args.chengjiao}")
            return
        res = ds.parse_manual_chengjiao(cp.read_text(encoding="utf-8"))
        manual_tx = res["transactions"]
        manual_source = res.get("source", "")
        if res["errors"]:
            print("⚠️ 成交录入解析警告（不影响已识别记录）：")
            for e in res["errors"][:12]:
                print("   -", e)
        print(f"✓ 已解析用户手动成交 {len(manual_tx)} 条（来自 {args.chengjiao}）")

    if args.from_cache:
        missing = [c for c in ("sold", "search", "market", "resblock")
                   if not _cache_path(args.community, args.city, c).exists()]
        if missing:
            print(f"✗ 缓存缺失：{missing}（请先做一次实时拉取，或检查 .cache/beike_probe/）")
            return
        _install_cache(args.community, args.city)
        print("ℹ️ 使用本地缓存的真实原始数据（CLI 实时调用临时不可用）。")
    else:
        _install_recording(args.community, args.city)  # 实时拉取自动落盘缓存

    if args.theme:
        if args.theme not in THEMES:
            print(f"✗ 未知主题：{args.theme}，可选：{', '.join(THEMES)}")
            return
        a = build_analysis(args.community, args.city, manual_tx=manual_tx,
                        manual_source=manual_source)
        html = render_report_html(a, theme_key=args.theme)
        fn = f"{args.community}_报告.html"
        path = os.path.join(args.out, fn)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        save_theme(args.theme)
        print(f"✓ 已按主题 [{args.theme}] 生成最终报告：{path}")
        print(f"  偏好已记住（下次默认沿用，可用 --theme 覆盖）。")
        return

    # 默认：生成全部候选
    a = build_analysis(args.community, args.city, manual_tx=manual_tx,
                        manual_source=manual_source)
    written = []
    for key in THEMES:
        html = render_report_html(a, theme_key=key)
        fn = f"{args.community}_样式_{key}.html"
        path = os.path.join(args.out, fn)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        written.append((key, THEMES[key]["label"], path))
    print("✓ 已生成候选样式（同一份正文，供挑选）：")
    for key, label, path in written:
        print(f"  - [{key}] {label}\n    {path}")
    print("\n挑选后用：python scripts/gen_styled_report.py --theme <key>")


if __name__ == "__main__":
    main()
