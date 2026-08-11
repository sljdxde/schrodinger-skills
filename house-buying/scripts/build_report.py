#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 v2 购房分析报告升级为 v3：可点击引用锚点 + 章节内嵌图表。

复用 scripts/data_sources.py 的 render_citations / render_tier_chart /
render_bar_chart / render_range_chart。仅 stdlib 依赖。

说明：图表数据为「南京·万寿万象汇」目标专属，换分析标的时改 CITES / CHARTS 即可。
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_sources as ds  # noqa: E402

SKILL_DIR = Path(__file__).resolve().parents[1]
INPUT = SKILL_DIR / "output" / "南京万寿万象汇购房分析.html"

# --------------------------------------------------------------------------- #
# 15 条参考资料（与 v2 一致，render_citations 会自动生成 id="cite-N"）
# --------------------------------------------------------------------------- #
CITES = [
    {"label": "栖霞区2025公办初中施教区范围（伯乐中学含万象天地，docx）",
     "url": "https://www.njqxq.gov.cn/qxqrmzf/202505/P020250516623633494215.docx"},
    {"label": "栖霞区2025初中招生实施办法（学位占用/落户规则）",
     "url": "https://www.njqxq.gov.cn/qxqrmzf/202505/t20250516_5564170.html"},
    {"label": "栖霞区2026义务教育招生问答",
     "url": "https://www.njqxq.gov.cn/qxqrmzf/202605/t20260518_5842097.html"},
    {"label": "晓庄小学2026新生招生公告（施教区含华荟花园）",
     "url": "http://www.njsxzxx.cn/id365775.html"},
    {"label": "晓庄小学素质教育督导自评报告",
     "url": "http://www.njsxzxx.cn/id333495.html"},
    {"label": "栖霞区政府对晓庄小学综合督导报告",
     "url": "https://www.njqxq.gov.cn/qxqrmzf/202410/t20241014_4785159.html"},
    {"label": "伯乐中学官网简介",
     "url": "http://njblzx.site.qxteacher.com/id9077.html"},
    {"label": "伯乐中学2019中考数据（校方发文，搜狐）",
     "url": "https://www.sohu.com/a/392976683_756476"},
    {"label": "我爱我家·华荟花园小区页（房价/在售/在租）",
     "url": "https://nj.5i5j.com/xq_news/200011958.html"},
    {"label": "58同城·华荟花园房价月度走势",
     "url": "https://nj.58.com/xinfang/xq104713802-fangjia.html"},
    {"label": "安居客·华荟花园小区页",
     "url": "https://m.anjuke.com/nj/community/1631284/"},
    {"label": "克而瑞/新浪财经·2025年南京房地产市场分析",
     "url": "https://finance.sina.cn/2026-03-18/detail-inhrkwsv9350119.d.html"},
    {"label": "南京市政府·房七条/首付15%政策答复",
     "url": "https://www.nanjing.gov.cn/xxgkn/jytabljggk/2025njytabl/shirddbjy/202512/t20251205_5706163.html"},
    {"label": "贝壳·万寿板块房价（青秀城/万寿花苑/依云华府）",
     "url": "https://m.ke.com/nj/xiaoqu/1413985091455763/"},
    {"label": "现代快报·城北万象汇2023.12.15开业",
     "url": "https://www.xdkb.net/rd/450144"},
]

# --------------------------------------------------------------------------- #
# 三张内嵌图表（章节融合，非独立图表章）
# --------------------------------------------------------------------------- #
TIER_SVG = ds.render_tier_chart(
    [
        {"label": "拉力琅（一梯队）", "value": 10},
        {"label": "晓庄小学", "value": 7},
        {"label": "伯乐中学", "value": 7},
    ],
    title="学区梯队指数对比（10=一梯队 / 7=二梯队 / 5=三梯队 / 3=四梯队）",
)

# 柱状图：可比盘挂牌均价（元/㎡）。柱顶标签后处理成「万」。
BAR_RAW = ds.render_bar_chart(
    [
        {"label": "华荟花园", "value": 28500},
        {"label": "青秀城", "value": 23300},
        {"label": "依云华府", "value": 21750},
        {"label": "万寿花苑", "value": 17400},
    ],
    title="同板块可比盘挂牌均价（元/㎡）",
)
_BAR_FIX = {28500: "2.85万", 23300: "2.33万", 21750: "2.18万", 17400: "1.74万"}
for raw, wan in _BAR_FIX.items():
    BAR_RAW = BAR_RAW.replace(f">{raw}</text>", f">{wan}</text>")

RANGE_SVG = ds.render_range_chart(
    [
        {"label": "乐观", "low": 0, "mid": 2.5, "high": 5},
        {"label": "基准", "low": -5, "mid": -2.5, "high": 0},
        {"label": "悲观", "low": -15, "mid": -12.5, "high": -10},
    ],
    title="三情景·1–3 年房价变动区间（%，中枢=圆点）",
)


def chart_block(svg: str, caption: str) -> str:
    return (f'<div class="chartbox">\n{svg}\n'
            f'<div class="caption">{caption}</div>\n</div>\n')


TIER_BLOCK = chart_block(
    TIER_SVG,
    "图：目标对口校（晓庄小学、伯乐中学，均第二梯队）与全市头部「拉力琅」系（第一梯队）"
    "的梯队指数对比。差距直观显示本项目属栖霞区级优质、非全市头部。",
)

BAR_BLOCK = chart_block(
    BAR_RAW,
    "图：同板块可比盘挂牌均价对比（元/㎡）。华荟花园比同施教区的依云华府高约 3,200–5,100 "
    "元/㎡、比青秀城高约 5 千，价差主要来自次新+万象汇商业，而非教育溢价（见 §5/§9）。",
)

RANGE_BLOCK = chart_block(
    RANGE_SVG,
    "图：三情景下 1–3 年房价变动区间（红色虚线=0%）。基准中枢约 -2.5%、乐观 +2.5%、悲观 -12.5%；"
    "短期买方占优，不宜追高（见 §8 表格）。",
)


def main() -> int:
    html = INPUT.read_text(encoding="utf-8")

    # 1) 重建底部引用列表，带 id="cite-N" 与真实 URL
    new_cites = ds.render_citations(CITES)
    html = re.sub(r'<ol class="cites">.*?</ol>', new_cites, html, flags=re.S)
    assert 'id="cite-1"' in html, "引用列表未生成 cite-N 锚点"

    # 2) 内联 <sup>[N]</sup> -> 可点击锚点 <a href="#cite-N" class="cite-ref">
    def repl_sup(m):
        nums = re.findall(r"\d+", m.group(1))
        return "".join(
            f'<a href="#cite-{n}" class="cite-ref">[{n}]</a>' for n in nums
        )
    html = re.sub(
        r"<sup>(\[\d+\](?:\[\d+\])*)</sup>", repl_sup, html
    )

    # 3) CSS：去 sup a，改 .cite-ref
    html = html.replace(
        "sup a{color:var(--olive);text-decoration:none;font-weight:600}",
        ".cite-ref{color:var(--olive);text-decoration:none;font-size:.85em;"
        "vertical-align:super;font-weight:600}\n"
        ".cite-ref:hover{text-decoration:underline}",
    )

    # 4) 嵌入图表到对应章节（章节融合，非独立图表章）
    assert '<h2>4. 学区确定性' in html
    html = html.replace('<h2>4. 学区确定性', TIER_BLOCK + '<h2>4. 学区确定性', 1)

    assert '<h2>8. 价格预期（三情景）' in html
    html = html.replace('<h2>8. 价格预期（三情景）', BAR_BLOCK + '<h2>8. 价格预期（三情景）', 1)

    assert '<h2>9. 学区 vs 非学区差异比较与后续走势（专章）' in html
    html = html.replace(
        '<h2>9. 学区 vs 非学区差异比较与后续走势（专章）',
        RANGE_BLOCK + '<h2>9. 学区 vs 非学区差异比较与后续走势（专章）',
        1,
    )

    # 校验
    leftover_sup = re.findall(r"<sup>", html)
    assert not leftover_sup, f"仍有 {len(leftover_sup)} 处 <sup> 未转换"
    assert "__" not in html, "存在未替换占位符"
    # 所有锚点引用都有对应 id
    ref_nums = set(re.findall(r'href="#cite-(\d+)"', html))
    id_nums = set(re.findall(r'id="cite-(\d+)"', html))
    missing = ref_nums - id_nums
    assert not missing, f"锚点缺失对应 id: {missing}"
    # 单文件自包含：无外链图片、无本地绝对路径
    assert "http://" not in html or True  # 允许引用链接为 http(s) 外链（溯源用途）
    assert '<img' not in html, "不应有外链/本地图片"
    assert re.search(r'src="(?!#)', html) is None, "不应有非锚点 src"

    INPUT.write_text(html, encoding="utf-8")
    print(f"✓ v3 已写出：{INPUT}")
    print(f"  内联可点击引用锚点：{len(ref_nums)} 处")
    print(f"  底部引用 id 锚点：{len(id_nums)} 个")
    print(f"  嵌入图表：tier(§3) / bar(§7) / range(§8) 各 1 张")
    print(f"  残留 <sup>：{len(leftover_sup)} 处 ｜ 占位符：{'无' if '__' not in html else '有'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
