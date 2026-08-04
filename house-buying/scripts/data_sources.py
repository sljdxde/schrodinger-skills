#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""杭州购房分析取数与学区工作流助手（house-buying skill）。

本脚本只做「编排与计划 + 取数适配」，不替用户下决策。真实数据来自两条通道：

1) 抓包 API 模式（推荐，数据最稳）
   微信小程序（杭房数研 / 小鸡选房）是封闭生态，没有公开网页 API。
   取数做法是：在手机上用 mitmproxy / Charles 对微信抓包，拿到小程序调用后端时
   的 HTTPS 接口（endpoint）和登录态（token / cookie），填进 `sources.json`，
   本脚本即可脚本化拉取结构化挂盘价 / 成交价。
   抓包一次，长期复用。

2) 联网检索兜底模式（默认）
   没有配置 endpoint/token 时，脚本会生成「精确到小程序名」的检索式，
   由 AI 代理用 WebSearch / WebFetch 取数，再把结果回填。

学区工作流（用户定义的流程）：
   选学区 -> 找到学区下所有小区（区分回迁房 / 商品房）-> 按小区平均挂牌价排序
   -> 用用户预算过滤 -> 去不同数据源拉取房源信息并分析
   若用户直接给小区（可多个）-> 跳过发现/排序，直接拉取分析
   最后 -> 给出学区 vs 周边非学区房价差异比较，并分析后续走势

依赖：仅标准库。Python 3.9+。
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import urllib.request
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

SKILL_DIR = Path(__file__).resolve().parents[1]
SOURCES_CONFIG = SKILL_DIR / "scripts" / "sources.json"


# --------------------------------------------------------------------------- #
# 数据结构
# --------------------------------------------------------------------------- #
@dataclass
class Community:
    name: str
    district: str = ""
    school: str = ""
    # commodity=商品房, resettlement=回迁房, unknown=未区分
    housing_type: str = "unknown"
    avg_listing_price: Optional[float] = None  # 元/㎡
    listing_count: Optional[int] = None
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "district": self.district,
            "school": self.school,
            "housing_type": self.housing_type,
            "avg_listing_price": self.avg_listing_price,
            "listing_count": self.listing_count,
            "note": self.note,
        }


@dataclass
class PriceSample:
    community: str
    price_per_sqm: float
    total_price: Optional[float] = None
    area: Optional[float] = None
    deal_date: str = ""
    source: str = ""
    kind: str = "listing"  # listing=挂牌, transaction=成交

    def to_dict(self) -> dict:
        return {
            "community": self.community,
            "price_per_sqm": self.price_per_sqm,
            "total_price": self.total_price,
            "area": self.area,
            "deal_date": self.deal_date,
            "source": self.source,
            "kind": self.kind,
        }


@dataclass
class SourceFetchResult:
    source: str
    community: str
    listings: list = field(default_factory=list)
    transactions: list = field(default_factory=list)
    queries: list = field(default_factory=list)
    raw_note: str = ""
    confidence: str = "low"
    mode: str = "websearch"  # api / websearch

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "community": self.community,
            "listings": [s.to_dict() for s in self.listings],
            "transactions": [s.to_dict() for s in self.transactions],
            "queries": self.queries,
            "raw_note": self.raw_note,
            "confidence": self.confidence,
            "mode": self.mode,
        }


# --------------------------------------------------------------------------- #
# 数据源适配器
# --------------------------------------------------------------------------- #
class BaseSource:
    name = "base"
    kind = "mini_program"  # mini_program / web
    # 该源主力提供什么口径
    provides = "listing"  # listing / transaction / both

    def __init__(self, cfg: Optional[dict] = None):
        self.cfg = cfg or {}

    @property
    def endpoint(self) -> Optional[str]:
        return self.cfg.get("endpoint")

    @property
    def token(self) -> Optional[str]:
        return self.cfg.get("token")

    def can_api(self) -> bool:
        return bool(self.endpoint and self.token)

    def fetch(self, community: str, district: str = "") -> SourceFetchResult:
        if self.can_api():
            try:
                return self._fetch_api(community, district)
            except Exception as exc:  # 兜底回检索
                res = self._fetch_websearch(community, district)
                res.raw_note = f"API 拉取失败({exc})，已退回联网检索模式。{res.raw_note}"
                return res
        return self._fetch_websearch(community, district)

    # ---- API 模式：子类实现具体接口 ----
    def _fetch_api(self, community: str, district: str) -> SourceFetchResult:
        raise NotImplementedError

    # ---- 检索模式：默认生成精确检索式 ----
    def _fetch_websearch(self, community: str, district: str) -> SourceFetchResult:
        queries = self.search_queries(community, district)
        return SourceFetchResult(
            source=self.name,
            community=community,
            queries=queries,
            raw_note="未配置接口，请按上述检索式联网取数后回填 listings/transactions。",
            confidence="low",
            mode="websearch",
        )

    def search_queries(self, community: str, district: str) -> list:
        raise NotImplementedError

    # 通用：对返回 JSON 做「宽容解析」，兼容不同字段命名
    def _request_json(self, url: str, headers: Optional[dict] = None) -> dict:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))

    @staticmethod
    def _extract_rows(obj) -> list:
        """从常见 JSON 形状里抽取记录数组。"""
        if isinstance(obj, list):
            return obj
        if isinstance(obj, dict):
            for key in ("data", "list", "items", "records", "communityList",
                        "result", "rows", "content"):
                v = obj.get(key)
                if isinstance(v, list) and v:
                    return v
            if "data" in obj and isinstance(obj["data"], dict):
                for key in ("list", "items", "records", "communityList", "rows"):
                    v = obj["data"].get(key)
                    if isinstance(v, list) and v:
                        return v
        return []

    @staticmethod
    def _to_float(val) -> Optional[float]:
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        try:
            return float(str(val).replace(",", "").replace("万", "0000")
                         .replace("元", "").replace("㎡", "").strip())
        except ValueError:
            return None


class HangfangSource(BaseSource):
    """杭房数研（微信小程序）：杭州每日新房/二手房签约、各小区成交价、一年量价走势。
    挂牌+成交双口径，本地高频，可信度中-高（部分做低）。"""
    name = "杭房数研"
    kind = "mini_program"
    provides = "both"

    def search_queries(self, community: str, district: str) -> list:
        c = f"{district} " if district else ""
        return [
            f"杭房数研 {c}{community} 成交价",
            f"杭房数研 {c}{community} 挂牌价 均价",
            f"杭房数研 {c}{community} 一年 量价走势",
            f"{community} 杭房数研 网签 套数",
        ]

    def _fetch_api(self, community: str, district: str) -> SourceFetchResult:
        url = (self.endpoint + "?" +
               urllib.parse.urlencode({"community": community, "district": district}))
        headers = {"Authorization": f"Bearer {self.token}"}
        obj = self._request_json(url, headers)
        rows = self._extract_rows(obj)
        listings, transactions = [], []
        for r in rows:
            price = self._to_float(r.get("price") or r.get("unitPrice")
                                   or r.get("avgPrice") or r.get("pricePerSqm"))
            if price is None:
                continue
            total = self._to_float(r.get("totalPrice") or r.get("total"))
            area = self._to_float(r.get("area") or r.get("buildArea"))
            kind = str(r.get("kind") or r.get("type") or "listing")
            sample = PriceSample(
                community=community,
                price_per_sqm=price,
                total_price=total,
                area=area,
                deal_date=str(r.get("date") or r.get("dealDate") or ""),
                source=self.name,
                kind="transaction" if "trans" in kind.lower() else "listing",
            )
            (transactions if sample.kind == "transaction" else listings).append(sample)
        return SourceFetchResult(
            source=self.name, community=community,
            listings=listings, transactions=transactions,
            raw_note=f"API 拉取成功：挂牌 {len(listings)} 条，成交 {len(transactions)} 条。",
            confidence="high", mode="api",
        )


class XiaojiSource(BaseSource):
    """小鸡选房（微信小程序）：杭州二手房挂盘价主力源，板块/小区维度挂盘量、
    挂牌单价、带看、成交。挂盘价反映卖方预期，需结合成交校验。"""
    name = "小鸡选房"
    kind = "mini_program"
    provides = "listing"

    def search_queries(self, community: str, district: str) -> list:
        c = f"{district} " if district else ""
        return [
            f"小鸡选房 {c}{community} 挂牌价",
            f"{community} 小鸡选房 成交价 近期",
            f"小鸡选房 {c}{community} 挂牌量 均价",
            f"{community} 小鸡选房 小区画像 带看",
        ]

    def _fetch_api(self, community: str, district: str) -> SourceFetchResult:
        url = (self.endpoint + "?" +
               urllib.parse.urlencode({"kw": community, "district": district}))
        headers = {"Authorization": f"Bearer {self.token}"}
        obj = self._request_json(url, headers)
        rows = self._extract_rows(obj)
        listings, transactions = [], []
        for r in rows:
            price = self._to_float(r.get("price") or r.get("unitPrice")
                                   or r.get("listingPrice") or r.get("avgPrice"))
            if price is None:
                continue
            total = self._to_float(r.get("totalPrice") or r.get("total"))
            area = self._to_float(r.get("area") or r.get("buildArea"))
            kind = str(r.get("kind") or r.get("type") or "listing")
            sample = PriceSample(
                community=community,
                price_per_sqm=price,
                total_price=total,
                area=area,
                deal_date=str(r.get("date") or r.get("listDate") or ""),
                source=self.name,
                kind="transaction" if "trans" in kind.lower() else "listing",
            )
            (transactions if sample.kind == "transaction" else listings).append(sample)
        return SourceFetchResult(
            source=self.name, community=community,
            listings=listings, transactions=transactions,
            raw_note=f"API 拉取成功：挂牌 {len(listings)} 条，成交 {len(transactions)} 条。",
            confidence="medium", mode="api",
        )


class BeikeSource(BaseSource):
    """贝壳/链家（网页）：成交+挂牌，作为交叉验证源。默认检索模式。"""
    name = "贝壳"
    kind = "web"
    provides = "both"

    def search_queries(self, community: str, district: str) -> list:
        c = f"{district} " if district else ""
        return [
            f"杭州 {c}{community} 贝壳 成交",
            f"杭州 {c}{community} 挂牌价 成交价",
            f"{community} 房价 走势图 贝壳",
        ]

    def _fetch_api(self, community: str, district: str) -> SourceFetchResult:
        # 贝壳无公开 API，can_api 默认 False；保留接口以便将来接入。
        return self._fetch_websearch(community, district)


def load_sources() -> list:
    """加载配置好的数据源（endpoint/token 在 sources.json）。"""
    sources = [XiaojiSource(), HangfangSource(), BeikeSource()]
    if SOURCES_CONFIG.is_file():
        try:
            cfg_all = json.loads(SOURCES_CONFIG.read_text(encoding="utf-8"))
        except Exception:
            cfg_all = {}
        for s in sources:
            if s.name in cfg_all:
                s.cfg = cfg_all[s.name] or {}
    return sources


# --------------------------------------------------------------------------- #
# 学区工作流编排
# --------------------------------------------------------------------------- #
class SchoolDistrictWorkflow:
    def __init__(self, sources: Optional[list] = None, city: str = "杭州"):
        self.sources = sources or load_sources()
        self.city = city

    # 1) 发现学区下所有小区：生成检索式（真实小区名单由代理联网补全）
    def discover_queries(self, school: str) -> list:
        return [
            f"{self.city} {school} 学区 对口 小区 名单",
            f"{school} 学区划分 对口小区",
            f"{self.city} {school} 学区房 小区 回迁房 商品房",
            f"{school} 学区 小区 均价 挂牌",
        ]

    # 2) 按平均挂牌价排序
    def rank_by_listing_price(self, communities: list,
                              reverse: bool = True) -> list:
        known = [c for c in communities if c.avg_listing_price is not None]
        unknown = [c for c in communities if c.avg_listing_price is None]
        known.sort(key=lambda c: c.avg_listing_price, reverse=reverse)
        return known + unknown

    # 3) 按预算过滤：est_area 为用户预估面积段（㎡）
    def filter_by_budget(self, communities: list, budget_wan: float,
                         est_area: float, upper_factor: float = 1.15) -> list:
        out = []
        for c in communities:
            if c.avg_listing_price is None:
                out.append(c)
                continue
            est_total_wan = c.avg_listing_price * est_area / 10000.0
            if est_total_wan <= budget_wan * upper_factor:
                out.append(c)
        return out

    # 4) 多源拉取房源信息
    def collect(self, communities: list) -> dict:
        result = {}
        for c in communities:
            per_community = {}
            for src in self.sources:
                res = src.fetch(c.name, c.district)
                per_community[src.name] = res.to_dict()
            result[c.name] = per_community
        return result

    # 5) 学区 vs 周边非学区差异比较 + 走势分析
    def compare_school_vs_nonschool(self, school_comm: list,
                                    nonschool_comm: list) -> dict:
        def avg_price(comms, htype=None):
            sel = [c for c in comms if c.avg_listing_price is not None]
            if htype:
                sel = [c for c in sel if c.housing_type == htype]
            if not sel:
                return None
            return sum(c.avg_listing_price for c in sel) / len(sel)

        # 学区侧：优先用商品房口径（回迁房会拉低均价，单独标注）
        sc_comm = avg_price(school_comm, "commodity")
        sc_all = avg_price(school_comm)
        ns = avg_price(nonschool_comm)
        premium = None
        if sc_comm is not None and ns not in (None, 0):
            premium = (sc_comm - ns) / ns

        return {
            "school_avg_listing_commodity": sc_comm,
            "school_avg_listing_all": sc_all,
            "nonschool_avg_listing": ns,
            "school_premium_rate": premium,
            "school_community_count": len(school_comm),
            "nonschool_community_count": len(nonschool_comm),
            "resettlement_note": (
                "学区侧含回迁房时已用商品房口径算溢价；回迁房通常挂牌价更低、"
                "居住品质/流动性较弱，比较时单独列出，不混入溢价计算。"
                if any(c.housing_type == "resettlement" for c in school_comm) else ""
            ),
            "trend_analysis_prompts": [
                "用 forecasting-framework.md 输出基准/乐观/悲观三情景，"
                "重点量化少子化对目标入学年份的学位需求影响。",
                "对比学区与周边非学区近 12-36 个月成交/挂牌动量，判断溢价收敛还是扩张。",
                "检查目标学校招生政策（多校划片、教师轮岗、学位预警）对确定性的冲击方向。",
                "给出学区房相对非学区的「后续走势」结论：溢价可持续/收窄/反转，及触发信号。",
            ],
        }


# --------------------------------------------------------------------------- #
# 输出：把社区名单 / 分析结果落盘成 plan.json
# --------------------------------------------------------------------------- #
def _read_communities_from_args(args) -> tuple:
    data: dict = {}
    if args.input:
        data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    else:
        comms = []
        for name in [x.strip() for x in (args.communities or "").split(",") if x.strip()]:
            comms.append(Community(name=name))
        data["communities"] = [c.to_dict() for c in comms]
    school = data.get("school", getattr(args, "school", "") or "")
    city = data.get("city", args.city or "杭州")
    budget = float(data.get("budget", args.budget if args.budget is not None else 0) or 0)
    area = float(data.get("area", args.area if args.area is not None else 90) or 90)
    communities = [Community(**c) for c in data.get("communities", [])]
    non_school = [Community(**c) for c in data.get("non_school_communities", [])]
    return school, city, budget, area, communities, non_school


def cmd_school(args) -> int:
    wf = SchoolDistrictWorkflow(city=args.city or "杭州")
    school, city, budget, area, communities, non_school = _read_communities_from_args(args)
    if not communities:
        # 还没有小区名单：先输出发现检索式，让代理补全
        plan = {
            "mode": "school-discover",
            "school": school,
            "city": city,
            "discover_queries": wf.discover_queries(school),
            "next_step": "用上述检索式找到学区下所有小区，区分回迁房/商品房，"
                         "填入各小区平均挂牌价后重新运行本命令。",
        }
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    ranked = wf.rank_by_listing_price(communities)
    filtered = wf.filter_by_budget(ranked, budget, area) if budget else ranked
    fetch_plan = wf.collect(filtered)
    comparison = None
    if non_school:
        # 溢价比较用「完整学区小区集」(ranked)，而非预算过滤后的子集，
        # 否则高价学区房被滤掉会把溢价算小，结论失真。
        comparison = wf.compare_school_vs_nonschool(ranked, non_school)

    plan = {
        "mode": "school",
        "school": school,
        "city": city,
        "budget_wan": budget,
        "est_area_sqm": area,
        "ranked_all": [c.to_dict() for c in ranked],
        "budget_filtered": [c.to_dict() for c in filtered],
        "per_source_fetch_plan": fetch_plan,
        "school_vs_nonschool": comparison,
    }
    _dump_plan(plan, args.output)
    return 0


def cmd_communities(args) -> int:
    wf = SchoolDistrictWorkflow(city=args.city or "杭州")
    _, city, budget, area, communities, _ = _read_communities_from_args(args)
    if not communities:
        print("请提供 --communities '小区A,小区B' 或 --input plan.json", file=sys.stderr)
        return 2
    ranked = wf.rank_by_listing_price(communities)
    filtered = wf.filter_by_budget(ranked, budget, area) if budget else ranked
    fetch_plan = wf.collect(filtered)
    plan = {
        "mode": "communities",
        "city": city,
        "budget_wan": budget,
        "est_area_sqm": area,
        "ranked_all": [c.to_dict() for c in ranked],
        "budget_filtered": [c.to_dict() for c in filtered],
        "per_source_fetch_plan": fetch_plan,
    }
    _dump_plan(plan, args.output)
    return 0


def cmd_fetch(args) -> int:
    sources = load_sources()
    src = next((s for s in sources if s.name == args.source), None)
    if src is None:
        print(f"未知数据源：{args.source}（可选："
              f"{', '.join(s.name for s in sources)}）", file=sys.stderr)
        return 2
    res = src.fetch(args.community, args.district or "")
    print(json.dumps(res.to_dict(), ensure_ascii=False, indent=2))
    return 0


def _dump_plan(plan: dict, output: Optional[str]) -> None:
    text = json.dumps(plan, ensure_ascii=False, indent=2)
    if output:
        Path(output).write_text(text, encoding="utf-8")
        print(f"已写出分析计划：{output}")
    else:
        print(text)


# --------------------------------------------------------------------------- #
# 自检
# --------------------------------------------------------------------------- #
def _mock_server(port: int, payload: dict) -> None:
    class H(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):  # noqa: N802
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    # 给服务器一点启动时间
    import time
    time.sleep(0.4)
    _mock_server.srv = srv


def self_test() -> int:
    ok = True

    # 1) 排序 + 预算过滤逻辑
    comms = [
        Community(name="A", housing_type="commodity", avg_listing_price=60000),
        Community(name="B", housing_type="resettlement", avg_listing_price=30000),
        Community(name="C", housing_type="commodity", avg_listing_price=80000),
        Community(name="D", housing_type="commodity", avg_listing_price=None),
    ]
    wf = SchoolDistrictWorkflow()
    ranked = wf.rank_by_listing_price(comms)
    assert [c.name for c in ranked[:3]] == ["C", "A", "B"], "排序错误"
    filtered = wf.filter_by_budget(ranked, budget_wan=500, est_area=90)
    # C: 80000*90/10000=720万 > 500*1.15 -> 过滤掉；A: 540万 -> 留；B: 270万 -> 留；D: 未知 -> 留
    assert [c.name for c in filtered] == ["A", "B", "D"], f"预算过滤错误: {[c.name for c in filtered]}"
    print("✓ 排序与预算过滤逻辑正确")

    # 2) 学区 vs 非学区溢价计算
    school_comm = [
        Community(name="学1", housing_type="commodity", avg_listing_price=70000),
        Community(name="学2", housing_type="commodity", avg_listing_price=60000),
        Community(name="学回", housing_type="resettlement", avg_listing_price=30000),
    ]
    nonschool = [Community(name="非1", housing_type="commodity", avg_listing_price=50000)]
    cmp = wf.compare_school_vs_nonschool(school_comm, nonschool)
    # 商品房口径均值 (70000+60000)/2=65000；溢价 (65000-50000)/50000=0.30
    assert abs(cmp["school_avg_listing_commodity"] - 65000) < 1e-6, "学区均价错误"
    assert abs(cmp["school_premium_rate"] - 0.30) < 1e-6, f"溢价率错误: {cmp['school_premium_rate']}"
    assert cmp["resettlement_note"], "回迁房提示缺失"
    print("✓ 学区溢价与回迁房区分正确（溢价率 30%）")

    # 3) 数据源检索式生成
    h = HangfangSource()
    q = h.search_queries("文鼎苑", "西湖")
    assert any("杭房数研" in x and "文鼎苑" in x for x in q), "杭房检索式缺失"
    x = XiaojiSource()
    qx = x.search_queries("文鼎苑", "西湖")
    assert any("小鸡选房" in x and "文鼎苑" in x for x in qx), "小鸡检索式缺失"
    print("✓ 两小程序检索式生成正确")

    # 4) API 模式（mock 服务器验证字段宽容解析）
    _mock_server(8791, {
        "data": {"list": [
            {"price": 62000, "totalPrice": 558, "area": 90, "date": "2026-07", "type": "listing"},
            {"price": 60000, "totalPrice": 540, "area": 90, "date": "2026-06", "type": "transaction"},
        ]}
    })
    h_api = HangfangSource(cfg={"endpoint": "http://127.0.0.1:8791/data",
                                "token": "test-token"})
    res = h_api.fetch("文鼎苑", "西湖")
    assert res.mode == "api", "未走 API 模式"
    assert len(res.listings) == 1 and len(res.transactions) == 1, "API 解析错误"
    assert res.confidence == "high", "API 置信度错误"
    print("✓ 杭房数研 API 模式（mock）解析正确：挂牌1/成交1")
    _mock_server.srv.shutdown()

    # 5) 无配置时退回检索模式
    h_ws = HangfangSource()
    res2 = h_ws.fetch("文鼎苑", "西湖")
    assert res2.mode == "websearch", "未退回检索模式"
    print("✓ 未配置接口时正确退回联网检索模式")

    print("\nself-test passed" if ok else "self-test failed")
    return 0 if ok else 1


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main() -> int:
    p = argparse.ArgumentParser(description="杭州购房取数与学区工作流助手")
    sub = p.add_subparsers(dest="cmd")

    ps = sub.add_parser("school", help="学区流程：发现小区→排序→预算过滤→多源拉取→差异比较")
    ps.add_argument("--school", default="")
    ps.add_argument("--city", default="杭州")
    ps.add_argument("--budget", type=float, default=None, help="总预算（万元）")
    ps.add_argument("--area", type=float, default=None, help="预估面积（㎡）")
    ps.add_argument("--communities", default="")
    ps.add_argument("--input", default="")
    ps.add_argument("--output", default="")
    ps.set_defaults(func=cmd_school)

    pc = sub.add_parser("communities", help="直接给小区（多个）流程：排序→预算过滤→多源拉取")
    pc.add_argument("--communities", default="")
    pc.add_argument("--school", default="")
    pc.add_argument("--city", default="杭州")
    pc.add_argument("--budget", type=float, default=None)
    pc.add_argument("--area", type=float, default=None)
    pc.add_argument("--input", default="")
    pc.add_argument("--output", default="")
    pc.set_defaults(func=cmd_communities)

    pf = sub.add_parser("fetch", help="单源拉取某个小区的挂盘/成交数据")
    pf.add_argument("--source", required=True, help="杭房数研 / 小鸡选房 / 贝壳")
    pf.add_argument("--community", required=True)
    pf.add_argument("--district", default="")
    pf.set_defaults(func=cmd_fetch)

    p.add_argument("--self-test", action="store_true", help="运行自检")
    args = p.parse_args()
    if args.self_test:
        return self_test()
    if not getattr(args, "cmd", None):
        p.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
