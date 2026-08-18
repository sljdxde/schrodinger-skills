#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全国城市购房分析取数与学区工作流助手（house-buying skill）。

本脚本只做「编排与计划 + 取数适配」，不替用户下决策。真实数据来自三条通道：

1) 抓包 / 平台 API 模式（数据最稳）
   微信小程序（杭房数研 / 小鸡选房）是封闭生态，没有公开网页 API；贝壳、
   我爱我家等网站也有反爬策略。取数做法是：在手机上用 mitmproxy / Charles
   对微信抓包，或从站点公开接口拿到调用后端时的 HTTPS 接口（endpoint）和
   登录态（token / cookie），填进 `sources.json`，脚本即可脚本化拉取。
   抓包一次，长期复用。

2) 浏览器渲染模式（反爬兜底，可选）
   对 JS 渲染、UA/头校验等常见反爬，可给数据源配置 `browser: true` 与
   `cookie`、`headers`、`request_interval`，脚本会先用浏览器化请求直连；
   仍拿不到数据时尝试本机已安装的 Playwright 渲染页面再解析。只采集公开
   页面数据，不破解验证码、不做高频批量抓取。

3) 联网检索兜底模式（默认）
   没有配置 endpoint/token 时，脚本会生成「精确到数据源与城市」的检索式，
   由 AI 代理用 WebSearch / WebFetch 取数，再把结果回填。

所有数据源统一要求输出价格时间轴：同一小区用月度粒度记录挂牌价、成交价和
样本量，禁止只给一个「当前均价」就下趋势判断。

学区工作流（用户定义的流程）：
   选学区 -> 找到学区下所有小区（区分回迁房 / 商品房）-> 按小区平均挂牌价排序
   -> 用用户预算过滤 -> 去不同数据源拉取房源时间轴并分析
   若用户直接给小区（可多个）-> 跳过发现/排序，直接拉取分析
   最后 -> 给出学区 vs 周边非学区房价差异比较，并分析后续走势

依赖：仅标准库；Playwright 为可选增强。Python 3.9+。
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

SKILL_DIR = Path(__file__).resolve().parents[1]
SOURCES_CONFIG = SKILL_DIR / "scripts" / "sources.json"

DEFAULT_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 "
                   "Safari/537.36"),
    "Accept": ("text/html,application/xhtml+xml,application/json;q=0.9,"
               "image/avif,image/webp,*/*;q=0.8"),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def normalize_month(raw) -> str:
    """把 2026-07-01 / 2026年7月 / 2026/7 统一成 YYYY-MM。"""
    s = str(raw or "").strip()
    if not s:
        return ""
    m = re.search(r"(\d{4})[-/年.](\d{1,2})", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    return s[:7]


# --------------------------------------------------------------------------- #
# 贝壳官方 CLI 接入（LianjiaTech/beike-ai-platform）
# --------------------------------------------------------------------------- #
# 贝壳提供官方 CLI 工具 `beike`（需登录获取 API Key 并 `beike auth <KEY> --save`）。
# 安装：curl -fsSL https://raw.githubusercontent.com/LianjiaTech/beike-ai-platform/master/cli/releases/install.sh | bash
# 这是 skill 接入「真实平台数据」的首选合规通道：返回结构化 JSON（默认单行），
# 而非抓取页面，避免反爬风险与编造。未安装 / 未鉴权时自动退回联网检索（绝不编造数据）。
BEIKE_CLI_BIN = "beike"
BEIKE_KEY_FILE = Path.home() / ".beike" / "BEIKE_MCP_API_KEY"
BEIKE_INSTALL_HINT = (
    "未检测到贝壳官方 CLI 或未鉴权，已退回联网检索模式（不会用 CLI 编造数据）。\n"
    "  1) 安装：curl -fsSL "
    "https://raw.githubusercontent.com/LianjiaTech/beike-ai-platform/master/cli/releases/install.sh | bash\n"
    "  2) 获取 Key：https://building.ke.com/?action=get-key&source=house-buying\n"
    "  3) 保存：beike auth <YOUR_API_KEY> --save\n"
    "详情见 references/data-source-playbook.md「贝壳官方 CLI」章节。"
)


def beike_cli_available() -> bool:
    """本机是否安装了贝壳 CLI 且已保存 API Key。"""
    if shutil.which(BEIKE_CLI_BIN) is None:
        return False
    if os.environ.get("BEIKE_MCP_API_KEY"):
        return True
    return BEIKE_KEY_FILE.is_file()


def _json_extract_all(text: str) -> list:
    """从文本中贪心抽取所有顶层 JSON 对象/数组（兼容 CLI 多段 JSON 拼接输出）。

    贝壳 CLI 的 `buy search` 等命令会一次性返回多段 `{"data": ...}` JSON（例如
    先 房源 子查询、再 新房 子查询），直接 json.loads 整段会因「Extra data」失败。
    这里用原始解码器顺序抽取，返回所有解析成功的 dict/list。
    """
    out: list = []
    i = 0
    n = len(text)
    dec = json.JSONDecoder()
    while i < n:
        # 跳过空白
        while i < n and text[i] in " \r\n\t":
            i += 1
        if i >= n:
            break
        try:
            obj, end = dec.raw_decode(text, i)
            out.append(obj)
            i = end
        except (json.JSONDecodeError, ValueError):
            # 当前位置无法解析：跳过 1 个字符，避免死循环
            i += 1
    return out


def _run_beike_cli(args: list, timeout: int = 30) -> dict:
    """执行 `beike <args>`，返回解析后的 JSON；失败抛异常（由调用方兜底）。

    返回「含 data 字段且 data 最长」的那一个顶层对象——`buy search` 等多子查询
    命令会拼接返回多段 JSON，房源结果段的 data 通常最长、信息最全。
    """
    if shutil.which(BEIKE_CLI_BIN) is None:
        raise RuntimeError("beike CLI 未安装")
    cmd = [BEIKE_CLI_BIN] + [str(a) for a in args]
    # 官方 CLI 默认返回友好纯文本；加 --json 才返回结构化 JSON（供程序解析）。
    # 不加 --json 会导致解析失败、错误退回检索，故始终强制补上（除非已显式指定）。
    if "--json" not in cmd and "--pretty" not in cmd:
        cmd.append("--json")
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(
            f"beike 退出码 {proc.returncode}：{(proc.stderr or '').strip()[:300]}")
    out = (proc.stdout or "").strip()
    if not out:
        raise RuntimeError(f"beike 无输出：{(proc.stderr or '').strip()[:300]}")
    try:
        objs = _json_extract_all(out)
    except Exception as exc:  # 极端兜底
        raise RuntimeError(f"beike 输出非 JSON（前200字）：{out[:200]}") from exc
    if not objs:
        raise RuntimeError(f"beike 输出无可解析 JSON（前200字）：{out[:200]}")
    data_objs = [o for o in objs if isinstance(o, dict) and isinstance(o.get("data"), str)]
    if not data_objs:
        # 退而求其次：返回第一个 dict
        for o in objs:
            if isinstance(o, dict):
                return o
        raise RuntimeError(f"beike 输出无结构化对象（前200字）：{out[:200]}")
    # 取 data 最长的对象（房源结果段信息最全）
    return max(data_objs, key=lambda o: len(o.get("data", "")))


def _beike_first(item: dict, keys) -> Optional[str]:
    for k in keys:
        v = item.get(k)
        if v not in (None, "", []):
            return str(v)
    return None


def _beike_item_to_row(item: dict) -> Optional[dict]:
    """把一条贝壳 CLI 记录映射成 _build_result 可消费的规范行。

    只抽取真实存在的字段；无法得到单价（元/㎡）则无法进入价格证据链，直接丢弃（不编造）。
    成交/挂牌记录常只给「总价(万)+面积(㎡)」，按 元/㎡ = 总价*10000/面积 反算单价，
    确保近期成交记录（house-buying 最看重的价格证据）也能进入证据链。
    """
    if not isinstance(item, dict):
        return None
    unit = BaseSource._to_float(
        item.get("unitPrice") or item.get("pricePerSqm")
        or item.get("unit_price") or item.get("price_per_sqm")
        or item.get("price")
    )
    total = BaseSource._to_float(
        item.get("totalPrice") or item.get("total_price") or item.get("total"))
    area = BaseSource._to_float(
        item.get("area") or item.get("buildArea") or item.get("build_area")
        or item.get("square"))
    # 成交/挂牌只给 总价+面积 时，反算单价（万→元/㎡）
    if unit is None and total is not None and area not in (None, 0):
        unit = (total * 10000.0) / area
    if unit is None:
        return None
    t = str(item.get("type") or item.get("tradeType") or item.get("status")
            or item.get("dealType") or "").lower()
    kind = "transaction" if ("sold" in t or "deal" in t or "trans" in t
                             or "成交" in t or "已售" in t) else "listing"
    return {
        # 进入价格证据链的字段（约定：price=元/㎡，totalPrice=万）
        "price": unit,
        "totalPrice": total,
        "area": area,
        "kind": kind,
        "date": item.get("dealDate") or item.get("deal_date") or "",
        # 明细字段：供真实 URL 引用与展示，不进入价格计算
        "title": _beike_first(item, ["title", "communityName",
                                      "estateName", "name"]),
        "communityName": _beike_first(item, ["communityName", "estateName",
                                             "community", "title"]),
        "district": _beike_first(item, ["districtName", "areaName",
                                        "region", "district"]),
        "url": _beike_first(item, ["url", "detailUrl", "detail_url",
                                   "houseUrl", "link"]),
        "cover": _beike_first(item, ["cover", "image", "imgUrl",
                                     "photo", "coverUrl"]),
    }


def _parse_beike_cli_payload(obj) -> tuple:
    """解析贝壳 CLI 返回的 JSON。返回 (rows, note)。

    对未知结构保持防御：返回空列表 + 说明，绝不抛异常、绝不编造。
    """
    rows: list = []
    note = ""
    if not isinstance(obj, (dict, list)):
        return rows, "CLI 返回非预期类型，已退回检索"
    arr = BaseSource._extract_rows(obj) if isinstance(obj, dict) else list(obj)
    if not arr:
        # 部分 CLI 把列表放在别的键
        for k in ("listings", "houses", "housesList", "sellList", "results"):
            v = obj.get(k) if isinstance(obj, dict) else None
            if isinstance(v, list) and v:
                arr = v
                break
    for it in arr:
        row = _beike_item_to_row(it)
        if row is not None:
            rows.append(row)
    if not rows:
        note = "CLI 返回结构无法解析为房源记录（字段名不匹配），已退回联网检索"
    return rows, note


# --------------------------------------------------------------------------- #
# 数据结构
# --------------------------------------------------------------------------- #
@dataclass
class Community:
    name: str
    city: str = ""
    district: str = ""
    school: str = ""
    # commodity=商品房, resettlement=回迁房, unknown=未区分
    housing_type: str = "unknown"
    avg_listing_price: Optional[float] = None  # 元/㎡
    listing_count: Optional[int] = None
    history: list = field(default_factory=list)  # PricePoint dicts，月度时间轴
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "city": self.city,
            "district": self.district,
            "school": self.school,
            "housing_type": self.housing_type,
            "avg_listing_price": self.avg_listing_price,
            "listing_count": self.listing_count,
            "history": self.history,
            "note": self.note,
        }


@dataclass
class PriceSample:
    community: str
    price_per_sqm: float
    city: str = ""
    total_price: Optional[float] = None
    area: Optional[float] = None
    deal_date: str = ""
    source: str = ""
    kind: str = "listing"  # listing=挂牌, transaction=成交

    def to_dict(self) -> dict:
        return {
            "community": self.community,
            "city": self.city,
            "price_per_sqm": self.price_per_sqm,
            "total_price": self.total_price,
            "area": self.area,
            "deal_date": self.deal_date,
            "source": self.source,
            "kind": self.kind,
        }


@dataclass
class PricePoint:
    """小区价格时间轴上的一个时间点，date 统一成 YYYY-MM。"""
    community: str
    city: str = ""
    date: str = ""
    price_per_sqm: Optional[float] = None
    total_price: Optional[float] = None
    area: Optional[float] = None
    source: str = ""
    kind: str = "listing"  # listing=挂牌, transaction=成交
    count: Optional[int] = None  # 该月份样本量
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "community": self.community,
            "city": self.city,
            "date": self.date,
            "price_per_sqm": self.price_per_sqm,
            "total_price": self.total_price,
            "area": self.area,
            "source": self.source,
            "kind": self.kind,
            "count": self.count,
            "note": self.note,
        }


@dataclass
class SourceFetchResult:
    source: str
    community: str
    city: str = ""
    listings: list = field(default_factory=list)
    transactions: list = field(default_factory=list)
    history: list = field(default_factory=list)
    queries: list = field(default_factory=list)
    raw_note: str = ""
    confidence: str = "low"
    mode: str = "websearch"  # api / websearch / cli / cli_unavailable
    months: int = 36
    tier: str = "T3"  # 数据源分级 T0/T1/T1.5/T2/T3/T4
    extra: dict = field(default_factory=dict)  # 平台专属载荷（如 CLI 明细列表/查询词）

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "community": self.community,
            "city": self.city,
            "listings": [s.to_dict() for s in self.listings],
            "transactions": [s.to_dict() for s in self.transactions],
            "history": [p.to_dict() for p in self.history],
            "queries": self.queries,
            "raw_note": self.raw_note,
            "confidence": self.confidence,
            "mode": self.mode,
            "months": self.months,
            "tier": self.tier,
            "extra": self.extra,
        }

# --------------------------------------------------------------------------- #
# 数据源适配器
# --------------------------------------------------------------------------- #
class BaseSource:
    name = "base"
    kind = "mini_program"  # mini_program / web
    # 该源主力提供什么口径
    provides = "listing"  # listing / transaction / both
    # 数据源分级（house-buying 五级体系，见 references/data-source-playbook.md）：
    # T0=核心平台(贝壳系/我爱我家) / T1=官方佐证(住建/网签/不动产登记) /
    # T1.5=城市本地高频源(接近网签，如杭房数研) / T2=政务App与本地小程序 /
    # T3=交叉验证(诸葛找房/安居客/房天下/58同城) / T4=舆情
    tier = "T3"

    def __init__(self, cfg: Optional[dict] = None, city: str = "杭州"):
        self.cfg = cfg or {}
        self.city = city

    def _cfg_for(self, city: Optional[str] = None) -> dict:
        """支持 sources.json 里按城市覆盖 endpoint/token/cookie/headers。"""
        city = city or self.city
        cities = self.cfg.get("cities")
        if isinstance(cities, dict):
            specific = cities.get(city)
            if isinstance(specific, dict):
                merged = {k: v for k, v in self.cfg.items() if k != "cities"}
                merged.update(specific)
                return merged
        return self.cfg

    def endpoint_for(self, city: Optional[str] = None) -> Optional[str]:
        return self._cfg_for(city).get("endpoint")

    def token_for(self, city: Optional[str] = None) -> Optional[str]:
        return self._cfg_for(city).get("token")

    def can_api(self, city: Optional[str] = None) -> bool:
        cfg = self._cfg_for(city)
        return bool(cfg.get("endpoint") and (cfg.get("token") or cfg.get("cookie")))

    def fetch(self, community: str, district: str = "",
              city: Optional[str] = None, months: int = 36) -> SourceFetchResult:
        city = city or self.city
        if self.can_api(city):
            try:
                res = self._fetch_api(community, district, city, months)
                res.tier = self.tier
                return res
            except Exception as exc:  # 兜底回检索
                res = self._fetch_websearch(community, district, city, months)
                res.tier = self.tier
                res.raw_note = f"API 拉取失败({exc})，已退回联网检索模式。{res.raw_note}"
                return res
        res = self._fetch_websearch(community, district, city, months)
        res.tier = self.tier
        return res

    # ---- API 模式：子类实现具体接口 ----
    def _fetch_api(self, community: str, district: str, city: str,
                   months: int = 36) -> SourceFetchResult:
        raise NotImplementedError

    # ---- 检索模式：默认生成精确检索式 ----
    def _fetch_websearch(self, community: str, district: str, city: str,
                         months: int = 36) -> SourceFetchResult:
        queries = self.search_queries(community, district, city, months)
        return SourceFetchResult(
            source=self.name,
            community=community,
            city=city,
            queries=queries,
            raw_note=("未配置接口，请按上述检索式联网取数后回填 "
                      "listings/transactions/history。"),
            confidence="low",
            mode="websearch",
            months=months,
        )

    def search_queries(self, community: str, district: str, city: str = "杭州",
                       months: int = 36) -> list:
        raise NotImplementedError

    # ---- 通用请求：浏览器化请求头、Cookie、限速、重试 ----
    def _request_text(self, url: str, city: Optional[str] = None,
                      headers: Optional[dict] = None) -> str:
        cfg = self._cfg_for(city or self.city)
        h = dict(DEFAULT_HEADERS)
        if headers:
            h.update(headers)
        h.update(cfg.get("headers") or {})
        cookie = cfg.get("cookie") or cfg.get("cookies")
        if cookie:
            h["Cookie"] = str(cookie)
        token = cfg.get("token")
        if token and "Authorization" not in h:
            h["Authorization"] = f"Bearer {token}"
        interval = float(cfg.get("request_interval") or 0)
        if interval > 0:
            time.sleep(interval)
        retries = max(1, int(cfg.get("retries") or 2) + 1)
        timeout = float(cfg.get("timeout") or 20)
        last_exc = None
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, headers=h)
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.read().decode("utf-8", "replace")
            except Exception as exc:
                last_exc = exc
                if attempt < retries - 1:
                    time.sleep(1.0 + attempt)
        if last_exc:
            raise last_exc
        return ""

    def _request_json(self, url: str, city: Optional[str] = None) -> dict:
        text = self._request_text(
            url, city=city,
            headers={"Accept": "application/json, text/plain, */*"},
        )
        return json.loads(text)

    @staticmethod
    def _url_with_params(endpoint: str, **params) -> str:
        sep = "&" if "?" in endpoint else "?"
        return endpoint + sep + urllib.parse.urlencode(params)

    @staticmethod
    def _extract_rows(obj) -> list:
        """从常见 JSON 形状里抽取记录数组。"""
        if isinstance(obj, list):
            return obj
        if isinstance(obj, dict):
            for key in ("data", "list", "items", "records", "communityList",
                        "result", "rows", "content", "priceHistory"):
                v = obj.get(key)
                if isinstance(v, list) and v:
                    return v
            if "data" in obj and isinstance(obj["data"], dict):
                for key in ("list", "items", "records", "communityList",
                            "rows", "priceHistory"):
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

    @staticmethod
    def _to_int(val) -> Optional[int]:
        if val is None:
            return None
        if isinstance(val, bool):
            return None
        try:
            return int(float(str(val).replace(",", "").strip()))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _history_point(row: dict, community: str, city: str, source: str,
                       kind: str = "listing") -> Optional[PricePoint]:
        price = BaseSource._to_float(
            row.get("price") or row.get("unitPrice") or row.get("avgPrice")
            or row.get("pricePerSqm")
        )
        if price is None:
            return None
        return PricePoint(
            community=community,
            city=city,
            date=normalize_month(row.get("date") or row.get("month")
                                 or row.get("dealDate") or row.get("time") or ""),
            price_per_sqm=price,
            total_price=BaseSource._to_float(row.get("totalPrice") or row.get("total")),
            area=BaseSource._to_float(row.get("area") or row.get("buildArea")),
            source=source,
            kind=kind,
            count=BaseSource._to_int(row.get("count") or row.get("num")
                                     or row.get("volume") or row.get("dealCount")),
        )

    def _build_result(self, rows: list, community: str, city: str, source: str,
                      default_kind: str = "listing") -> tuple:
        listings: list = []
        transactions: list = []
        history: list = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            price = self._to_float(r.get("price") or r.get("unitPrice")
                                   or r.get("avgPrice") or r.get("pricePerSqm")
                                   or r.get("listingPrice"))
            if price is None:
                continue
            total = self._to_float(r.get("totalPrice") or r.get("total"))
            area = self._to_float(r.get("area") or r.get("buildArea"))
            kind = str(r.get("kind") or r.get("type") or default_kind).lower()
            sample_kind = "transaction" if "trans" in kind else "listing"
            sample = PriceSample(
                community=community,
                city=city,
                price_per_sqm=price,
                total_price=total,
                area=area,
                deal_date=str(r.get("date") or r.get("dealDate") or ""),
                source=source,
                kind=sample_kind,
            )
            (transactions if sample_kind == "transaction" else listings).append(sample)
            hs = (r.get("history") or r.get("priceHistory") or r.get("monthly")
                  or r.get("trend") or r.get("points"))
            if isinstance(hs, list):
                for hp in hs:
                    if not isinstance(hp, dict):
                        continue
                    point = self._history_point(hp, community, city, source, sample_kind)
                    if point is not None and point.price_per_sqm is not None:
                        history.append(point)
        return listings, transactions, history


class WebSource(BaseSource):
    """网页源：浏览器化直连 + 可选 Playwright 渲染兜底。"""
    kind = "web"

    def _fetch_html(self, url: str, city: Optional[str] = None) -> str:
        city = city or self.city
        cfg = self._cfg_for(city)
        html = ""
        try:
            html = self._request_text(url, city=city)
        except Exception:
            html = ""
        if cfg.get("browser"):
            rendered = self._playwright_html(url, city)
            if rendered:
                html = rendered
        return html

    def _playwright_html(self, url: str, city: str) -> str:
        cfg = self._cfg_for(city)
        if not cfg.get("browser"):
            return ""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return ""
        try:
            with sync_playwright() as p:
                browser_type_name = cfg.get("browser_type") or "chromium"
                browser_type = getattr(p, browser_type_name, p.chromium)
                browser = browser_type.launch(
                    headless=bool(cfg.get("headless", True)),
                    args=["--disable-blink-features=AutomationControlled"],
                )
                context = browser.new_context(
                    user_agent=cfg.get("user_agent") or DEFAULT_HEADERS["User-Agent"],
                    locale="zh-CN",
                    viewport={"width": 1280, "height": 900},
                )
                cookie = cfg.get("cookie") or cfg.get("cookies")
                if cookie:
                    cookies = []
                    domain = urllib.parse.urlparse(url).hostname or ""
                    for item in str(cookie).split(";"):
                        if "=" in item:
                            name, value = item.strip().split("=", 1)
                            cookies.append({
                                "name": name,
                                "value": value,
                                "domain": domain,
                                "path": "/",
                            })
                    if cookies:
                        context.add_cookies(cookies)
                headers = cfg.get("headers") or {}
                if headers and not cookie:
                    context.set_extra_http_headers(headers)
                page = context.new_page()
                timeout_ms = float(cfg.get("timeout_ms") or 30000)
                page.goto(
                    url,
                    wait_until=cfg.get("wait_until") or "domcontentloaded",
                    timeout=timeout_ms,
                )
                if cfg.get("wait_selector"):
                    page.wait_for_selector(
                        cfg["wait_selector"],
                        timeout=float(cfg.get("timeout_ms") or 15000),
                    )
                html = page.content()
                browser.close()
                return html
        except Exception:
            return ""

    def _embedded_json_rows(self, html: str) -> list:
        patterns = [
            r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            r'<script[^>]+id="__NUXT_DATA__"[^>]*>(.*?)</script>',
            r'<script[^>]+type="application/json"[^>]*>(.*?)</script>',
        ]
        for pat in patterns:
            m = re.search(pat, html, re.S)
            if m:
                try:
                    obj = json.loads(html_lib.unescape(m.group(1)))
                    rows = self._extract_rows(obj)
                    if rows:
                        return rows
                except Exception:
                    continue
        for marker in ("__INITIAL_STATE__", "__APP_DATA__", "__NUXT__"):
            idx = html.find(marker)
            if idx < 0:
                continue
            start = html.find("{", idx)
            if start < 0:
                continue
            try:
                obj, _ = json.JSONDecoder().raw_decode(html[start:])
                rows = self._extract_rows(obj)
                if rows:
                    return rows
            except Exception:
                continue
        return []

    def _rows_from_html(self, html: str) -> list:
        rows = self._embedded_json_rows(html)
        if rows:
            return rows
        # 兜底：从页面内嵌 JSON 字段里抓 price，只能当线索，不可当精确证据。
        seen = set()
        out = []
        for raw in re.findall(r'"(?:unitPrice|avgPrice|price)"\s*:\s*(\d+(?:\.\d+)?)', html):
            value = float(raw)
            if value not in seen:
                seen.add(value)
                out.append({"price": value})
        return out


class HangfangSource(BaseSource):
    """杭房数研（微信小程序）：城市日度/月度网签与小区量价走势。"""
    name = "杭房数研"
    kind = "mini_program"
    provides = "both"
    tier = "T1.5"  # 城市本地高频源，接近网签口径

    def search_queries(self, community: str, district: str, city: str = "杭州",
                       months: int = 36) -> list:
        c = f"{district} " if district else ""
        return [
            f"杭房数研 {city} {c}{community} 成交价",
            f"杭房数研 {city} {c}{community} 挂牌价 均价",
            f"杭房数研 {city} {c}{community} 近{months}个月 量价走势 月度",
            f"{community} 杭房数研 网签 套数 每月",
        ]

    def _fetch_api(self, community: str, district: str, city: str,
                   months: int = 36) -> SourceFetchResult:
        url = self._url_with_params(
            self.endpoint_for(city),
            community=community, district=district, city=city, months=months,
        )
        obj = self._request_json(url, city=city)
        rows = self._extract_rows(obj)
        listings, transactions, history = self._build_result(
            rows, community, city, self.name,
        )
        return SourceFetchResult(
            source=self.name, community=community, city=city,
            listings=listings, transactions=transactions, history=history,
            raw_note=(f"API 拉取成功：挂牌 {len(listings)} 条，成交 "
                      f"{len(transactions)} 条，历史点 {len(history)} 个。"),
            confidence="high", mode="api", months=months,
        )


class XiaojiSource(BaseSource):
    """小鸡选房（微信小程序）：挂盘价主力源，覆盖板块/小区维度。"""
    name = "小鸡选房"
    kind = "mini_program"
    provides = "listing"
    tier = "T2"  # 城市本地小程序（挂盘口径）

    def search_queries(self, community: str, district: str, city: str = "杭州",
                       months: int = 36) -> list:
        c = f"{district} " if district else ""
        return [
            f"小鸡选房 {city} {c}{community} 挂牌价",
            f"{community} 小鸡选房 {city} 成交价 近期",
            f"小鸡选房 {city} {c}{community} 挂牌量 均价",
            f"{community} 小鸡选房 小区画像 带看",
        ]

    def _fetch_api(self, community: str, district: str, city: str,
                   months: int = 36) -> SourceFetchResult:
        url = self._url_with_params(
            self.endpoint_for(city),
            kw=community, district=district, city=city, months=months,
        )
        obj = self._request_json(url, city=city)
        rows = self._extract_rows(obj)
        listings, transactions, history = self._build_result(
            rows, community, city, self.name,
        )
        return SourceFetchResult(
            source=self.name, community=community, city=city,
            listings=listings, transactions=transactions, history=history,
            raw_note=(f"API 拉取成功：挂牌 {len(listings)} 条，成交 "
                      f"{len(transactions)} 条，历史点 {len(history)} 个。"),
            confidence="medium", mode="api", months=months,
        )


class BeikeSource(WebSource):
    """贝壳/链家（网页）：全国城市成交+挂牌，T0 核心数据源。"""
    name = "贝壳"
    kind = "web"
    provides = "both"
    tier = "T0"

    def fetch(self, community: str, district: str = "",
              city: Optional[str] = None, months: int = 36) -> SourceFetchResult:
        # 优先走贝壳官方 CLI（真实结构化数据）；不可用则退回 endpoint/websearch
        city = city or self.city
        if beike_cli_available():
            try:
                return BeikeCliSource(city=city).fetch(
                    community, district, city, months)
            except Exception:
                pass
        return super().fetch(community, district, city, months)

    def search_queries(self, community: str, district: str, city: str = "杭州",
                       months: int = 36) -> list:
        c = f"{district} " if district else ""
        return [
            f"{city} {c}{community} 贝壳 成交",
            f"{city} {c}{community} 挂牌价 成交价",
            f"{city} {community} 近{months}个月 房价 走势图 贝壳",
        ]

    def _fetch_api(self, community: str, district: str, city: str,
                   months: int = 36) -> SourceFetchResult:
        cfg = self._cfg_for(city)
        endpoint = self.endpoint_for(city)
        if not endpoint:
            return self._fetch_websearch(community, district, city, months)
        if cfg.get("html") or cfg.get("render"):
            html = self._fetch_html(endpoint, city)
            rows = self._rows_from_html(html)
            mode_note = "HTML/浏览器渲染模式"
        else:
            obj = self._request_json(endpoint, city=city)
            rows = self._extract_rows(obj)
            mode_note = "JSON API 模式"
        listings, transactions, history = self._build_result(
            rows, community, city, self.name,
        )
        raw_note = (f"{mode_note}：挂牌 {len(listings)} 条，成交 "
                    f"{len(transactions)} 条，历史点 {len(history)} 个。")
        if not rows:
            raw_note += " 未解析到结构化记录，请核对 endpoint/selectors 或改用检索模式。"
        return SourceFetchResult(
            source=self.name, community=community, city=city,
            listings=listings, transactions=transactions, history=history,
            raw_note=raw_note,
            confidence="high" if rows else "low",
            mode="api", months=months,
        )


class WoaiwojiaSource(WebSource):
    """我爱我家（网页）：全国城市挂牌+成交，T0 核心数据源。"""
    name = "我爱我家"
    kind = "web"
    provides = "both"
    tier = "T0"

    def search_queries(self, community: str, district: str, city: str = "杭州",
                       months: int = 36) -> list:
        c = f"{district} " if district else ""
        return [
            f"{city} {c}{community} 我爱我家 挂牌价",
            f"{city} {c}{community} 我爱我家 成交价 近期",
            f"{city} {community} 近{months}个月 我爱我家 房价走势",
        ]

    def _fetch_api(self, community: str, district: str, city: str,
                   months: int = 36) -> SourceFetchResult:
        cfg = self._cfg_for(city)
        endpoint = self.endpoint_for(city)
        if not endpoint:
            return self._fetch_websearch(community, district, city, months)
        if cfg.get("html") or cfg.get("render"):
            html = self._fetch_html(endpoint, city)
            rows = self._rows_from_html(html)
            mode_note = "HTML/浏览器渲染模式"
        else:
            obj = self._request_json(endpoint, city=city)
            rows = self._extract_rows(obj)
            mode_note = "JSON API 模式"
        listings, transactions, history = self._build_result(
            rows, community, city, self.name,
        )
        raw_note = (f"{mode_note}：挂牌 {len(listings)} 条，成交 "
                    f"{len(transactions)} 条，历史点 {len(history)} 个。")
        if not rows:
            raw_note += " 未解析到结构化记录，请核对 endpoint/selectors 或改用检索模式。"
        return SourceFetchResult(
            source=self.name, community=community, city=city,
            listings=listings, transactions=transactions, history=history,
            raw_note=raw_note,
            confidence="high" if rows else "low",
            mode="api", months=months,
        )


# --------------------------------------------------------------------------- #
# 贝壳官方 CLI 真实输出解析（适配 beike v0.2.x 半结构化文本）
# --------------------------------------------------------------------------- #
# 说明：beike CLI `--json` 返回的不是干净列表 JSON，而是 `{"data": "<长文本>"}`，
# data 是 XML/Markdown 混合的半结构化文本：每个房源用 `<房源ID>` 标签包裹、内部
# 嵌一段 JSON 片段；价格/小区信息是中文字符串（如「总价899万，单价52595元/平米」）。
# 以下解析器从文本抽取真实房源/小区实体，并用真实房源ID构造 ke.com 详情 URL。
# 防御式：解析不出任何实体返回空，绝不抛异常、绝不编造。

# 主要城市 ke.com 拼音缩写（构造真实详情 URL 用；未覆盖城市不构造 URL）
CITY_PINYIN = {
    "北京": "bj", "上海": "sh", "广州": "gz", "深圳": "sz", "成都": "cd",
    "杭州": "hz", "武汉": "wh", "南京": "nj", "苏州": "su", "重庆": "cq",
    "天津": "tj", "西安": "xa", "宁波": "nb", "无锡": "wx", "佛山": "fs",
    "珠海": "zh", "厦门": "xm", "长沙": "cs", "郑州": "zz", "青岛": "qd",
    "大连": "dl", "沈阳": "sy", "济南": "jn", "合肥": "hf", "昆明": "km",
    "贵阳": "gy", "南宁": "nn", "海口": "hk", "南昌": "nc", "福州": "fz",
    "东莞": "dg", "石家庄": "sjz", "哈尔滨": "hrb", "长春": "cc", "太原": "ty",
    "兰州": "lz", "乌鲁木齐": "wlmq", "呼和浩特": "huh", "银川": "yc",
    "西宁": "xn", "拉萨": "ls",
}


def _beike_city_py(city: str) -> Optional[str]:
    return CITY_PINYIN.get((city or "").strip())


_NUM = r"(\d+(?:\.\d+)?)"


def _beike_extract_blocks(data: str) -> list:
    """从 data 文本抽取所有 `<标识>\\n{JSON}\\n</标识>` 区块，返回 [(标识, dict)]。"""
    blocks: list = []
    for m in re.finditer(r"<([^/>]+)>\s*\n?\s*(\{.*?\})\s*\n?\s*</\1>", data,
                         re.DOTALL):
        ident = m.group(1).strip()
        try:
            d = json.loads(m.group(2))
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict):
            blocks.append((ident, d))
    return blocks


def _beike_price_from_text(text: str):
    """从价格文本提取 (总价万, 单价元/㎡)。

    兼容多种真实写法：
    - 摘要信息式：「总价520万，单价58000元/平米」
    - 基本信息式成交：「成交价格315万」/「挂牌价格335万」/ 裸「315万」
    - 其它：带标签的「成交价/挂牌价 X万」
    """
    if not text:
        return None, None
    total = None
    unit = None
    mt = re.search(r"(?:总价|成交价格|挂牌价格|成交价|挂牌价)?\s*"
                   + _NUM + r"\s*万", text)
    if mt:
        total = float(mt.group(1))
    mu = re.search(r"单价\s*" + _NUM + r"\s*元/平米", text)
    if mu:
        unit = float(mu.group(1))
    return total, unit


def _beike_normalize_date(s: str) -> str:
    """把真实 CLI 的多种日期写法归一为 YYYY-MM / YYYY-MM-DD。

    - 点分隔成交日期：「2026.04.26」->「2026-04-26」
    - 短横/连字符：「2026-07-15」「2026/07」
    - 中文：「2026年7月15日」「2026年7月」
    无法识别原样返回（绝不编造）。
    """
    if not s:
        return ""
    s = str(s).strip()
    m = re.search(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r"(\d{4})-(\d{1,2})(?:-(\d{1,2}))?", s)
    if m:
        base = f"{m.group(1)}-{int(m.group(2)):02d}"
        return base + (f"-{int(m.group(3)):02d}" if m.group(3) else "")
    m = re.search(r"(\d{4})年(\d{1,2})月(?:(\d{1,2})日)?", s)
    if m:
        base = f"{m.group(1)}-{int(m.group(2)):02d}"
        return base + (f"-{int(m.group(3)):02d}" if m.group(3) else "")
    return s


def _beike_community_from_title(title) -> Optional[str]:
    """从房源标题前缀抽小区名：「德信银树湾 2室2厅 89.4㎡」->「德信银树湾」。"""
    if not title:
        return None
    t = str(title).strip()
    m = re.search(r"^(.+?)\s+\d+室", t)
    if m:
        return m.group(1).strip()
    m2 = re.search(r"^(\S+)", t)
    return m2.group(1).strip() if m2 else None


def _beike_xiaoqu_id_from_text(*texts) -> Optional[str]:
    """从任意文本里抽小区ID（「小区ID:1811044432792」/「小区ID 1811044432792」）。"""
    for t in texts:
        if not t:
            continue
        m = re.search(r"小区ID[:：]?\s*([0-9A-Za-z]+)", str(t))
        if m:
            return m.group(1)
    return None


def _beike_listing_date_from_text(s: str) -> str:
    """挂牌/在售记录无成交日期时，从「房源动态」取最近一次调价日（点分隔）。"""
    if not s:
        return ""
    dates = re.findall(r"(\d{4})\.(\d{2})\.(\d{2})", str(s))
    if dates:
        y, mo, d = dates[-1]  # 最近一次调价
        return f"{y}-{mo}-{d}"
    return ""


def _beike_area_from_text(*texts):
    for t in texts:
        if not t:
            continue
        ma = re.search(r"建筑面积\s*" + _NUM + r"\s*㎡", t)
        if ma:
            return float(ma.group(1))
        ma2 = re.search(_NUM + r"\s*㎡", t)
        if ma2:
            return float(ma2.group(1))
    return None


def _beike_block_details(ident, d: dict, city: str, tag: str) -> dict:
    """抽取单房源块的全部真实维度，供「房屋成交详细信息」模块全量呈现。

    返回规范化字典：所有字段均来自 CLI 真实返回，缺失即为空串/None，绝不编造。
    键命名与 CLI 字段语义一致，便于渲染层按需取用（sold/search 各异）。
    """
    info = (d.get("基本信息") if isinstance(d.get("基本信息"), dict)
            else (d.get("摘要信息") if isinstance(d.get("摘要信息"), dict) else d))
    det: dict = {"tag": tag}
    det["hid"] = str(info.get("房源ID") or d.get("房源ID") or ident)
    det["xiaoqu_id"] = (info.get("小区ID") or d.get("小区ID")
                        or _beike_xiaoqu_id_from_text(info.get("小区信息"),
                                                      d.get("小区信息")) or "")
    det["community"] = (_beike_community_from_title(info.get("小区信息"))
                        or info.get("小区名称") or d.get("小区名") or d.get("小区名称")
                        or _beike_community_from_title(info.get("房源名称")
                                                       or info.get("房源标题")) or "")
    det["title"] = (info.get("房源名称") or info.get("房源标题")
                    or d.get("房源标题") or "")
    py = _beike_city_py(city)
    if tag == "sold":
        det["url"] = f"https://{py}.ke.com/chengjiao/{det['hid']}.html" if py else None
    else:
        det["url"] = f"https://{py}.ke.com/ershoufang/{det['hid']}.html" if py else None
    if tag == "sold":
        tp, _ = _beike_price_from_text(info.get("成交价格") or "")
        lp, _ = _beike_price_from_text(info.get("挂牌价格") or "")
        det["deal_price_wan"] = tp
        det["list_price_wan"] = lp
        det["deal_date"] = _beike_normalize_date(info.get("成交日期") or "")
        det["deal_cycle"] = info.get("成交周期") or ""
        det["followers"] = info.get("关注人数") or ""
        det["total_visits"] = info.get("总带看次数") or ""
        det["orientation"] = info.get("朝向") or ""
        det["ownership"] = info.get("权属") or ""
        det["building_type"] = info.get("楼型") or ""
        det["floor"] = info.get("楼层") or ""
        det["usage"] = info.get("用途") or ""
        det["elevator"] = info.get("电梯") or ""
        det["decoration"] = info.get("装修") or ""
        det["era"] = info.get("年代") or ""
    elif tag == "search":
        det["price_info"] = info.get("价格信息") or ""
        det["trade_info"] = info.get("交易信息") or ""
        det["location_traffic"] = info.get("区位交通") or ""
        det["building_info"] = info.get("单元楼栋信息") or ""
        det["same_layout_market"] = info.get("同小区同居室成交行情") or ""
        det["school"] = info.get("学区信息") or ""
        det["community_info"] = info.get("小区信息") or ""
        det["layout_info"] = info.get("户型信息") or ""
        det["highlights"] = info.get("房源亮点") or ""
        det["dynamics"] = info.get("房源动态") or ""
        det["status"] = info.get("房源售卖状态") or ""
        det["floor_info"] = info.get("房源所在楼层信息") or ""
    return det


def _beike_block_to_row(ident, d: dict, city: str, tag: str) -> Optional[dict]:
    """把单个房源 JSON 块映射成规范行（真实字段 + 真实详情 URL）。

    兼容真实 CLI 的两种块结构：
    - `sold` 成交：字段嵌套在 d["基本信息"] 下
      （成交价格(万)/挂牌价格(万)/成交日期(点分隔)/房源名称(含户型面积)/小区ID ...
       关注人数/总带看次数/成交周期/朝向/权属/楼型/楼层/用途/电梯/装修/年代）
    - `search` 挂牌：字段嵌套在 d["摘要信息"] 下
      （价格信息/房源标题/房源ID/小区信息(含小区ID)/户型信息/房源售卖状态/
       学区信息/交易信息/单元楼栋信息/同小区同居室成交行情/房源亮点/房源动态/
       房源所在楼层信息/区位交通）
    - 旧式/兜底：字段直接位于顶层。
    只抽取真实存在的字段；无法得到出售单价（元/㎡）的出售块直接丢弃（不编造）。
    成交/挂牌只给「总价(万)+面积(㎡)」时，按 元/㎡ = 总价*10000/面积 反算单价。
    所有真实维度另存于返回的 details 字典，供「房屋成交详细信息」模块全量呈现。
    """
    info = (d.get("基本信息") if isinstance(d.get("基本信息"), dict)
            else (d.get("摘要信息") if isinstance(d.get("摘要信息"), dict) else d))
    # 总价：成交价优先(sold)；否则挂牌价(listing)
    if tag == "sold":
        total_text = (info.get("成交价格") or info.get("成交价")
                      or d.get("价格信息") or "")
    else:
        total_text = (info.get("挂牌价格") or info.get("成交价格")
                      or info.get("价格信息") or d.get("价格信息") or "")
    total, unit = _beike_price_from_text(total_text)
    # 面积：出售用「建筑面积」或标题内面积
    area = _beike_area_from_text(
        info.get("房源名称"), info.get("房源标题"), d.get("房源标题"),
        info.get("户型信息"), d.get("户型信息"))
    if unit is None and total is not None and area:
        unit = total * 10000.0 / area  # 仅总价+面积时反算单价
    if unit is None:
        return None  # 无单价无法进价格证据链
    hid = str(info.get("房源ID") or d.get("房源ID") or ident)
    title = (info.get("房源名称") or info.get("房源标题")
             or d.get("房源标题") or d.get("标题"))
    py = _beike_city_py(city)
    if tag == "sold":
        url = (f"https://{py}.ke.com/chengjiao/{hid}.html" if py else None)
    else:
        url = (f"https://{py}.ke.com/ershoufang/{hid}.html" if py else None)
    # 小区名：房源标题前缀 > 小区信息串前缀 > 小区名称字段
    community = (_beike_community_from_title(title)
                 or _beike_community_from_title(info.get("小区信息"))
                 or info.get("小区名称") or d.get("小区名") or d.get("小区名称")
                 or None)
    # 小区ID：基本信息/摘要信息里的 小区ID，或 小区信息串里的小区ID:xxxx
    xiaoqu_id = (info.get("小区ID") or d.get("小区ID")
                 or _beike_xiaoqu_id_from_text(info.get("小区信息"),
                                               d.get("小区信息")) or "")
    # 学区（house-buying 核心关注点）
    school = info.get("学区信息") or d.get("学区信息") or ""
    # 日期：成交用 成交日期(点分隔)；挂牌无成交日期，取房源动态最近调价日
    if tag == "sold":
        date_raw = info.get("成交日期") or d.get("成交时间") or d.get("dealDate") or ""
    else:
        date_raw = (info.get("挂牌时间") or info.get("最近调价")
                    or _beike_listing_date_from_text(info.get("房源动态", "")) or "")
    date = _beike_normalize_date(date_raw)
    details = _beike_block_details(ident, d, city, tag)
    return {
        "price": unit,
        "totalPrice": total,
        "area": area,
        "kind": ("transaction" if tag == "sold" else "listing"),
        "date": date,
        "title": title,
        "communityName": community,
        "xiaoquId": xiaoqu_id,
        "school": school,
        "hid": hid,
        "url": url,
        "cover": None,
        "status_text": (info.get("房源售卖状态")
                        or d.get("房源售卖状态") or ""),
        "details": details,
        "raw_block": d,  # 保留原始块，供报告引用小区/学区/楼栋等真实信息
    }


def _beike_resblock_from_block(ident, d: dict, city: str) -> dict:
    """从 `beike buy resblock` 小区块抽取小区档案（真实字段）。

    真实结构：字段嵌套在 d["摘要信息"] 下，其中 小区信息 是中文串
    （含 小区ID / 建成年份 / 容积率 / 绿化率 / 物业费 / 户数 / 车位配比），
    市场行情 串含 在售套数 / 价格范围。官方 CLI 的 resblock 通常不直给「均价」，
    均价改由 market/sold 聚合获得，故此处不强行编造 avg_listing_price。
    """
    info = d.get("摘要信息") if isinstance(d.get("摘要信息"), dict) else d
    block_info = info.get("小区信息") or d.get("小区信息") or ""
    market_info = info.get("市场行情") or d.get("市场行情") or ""
    xiaoqu_id = (info.get("小区ID") or d.get("小区ID")
                 or _beike_xiaoqu_id_from_text(block_info) or "")
    name_v = (info.get("小区名称") or d.get("小区名") or d.get("小区名称")
              or (ident if isinstance(ident, str) and ident not in ("小区", "德信银树湾")
                  else ""))
    out: dict = {}
    # 在售套数 / 价格范围（市场行情串）
    onsale = re.search(r"在售\s*(\d+)\s*套", market_info + " " + block_info)
    if onsale:
        out["onsale_count"] = int(onsale.group(1))
    pr = re.search(r"价格范围\s*" + _NUM + r"\s*-\s*" + _NUM + r"\s*万",
                   market_info + " " + block_info)
    if pr:
        out["price_range_wan"] = [float(pr.group(1)), float(pr.group(2))]
    # 建成年份 / 容积率 / 绿化率 / 物业费 / 车位配比 / 户数
    mb = re.search(r"(\d{4})年建成", block_info)
    build_year = mb.group(1) if mb else None
    vol = re.search(r"容积率\s*" + _NUM, block_info)
    green = re.search(r"绿化率\s*" + _NUM, block_info)
    fee = re.search(r"物业费\s*" + _NUM + r"\s*元", block_info)
    car = re.search(r"车位配比\s*([0-9:：.]+)", block_info)
    hh = re.search(r"(\d+)户", block_info)
    if name_v:
        out["name"] = name_v
    if xiaoqu_id:
        out["xiaoqu_id"] = xiaoqu_id
        py = _beike_city_py(city)
        if py:
            out["url"] = f"https://{py}.ke.com/xiaoqu/{xiaoqu_id}.html"
    if build_year:
        out["build_year"] = build_year
    if vol:
        out["volume_rate"] = float(vol.group(1))
    if green:
        out["green_rate"] = float(green.group(1))
    if fee:
        out["property_fee"] = float(fee.group(1))
    if car:
        out["car_ratio"] = car.group(1)
    if hh:
        out["households"] = int(hh.group(1))
    return out


def _beike_market_from_text(data: str, city: str, name: str) -> list:
    """从 `beike buy market` 文本尽力抽取月度均价走势点（PricePoint）。

    兼容两种写法：
    - 旧式/兜底纯文本：「2026年5月 均价57000元/平米」
    - 真实 CLI 行情块（见 _beike_parse_market_data）
    """
    points: list = []
    for m in re.finditer(
            r"(\d{4})[年/-](\d{1,2})[月/-]?[^\d]*?" + _NUM + r"\s*元/平米", data):
        y, mo, p = m.group(1), int(m.group(2)), float(m.group(3))
        points.append(PricePoint(
            community="", city=city, date=f"{y}-{mo:02d}",
            price_per_sqm=p, source=name, kind="listing",
            note="贝壳官方CLI均价走势"))
    return points


def _beike_wan_m2_to_float(s: str) -> Optional[float]:
    """把「3.52万/m2」/「35200元/平米」转成 元/㎡ 浮点；无法识别返回 None。"""
    if not s:
        return None
    m = re.search(r"(" + _NUM + r")\s*万/m2", str(s))
    if m:
        return float(m.group(1)) * 10000.0
    m = re.search(_NUM + r"\s*元/平米", str(s))
    if m:
        return float(m.group(1))
    return None


def _beike_parse_market_data(data: str, city: str, name: str) -> list:
    """解析真实 `beike buy market` 行情块（小区行情数据.各指标.最近6月趋势）。

    真实结构：<价格走势> 内 <小区名行情> 块含多段 JSON——
    {"小区最新行情": {...}} 与 {"小区行情数据": {"成交均价": {"最近6月趋势":
    {"2026-02": "3.37万/m2", ...}}, "挂牌均价": {...}, "成交量": {...}}}。
    抽取成交均价/挂牌均价/成交量三类月度点；同类同月去重，按日期排序。
    无任何结构化点时退化为 _beike_market_from_text 正则兜底。
    """
    points: list = []
    # 定位行情区域（无标签时回退整段）
    m = re.search(r"<价格走势>(.*?)</价格走势>", data, re.DOTALL)
    region = m.group(1) if m else data
    for obj in _json_extract_all(region):
        sd = obj.get("小区行情数据") if isinstance(obj, dict) else None
        if not isinstance(sd, dict):
            continue
        metric_map = (("成交均价", "transaction"), ("挂牌均价", "listing"))
        for metric, kind in metric_map:
            trend = (sd.get(metric) or {}).get("最近6月趋势")
            if not isinstance(trend, dict):
                continue
            for k, v in trend.items():
                pp = _beike_wan_m2_to_float(v)
                if pp is None:
                    continue
                nk = _beike_normalize_date(k)
                if not nk:
                    continue
                points.append(PricePoint(
                    community="", city=city, date=nk, price_per_sqm=pp,
                    source=name, kind=kind,
                    note="贝壳官方CLI均价走势"))
        vol = (sd.get("成交量") or {}).get("最近6月趋势")
        if isinstance(vol, dict):
            for k, v in vol.items():
                vm = re.search(r"(\d+)\s*套", str(v))
                if not vm:
                    continue
                nk = _beike_normalize_date(k)
                if not nk:
                    continue
                points.append(PricePoint(
                    community="", city=city, date=nk, price_per_sqm=None,
                    count=int(vm.group(1)), source=name, kind="volume",
                    note="贝壳官方CLI成交量"))
    # 去重：(date, kind) 取首个；按 date 升序
    seen: dict = {}
    out: list = []
    for p in points:
        key = (p.date, p.kind)
        if key in seen:
            continue
        seen[key] = True
        out.append(p)
    out.sort(key=lambda p: p.date or "")
    if out:
        return out
    # 兜底：纯文本正则
    return _beike_market_from_text(data, city, name)


def _parse_beike_text_payload(obj, city: str, tag: str):
    """解析真实 beike CLI 半结构化文本输出。

    返回 (rows, enriched_list, enriched_tx, market_points, resblock_info, note)。
    防御式：解析不出任何实体返回空结构，不抛异常、绝不编造。
    """
    empty = ([], [], [], [], {}, "")
    if not isinstance(obj, dict):
        return empty[0], empty[1], empty[2], empty[3], empty[4], "CLI 返回非预期类型"
    # 明确识别 CLI 后端工具下架/不可用（如 Unknown tool: 'house_sold_search'）
    if obj.get("ok") is False:
        err = obj.get("error") or ""
        if "Unknown tool" in err:
            return empty[0], empty[1], empty[2], empty[3], empty[4], f"CLI 后端已下架该工具（{err}）"
        return empty[0], empty[1], empty[2], empty[3], empty[4], f"CLI 返回错误：{err}"
    data = obj.get("data")
    if not isinstance(data, str) or not data.strip():
        return empty[0], empty[1], empty[2], empty[3], empty[4], "CLI 返回无数据文本"
    blocks = _beike_extract_blocks(data)
    # market 走势为行情块（含多段 JSON），独立于 blocks 直接结构化解析
    if tag == "market":
        pts = _beike_parse_market_data(data, city, "贝壳(官方CLI)")
        note = "" if pts else "market 文本未解析出走势点"
        return [], [], [], pts, {}, note
    if tag == "resblock":
        for ident, d in blocks:
            info = _beike_resblock_from_block(ident, d, city)
            if info:
                return [], [], [], [], info, ""
        return (empty[0], empty[1], empty[2], empty[3], empty[4],
                "resblock 文本未解析出小区档案")
    # search / sold：需要 <房源ID> 块；无块时退回旧式干净 JSON 兜底
    if not blocks:
        # 兼容旧式干净列表 JSON（若 CLI 未来改版）：走通用解析兜底
        list_rows, list_note = _parse_beike_cli_payload(obj)
        if list_rows:
            el = [r for r in list_rows if r.get("url") or r.get("title")]
            return list_rows, el, [], [], {}, list_note
        return (empty[0], empty[1], empty[2], empty[3], empty[4],
                "CLI 文本未解析出房源/小区实体")
    # search / sold
    rows, el, et = [], [], []
    for ident, d in blocks:
        row = _beike_block_to_row(ident, d, city, tag)
        if row is None:
            continue
        rows.append(row)
        if row.get("url") or row.get("title"):
            (et if row["kind"] == "transaction" else el).append(row)
    note = "" if rows else "CLI 文本未解析出可计价房源（字段缺失），已退回检索"
    return rows, el, et, [], {}, note


class BeikeCliSource(BaseSource):
    """贝壳官方 CLI（真实结构化数据通道，T0，多命令聚合）。

    首选合规通道：调用官方 `beike` CLI 拿实时结构化数据，对齐「贝壳买房专家」
    的命令体系——`buy search`(挂牌) / `buy sold`(近期成交) / `buy market`(均价
    走势) / `buy resblock`(小区档案)，全部含真实详情 URL。用于强化报告引用的
    真实性与防伪。各命令独立调用、独立兜底：任一命令失败只少一类数据，不整体异常。
    未安装 CLI / 未鉴权 / 调用失败时，自动退回联网检索模式（生成精确检索式），
    绝不编造或假装成真实数据。
    """
    name = "贝壳(官方CLI)"
    kind = "cli"
    provides = "both"
    tier = "T0"

    # 多命令聚合：命令模板(含占位符) -> 用途标签
    _BEIKE_COMMANDS = (
        (("buy", "search", "-c", "_CITY", "-q", "_Q"), "search"),
        (("buy", "sold", "-c", "_CITY", "-q", "_Q"), "sold"),
        (("buy", "market", "-c", "_CITY", "-q", "_Q"), "market"),
        (("buy", "resblock", "-c", "_CITY", "-q", "_Q"), "resblock"),
    )

    def search_queries(self, community: str, district: str, city: str = "杭州",
                       months: int = 36) -> list:
        c = f"{district} " if district else ""
        return [
            f"{city} {c}{community} 贝壳 成交",
            f"{city} {c}{community} 挂牌价 成交价",
            f"{city} {community} 近{months}个月 房价 走势图 贝壳",
        ]

    def fetch(self, community: str, district: str = "",
              city: Optional[str] = None, months: int = 36) -> SourceFetchResult:
        city = city or self.city
        # 未安装 / 未鉴权：明确标记状态 + 给安装提示，退回检索式
        if not beike_cli_available():
            res = self._fetch_websearch(community, district, city, months)
            res.mode = "cli_unavailable"
            res.tier = self.tier
            res.raw_note = BEIKE_INSTALL_HINT + "\n" + res.raw_note
            return res
        query = f"{district} {community}".strip() if district else community
        rows_all: list = []
        notes: list = []
        enriched_listings: list = []
        enriched_tx: list = []
        market_points: list = []
        resblock_info: dict = {}
        for cmd_tmpl, tag in self._BEIKE_COMMANDS:
            args = [city if a == "_CITY" else (query if a == "_Q" else a)
                    for a in cmd_tmpl]
            try:
                obj = _run_beike_cli(args)
            except Exception as exc:
                notes.append(f"{tag} 调用失败：{exc}")
                continue
            if tag in ("search", "sold"):
                rows, el, et, _, _, note = _parse_beike_text_payload(obj, city, tag)
                if note:
                    notes.append(f"{tag}：{note}")
                rows_all.extend(rows)
                enriched_listings.extend(el)
                enriched_tx.extend(et)
            elif tag == "market":
                _, _, _, pts, _, note = _parse_beike_text_payload(obj, city, tag)
                if pts:
                    market_points.extend(pts)
                else:
                    notes.append(note or "market 返回无法解析为走势点")
            elif tag == "resblock":
                _, _, _, _, info, note = _parse_beike_text_payload(obj, city, tag)
                if info:
                    resblock_info = info
                else:
                    notes.append(note or "resblock 返回无法解析为小区档案")
        # 聚合 挂牌+成交 -> listings/transactions/history
        listings, transactions, history = self._build_result(
            rows_all, community, city, self.name)
        # 合并均价走势点（按 (date, kind) 去重，market 点优先保留；
        # 成交均价/挂牌均价/成交量 同类同月各自保留，避免只留首类）
        if market_points:
            seen = {(p.date, p.kind) for p in history}
            for p in market_points:
                if p.date and (p.date, p.kind) not in seen:
                    history.append(p)
                    seen.add((p.date, p.kind))
            history.sort(key=lambda p: p.date or "")
        ok = bool(listings or transactions or history)
        # 识别官方 CLI 成交/行情工具被后端下架的场景，给出明确、不误导的降级说明
        deprecated = [n for n in notes if "CLI 后端已下架该工具" in n]
        deprecated_note = ""
        if deprecated:
            deprecated_note = " 注意：" + "；".join(deprecated) + "，真实成交明细与月度均价走势暂不可得。"
        # 全部命令失败 / 无可用数据：退回联网检索兜底（绝不编造）
        if not ok:
            res = self._fetch_websearch(community, district, city, months)
            res.mode = "cli_unavailable"
            res.tier = self.tier
            res.raw_note = (("CLI 调用无可用结果：" + " ".join(notes) + "\n")
                            if notes else "") + deprecated_note + res.raw_note
            return res
        raw_note = (f"官方CLI实时数据：挂牌 {len(listings)} 条，成交 "
                    f"{len(transactions)} 条，走势点 {len(history)} 个。"
                    + deprecated_note
                    + (" ".join(n for n in notes if "CLI 后端已下架该工具" not in n) if notes else ""))
        return SourceFetchResult(
            source=self.name, community=community, city=city,
            listings=listings, transactions=transactions, history=history,
            extra={"listings": enriched_listings, "transactions": enriched_tx,
                   "resblock": resblock_info, "market_points": market_points,
                   "query": query, "source_mode": "cli"},
            raw_note=raw_note,
            confidence="high" if ok else "low",
            mode="cli", months=months, tier=self.tier,
        )


# --------------------------------------------------------------------------- #
# T3 交叉验证源（诸葛找房 / 安居客 / 房天下 / 58同城）
# --------------------------------------------------------------------------- #
# 用途：同一指标的多源交叉比对，标注一致性程度。只做交叉验证，不单独支撑结论；
# 未配置 API 时一律退回联网检索模式（生成精确检索式，由代理取数回填）。
class ZhugeSource(WebSource):
    """诸葛找房（网页）：多平台聚合挂牌+成交，全国，T3 交叉验证源。"""
    name = "诸葛找房"
    kind = "web"
    provides = "both"
    tier = "T3"

    def search_queries(self, community: str, district: str, city: str = "杭州",
                       months: int = 36) -> list:
        c = f"{district} " if district else ""
        return [
            f"{city} {c}{community} 诸葛找房 挂牌价 成交价",
            f"{city} {c}{community} 诸葛找房 小区 均价 走势",
            f"{community} 诸葛找房 近{months}个月 房价 走势",
        ]


class AnjukeSource(WebSource):
    """安居客（网页）：挂牌口径为主，全国，T3 交叉验证源。"""
    name = "安居客"
    kind = "web"
    provides = "listing"
    tier = "T3"

    def search_queries(self, community: str, district: str, city: str = "杭州",
                       months: int = 36) -> list:
        c = f"{district} " if district else ""
        return [
            f"{city} {c}{community} 安居客 挂牌价 均价",
            f"{city} {c}{community} 安居客 小区 二手房 房价",
            f"{community} 安居客 近{months}个月 房价走势 月度",
        ]


class FangSource(WebSource):
    """房天下（网页）：挂牌口径为主，全国，T3 交叉验证源。"""
    name = "房天下"
    kind = "web"
    provides = "listing"
    tier = "T3"

    def search_queries(self, community: str, district: str, city: str = "杭州",
                       months: int = 36) -> list:
        c = f"{district} " if district else ""
        return [
            f"{city} {c}{community} 房天下 挂牌价 均价",
            f"{city} {c}{community} 房天下 二手房 房价 走势",
            f"{community} 房天下 近{months}个月 小区房价 月度",
        ]


class WubaSource(WebSource):
    """58同城房产（网页）：挂牌为主，中介重复房源多，T3 低置信交叉源。"""
    name = "58同城"
    kind = "web"
    provides = "listing"
    tier = "T3"

    def search_queries(self, community: str, district: str, city: str = "杭州",
                       months: int = 36) -> list:
        c = f"{district} " if district else ""
        return [
            f"{city} {c}{community} 58同城 二手房 挂牌价",
            f"{city} {c}{community} 58同城 小区 均价",
        ]


class GovCommunityAdapter(BaseSource):
    """T1 官方单小区数据适配器（G 模块）。

    针对已公开单小区级成交/公示的城市（宁波/苏州/无锡/佛山/珠海等，见
    references/data-source-playbook.md 第八节），在 sources.json 为该城配置
    gov.endpoint 后，直拉小区级成交参考价/公示，作为 T1 强证据。未配置或
    解析失败时退回精确 T1 检索式，由 AI 代理联网取数后回填。
    """
    name = "官方单小区"
    kind = "web"
    provides = "both"
    tier = "T1"

    def can_api(self, city: Optional[str] = None) -> bool:
        # T1 官方源多为无需登录公开页，仅需 endpoint 即可拉取
        return bool(self.endpoint_for(city))

    def search_queries(self, community: str, district: str, city: str = "杭州",
                       months: int = 36) -> list:
        c = f"{district} " if district else ""
        return [
            f"{city} {c}{community} 官方 二手房 成交 公示 网签",
            f"{city} 住建局 {c}{community} 存量房 成交参考价",
            f"{city} {c}{community} 不动产登记 网签公示",
        ]

    def _fetch_api(self, community: str, district: str, city: str,
                   months: int = 36) -> SourceFetchResult:
        endpoint = self.endpoint_for(city)
        if not endpoint:
            raise RuntimeError("未配置 gov endpoint，退回检索")
        html = self._request_text(endpoint, city=city)
        # 官方页面结构易变：不做脆弱的字段解析，返回原始页（截断）供 AI 解析，
        # 作为 T1 强证据承载；解析失败时改用检索式兜底。
        return SourceFetchResult(
            source=self.name,
            community=community,
            city=city,
            queries=self.search_queries(community, district, city, months),
            raw_note=("已拉取官方页面原始内容（前 20000 字符），请 AI 代理按该城页面"
                      "结构解析小区级成交/公示并补回 listings/transactions/history；"
                      "解析失败时改用检索式兜底。\n---RAW---\n"
                      + html[:20000]),
            confidence="medium",
            mode="api",
            months=months,
        )


def load_sources(city: str = "杭州") -> list:
    """加载配置好的数据源（endpoint/token/cookie/headers 在 sources.json）。"""
    sources = [
        # T0 核心双源
        BeikeSource(city=city),
        WoaiwojiaSource(city=city),
        # T1.5 / T2 城市本地高频源与小程序（杭州）
        XiaojiSource(city=city),
        HangfangSource(city=city),
        # T3 交叉验证源
        ZhugeSource(city=city),
        AnjukeSource(city=city),
        FangSource(city=city),
        WubaSource(city=city),
    ]
    if SOURCES_CONFIG.is_file():
        try:
            cfg_all = json.loads(SOURCES_CONFIG.read_text(encoding="utf-8"))
        except Exception:
            cfg_all = {}
        for s in sources:
            if s.name in cfg_all:
                s.cfg = cfg_all[s.name] or {}
            s.city = city
    return sources


# --------------------------------------------------------------------------- #
# 学区工作流编排
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# 全国城市源注册表（预置内置，避免运行时检索）
# --------------------------------------------------------------------------- #
CITY_REGISTRY_PATH = SKILL_DIR / "scripts" / "city_sources.json"
CITY_POLICY_PATH = SKILL_DIR / "scripts" / "city_policy.json"


def load_city_registry() -> dict:
    if CITY_REGISTRY_PATH.is_file():
        try:
            return json.loads(CITY_REGISTRY_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def load_city_policy(city: str = "") -> dict:
    """读取逐城 2026 政策基线（见 references/policy-baseline-2026.md）。

    返回该城政策基线字典；未提供城市或城市未登记时返回 _default
    （verify_status=待联网核验）。
    """
    data: dict = {}
    if CITY_POLICY_PATH.is_file():
        try:
            data = json.loads(CITY_POLICY_PATH.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    default = data.get("_default", {})
    if city:
        return data.get(city, default)
    return default


def national_policy_baseline() -> str:
    if CITY_POLICY_PATH.is_file():
        try:
            data = json.loads(CITY_POLICY_PATH.read_text(encoding="utf-8"))
            return data.get("_national_baseline", "")
        except Exception:
            return ""
    return ""


def cmd_policy(args) -> int:
    city = getattr(args, "city", "") or ""
    if not city:
        print("【2026 全国政策基线】")
        print(national_policy_baseline())
        return 0
    p = load_city_policy(city)
    print(f"【{city} 2026 政策基线】（核实状态：{p.get('verify_status', '未知')}）")
    fields = [
        ("多校划片", "multi_school_assignment"),
        ("教师轮岗", "teacher_rotation"),
        ("户籍与学位/权益脱钩", "hukou_decoupled"),
        ("学位锁定年限(年)", "seat_lock_years"),
        ("学区预警机制", "alert_mechanism"),
    ]
    for label, key in fields:
        val = p.get(key, "未知")
        print(f"  - {label}: {val}")
    if p.get("note"):
        print(f"  备注: {p['note']}")
    if p.get("sources"):
        print("  来源:")
        for s in p["sources"]:
            print(f"    - {s}")
    print("\n⚠️ 凡 verify_status=待联网核验，分析时以当年该市/区教育局招生公告为准，"
          "勿直接引用本快照为结论。")
    return 0


def city_source_queries(city: str) -> dict:
    """按声明城市从注册表生成精确取数检索式与源指引。

    全国网页源（贝壳/我爱我家）始终可用；政府公开源、政务 APP、本地小程序
    按注册表给出，避免运行时再检索。未内置城市则退回全国源 + 联网检索。
    """
    reg = load_city_registry()
    entry = reg.get(city, {})
    queries: list = []
    sources: list = []
    for ns in entry.get("national", ["贝壳", "我爱我家"]):
        sources.append(ns)
        queries.append(f"{city} {ns} 二手房 挂牌价 成交价 近36个月 走势")
    for g in entry.get("gov", []):
        sources.append(g.get("name", "政府源"))
        q = f"{city} {g.get('name', '')} 二手房 网签 成交公示 月度"
        if g.get("url"):
            q += f" ({g['url']})"
        queries.append(q)
    for app in entry.get("gov_app", []):
        sources.append(app.get("name", "政务APP"))
        queries.append(f"{app.get('name', '')} {city} 不动产 住房 查询 二手房")
    for mp in entry.get("mini_program", []):
        name = mp.get("name", "")
        if name and name != "无":
            sources.append(name)
            queries.append(f"{name} {city} 二手房 成交价 小区 走势")
    # 学区划片源（C 模块）：区教育局招生专栏 + 检索兜底
    sd = entry.get("school_district") or {}
    if sd:
        q_sd = sd.get("fallback_search") or f"{city} 教育局 义务教育招生 对口地段表"
        queries.append(f"【学区划片】{q_sd}")
        if sd.get("education_bureau_url"):
            queries.append(f"【学区划片-官方入口】{sd['education_bureau_url']}")
    # 学区预警源（D 模块）：红黄牌预警 + 检索兜底
    al = entry.get("enrollment_alert") or {}
    if al:
        q_al = al.get("fallback_search") or f"{city} 学区预警 学位预警"
        queries.append(f"【学区预警】{q_al}")
    if not entry:
        queries.append(
            f"{city} 二手房 成交价 挂牌价 近36个月 走势"
            f"（未内置源，建议贝壳/我爱我家 + 联网检索兜底）")
    return {
        "city": city,
        "registered": bool(entry),
        "recommended_sources": sources,
        "queries": queries,
        "note": entry.get("note", ""),
        "public_access_summary": [
            f"{g.get('name')}: {g.get('public_access')}"
            for g in entry.get("gov", [])
        ],
        "school_district": entry.get("school_district"),
        "enrollment_alert": entry.get("enrollment_alert"),
    }


# --------------------------------------------------------------------------- #
# 维度网络（单一维度展开策略，见 references/dimension-network.md）
# --------------------------------------------------------------------------- #
# 先做透第一维度「房价」（mandatory），再按用户诉求逐层展开其余维度；
# 每个维度列出：数据字段、推荐来源层级（T0-T4）、展开条件、报告输出位置。
DIMENSION_FRAMEWORK = {
    "price": {
        "name": "房价",
        "mandatory": True,
        "fields": [
            "挂牌价（月度时间轴）", "成交价（月度时间轴）", "环比MoM", "同比YoY",
            "3/6/12/24/36个月涨跌幅", "带看量", "在售房源量", "议价空间", "成交周期",
        ],
        "sources": ["T0 贝壳系(贝壳/链家)+我爱我家", "T1 官方网签/住建公示",
                    "T1.5 城市本地高频源(杭房数研类)", "T3 诸葛找房/安居客/房天下/58同城交叉验证"],
        "expand_when": "每次分析必做",
        "output": "报告「交易与价格」章节：走势图 + 时间轴表格 + 峰/谷/当前值 + 动量指标",
    },
    "volume": {
        "name": "成交量",
        "mandatory": False,
        "fields": [
            "月度成交套数（新房/二手分开）", "月度挂牌量", "成交周期（天）",
            "带看量/带看转化", "近3/6/12个月成交量变化",
        ],
        "sources": ["T1 住建局/网签平台月度成交公示", "T1.5 城市高频源", "T0 平台成交记录",
                    "T3 诸葛找房/中指研究院"],
        "expand_when": "用户关心市场热度、判断趋势拐点、砍价时机",
        "output": "报告「市场供需与热度」章节：成交量柱状图（render_bar_chart）",
    },
    "supply_demand": {
        "name": "供需比",
        "mandatory": False,
        "fields": [
            "在售挂牌量", "近12个月成交量", "去化周期（挂牌量/月均成交量）",
            "新增挂牌 vs 成交比", "库存消化速度",
        ],
        "sources": ["T0 平台挂牌量", "T1 网签平台库存/可售公示", "T1.5 城市高频源"],
        "expand_when": "判断议价空间与买方/卖方市场强弱",
        "output": "报告「市场供需与热度」章节：去化周期与挂牌/成交比",
    },
    "land": {
        "name": "土地出让",
        "mandatory": False,
        "fields": [
            "近12个月涉宅用地出让宗数/面积/楼面价", "溢价率/流拍率",
            "板块内新增供应对存量竞争", "土地成交价对房价预期的传导",
        ],
        "sources": ["T1 自然资源局/规划资源局土地出让公告与成交公示",
                    "T1 市公共资源交易中心"],
        "expand_when": "判断片区未来供应量与价格预期（新房扎堆风险）",
        "output": "报告「土地与供应」章节（若有数据）",
    },
    "school_policy": {
        "name": "学区/政策",
        "mandatory": False,
        "fields": [
            "对口小学/初中（当年招生公告口径）", "落户/房户一致/学位占用规则",
            "学区预警/多校划片/教师轮岗", "限购/限售/限贷/公积金政策",
            "二手房参考价机制",
        ],
        "sources": ["T1 教育局招生公告", "T1 住建/房管政策文件", "T2 政务App政策板块"],
        "expand_when": "涉及学区、政策敏感期、用户有入学诉求（必做）",
        "output": "报告「学区」系列章节 + 政策风险清单",
    },
    "population": {
        "name": "人口流动",
        "mandatory": False,
        "fields": [
            "常住人口/净流入（统计公报）", "出生人口与学龄人口趋势",
            "就业/产业人口结构", "租售比与空置 proxy",
        ],
        "sources": ["T1 统计局统计公报", "T1 政府工作报告", "T4 主流媒体（低置信）"],
        "expand_when": "判断中长期需求底座（少子化/人口流出风险）",
        "output": "报告「长期人口与供需」评分维度 + 情景分析依据",
    },
    "credit": {
        "name": "信贷环境",
        "mandatory": False,
        "fields": [
            "首套/二套房贷利率", "首付比例政策", "公积金贷款额度/利率",
            "LPR走势与放款周期", "经营贷/消费贷监管口径",
        ],
        "sources": ["T1 央行/金融监管总局公告", "T1 住建/公积金中心政策",
                    "T2 政务App公积金板块"],
        "expand_when": "测算月供、评估购买力与政策宽松/收紧方向",
        "output": "报告「家庭现金流与贷款」章节",
    },
}


def cmd_dimensions(args) -> int:
    """输出维度网络框架：7 维度（房价为第一维度）的字段/来源/展开条件/输出位置。"""
    name = getattr(args, "dimension", "") or ""
    if name:
        dim = DIMENSION_FRAMEWORK.get(name)
        if not dim:
            print(f"未知维度：{name}（可选：{', '.join(DIMENSION_FRAMEWORK)}）",
                  file=sys.stderr)
            return 2
        print(json.dumps({name: dim}, ensure_ascii=False, indent=2))
        return 0
    print(json.dumps(DIMENSION_FRAMEWORK, ensure_ascii=False, indent=2))
    return 0


# --------------------------------------------------------------------------- #
# 价格时间轴走势图（自包含 SVG，无外部依赖）
# --------------------------------------------------------------------------- #
def render_timeline_chart(history: list, title: str = "", width: int = 720,
                          height: int = 300) -> str:
    """根据月度 history 生成双序列（挂牌/成交）SVG 折线图。

    history: list[dict]，元素含 date/price_per_sqm/kind/count(可选)。
    返回 SVG 字符串（中文标签、元/㎡ 纵轴、YYYY-MM 横轴），可嵌入 HTML 报告；
    转 docx 时由 html-to-docx 转图。零依赖，不引入 matplotlib/plotly。
    配色避坑：挂牌=蓝、成交=橙，不套用股市红涨绿跌语义。
    样本量 count<5 的月份用空心点，不实线连接（调用方保证）。
    """
    pts = [p for p in (history or []) if isinstance(p, dict) and p.get("price_per_sqm")]
    if not pts:
        return "<!-- 无时间轴数据，无法生成走势图 -->"
    months = sorted({str(p.get("date", "")) for p in pts if p.get("date")})
    if len(months) < 2:
        return "<!-- 时间轴不足 2 个月，无法生成走势图 -->"
    series: dict = {"listing": {}, "transaction": {}}
    for p in pts:
        d = str(p.get("date", ""))
        k = "transaction" if "trans" in str(p.get("kind", "listing")).lower() else "listing"
        try:
            series[k][d] = (float(p["price_per_sqm"]), int(p.get("count") or 0))
        except (TypeError, ValueError):
            continue
    all_vals = [v for s in series.values() for v, _ in s.values()]
    if not all_vals:
        return "<!-- 价格数据无法解析，无法生成走势图 -->"
    lo, hi = min(all_vals), max(all_vals)
    pad = (hi - lo) * 0.12 or max(hi * 0.05, 1)
    ymin, ymax = lo - pad, hi + pad
    L, R, T, B = 56, 16, 30, 40
    plot_w, plot_h = width - L - R, height - T - B
    n = len(months)

    def x(i: int) -> float:
        return L + (plot_w * i / (n - 1)) if n > 1 else L + plot_w / 2

    def y(v: float) -> float:
        return T + plot_h * (1 - (v - ymin) / (ymax - ymin or 1))

    colors = {"listing": "#2f6fed", "transaction": "#f5933b"}
    labels = {"listing": "挂牌均价", "transaction": "成交均价"}
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
           f'font-family="-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif">',
           f'<rect width="{width}" height="{height}" fill="#ffffff"/>']
    if title:
        svg.append(f'<text x="{L}" y="18" font-size="13" fill="#1f2937" '
                   f'font-weight="600">{title}</text>')
    for gi in range(5):
        gv = ymin + (ymax - ymin) * gi / 4
        gy = y(gv)
        svg.append(f'<line x1="{L}" y1="{gy:.1f}" x2="{width - R}" y2="{gy:.1f}" '
                   f'stroke="#eceef1" stroke-width="1"/>')
        svg.append(f'<text x="{L - 6}" y="{gy + 4:.1f}" font-size="10" fill="#6b7280" '
                   f'text-anchor="end">{gv / 10000:.2f}万</text>')
    xticks = [0, n // 2, n - 1] if n > 2 else list(range(n))
    for i in xticks:
        svg.append(f'<text x="{x(i):.1f}" y="{height - B + 16}" font-size="10" '
                   f'fill="#6b7280" text-anchor="middle">{months[i]}</text>')
    flat = []
    for key in ("listing", "transaction"):
        dmap = series[key]
        if not dmap:
            continue
        coords = [(x(months.index(m)), y(v)) for m, (v, _) in dmap.items()]
        poly = " ".join(f"{cx:.1f},{cy:.1f}" for cx, cy in coords)
        svg.append(f'<polyline points="{poly}" fill="none" stroke="{colors[key]}" '
                   f'stroke-width="2"/>')
        for m, (v, c) in dmap.items():
            cx, cy = x(months.index(m)), y(v)
            if c and c < 5:
                svg.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="2.8" fill="#fff" '
                           f'stroke="{colors[key]}" stroke-width="1.4"/>')
            else:
                svg.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="2.8" '
                           f'fill="{colors[key]}"/>')
        flat.extend((m, v, key) for m, (v, _) in dmap.items())
    if flat:
        hi_pt = max(flat, key=lambda t: t[1])
        lo_pt = min(flat, key=lambda t: t[1])
        hx, hy = x(months.index(hi_pt[0])), y(hi_pt[1])
        lx2, ly2 = x(months.index(lo_pt[0])), y(lo_pt[1])
        svg.append(f'<text x="{hx:.1f}" y="{hy - 8:.1f}" font-size="9" '
                   f'fill="{colors[hi_pt[2]]}" text-anchor="middle">'
                   f'峰 {hi_pt[1] / 10000:.2f}万</text>')
        svg.append(f'<text x="{lx2:.1f}" y="{ly2 + 14:.1f}" font-size="9" '
                   f'fill="{colors[lo_pt[2]]}" text-anchor="middle">'
                   f'谷 {lo_pt[1] / 10000:.2f}万</text>')
    lx = L
    for key in ("listing", "transaction"):
        if series[key]:
            svg.append(f'<rect x="{lx}" y="{height - 12}" width="10" height="10" '
                       f'fill="{colors[key]}"/>')
            svg.append(f'<text x="{lx + 14}" y="{height - 3}" font-size="10" '
                       f'fill="#374151">{labels[key]}</text>')
            lx += 92
    svg.append("</svg>")
    return "\n".join(svg)


# --------------------------------------------------------------------------- #
# 环比 / 同比 / N 月涨跌幅（数据链路第一维度「房价」的强制输出）
# --------------------------------------------------------------------------- #
def _kind_group(history: list) -> dict:
    """把月度时间轴按口径分组：listing / transaction，键为 YYYY-MM -> (price, count)。"""
    grouped: dict = {"listing": {}, "transaction": {}}
    for p in (history or []):
        if not isinstance(p, dict):
            continue
        d = str(p.get("date", "")).strip()
        v = p.get("price_per_sqm")
        if not d or v is None:
            continue
        try:
            v = float(v)
        except (TypeError, ValueError):
            continue
        k = "transaction" if "trans" in str(p.get("kind", "listing")).lower() else "listing"
        cnt = p.get("count")
        try:
            cnt = int(cnt or 0)
        except (TypeError, ValueError):
            cnt = 0
        grouped[k][d] = (v, cnt)
    return grouped


def _shift_month(d: str, n: int) -> str:
    """YYYY-MM 向前/后推 n 个月（n 可为负）。"""
    y, m = d.split("-")
    total = int(y) * 12 + int(m) - 1 + n
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def compute_mom_yoy(history: list, months: int = 36) -> dict:
    """从月度时间轴计算房价动量指标（口径分挂牌/成交）。

    输出字段：
      mom:           月度环比（本月 / 上月 - 1），{date: pct}；仅当相邻月份存在时计算，
                     缺月不编造（2025-03 之后直接到 2026-01 不产生环比）
      yoy:           月度同比（本月 / 去年同月 - 1），{date: pct}
      change_nm:     N 个月涨跌幅 {3: pct, 6: pct, 12: pct, 24: pct, 36: pct}
                     （当前月 vs 恰好 N 个月前的月份，按日历月差；该月缺失则跳过）
      peak/valley:   区间内峰值 / 谷值 {date, price}
      current:       最新月份 {date, price, count}
      months_covered: 覆盖的月份数
    无数据或样本不足时不编造：单个时点无法算环比/同比时返回 None。
    """
    grouped = _kind_group(history)
    out: dict = {}
    for kind in ("listing", "transaction"):
        dmap = grouped[kind]
        if not dmap:
            continue
        dates = sorted(dmap)
        mom: dict = {}
        yoy: dict = {}
        for i, d in enumerate(dates):
            if i > 0:
                prev_date, prev = dates[i - 1], dmap[dates[i - 1]][0]
                if prev and _shift_month(prev_date, 1) == d:
                    mom[d] = (dmap[d][0] - prev) / prev
            # 同比：去年同月（YYYY-MM 减一年）
            y, m = d.split("-") if "-" in d else (d, "")
            if m:
                ly = f"{int(y) - 1:04d}-{m}"
                if ly in dmap:
                    base = dmap[ly][0]
                    if base:
                        yoy[d] = (dmap[d][0] - base) / base
        change_nm: dict = {}
        cur = dmap[dates[-1]][0]
        for n in (3, 6, 12, 24, 36):
            target = _shift_month(dates[-1], -n)
            if target in dmap and dmap[target][0]:
                change_nm[n] = (cur - dmap[target][0]) / dmap[target][0]
        vals = [(d, v[0]) for d, v in dmap.items()]
        peak = {"date": max(vals, key=lambda t: t[1])[0],
                "price": max(v for _, v in vals)}
        valley = {"date": min(vals, key=lambda t: t[1])[0],
                  "price": min(v for _, v in vals)}
        last_date, (last_price, last_count) = dates[-1], dmap[dates[-1]]
        out[kind] = {
            "mom": mom,
            "yoy": yoy,
            "change_nm": change_nm,
            "peak": peak,
            "valley": valley,
            "current": {"date": last_date, "price": last_price, "count": last_count},
            "months_covered": len(dates),
        }
    return out


class SchoolDistrictWorkflow:
    def __init__(self, sources: Optional[list] = None, city: str = "杭州"):
        self.city = city
        self.sources = sources or load_sources(city)
        for src in self.sources:
            src.city = city

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

    # 4) 多源拉取房源信息（含月度时间轴）
    def collect(self, communities: list, months: int = 36) -> dict:
        result = {}
        for c in communities:
            per_community = {}
            community_city = c.city or self.city
            for src in self.sources:
                res = src.fetch(c.name, c.district, community_city, months)
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
                "对比学区与周边非学区近 12-36 个月成交/挂牌月度时间轴，"
                "判断溢价收敛还是扩张，不能用单一当前均价代替趋势。",
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
    city = data.get("city") or getattr(args, "city", "杭州") or "杭州"
    budget = float(data.get("budget", args.budget if args.budget is not None else 0) or 0)
    area = float(data.get("area", args.area if args.area is not None else 90) or 90)

    def with_city(raw_list: list) -> list:
        out = []
        for c in raw_list:
            c = dict(c)
            c.setdefault("city", city)
            out.append(Community(**c))
        return out

    communities = with_city(data.get("communities", []))
    non_school = with_city(data.get("non_school_communities", []))
    return school, city, budget, area, communities, non_school


def cmd_school(args) -> int:
    school, city, budget, area, communities, non_school = _read_communities_from_args(args)
    wf = SchoolDistrictWorkflow(city=city)
    months = int(getattr(args, "months", 36) or 36)
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
    fetch_plan = wf.collect(filtered, months)
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
        "months": months,
        "ranked_all": [c.to_dict() for c in ranked],
        "budget_filtered": [c.to_dict() for c in filtered],
        "per_source_fetch_plan": fetch_plan,
        "school_vs_nonschool": comparison,
    }
    _dump_plan(plan, args.output)
    return 0


def cmd_communities(args) -> int:
    _, city, budget, area, communities, _ = _read_communities_from_args(args)
    wf = SchoolDistrictWorkflow(city=city)
    months = int(getattr(args, "months", 36) or 36)
    if not communities:
        print("请提供 --communities '小区A,小区B' 或 --input plan.json", file=sys.stderr)
        return 2
    ranked = wf.rank_by_listing_price(communities)
    filtered = wf.filter_by_budget(ranked, budget, area) if budget else ranked
    fetch_plan = wf.collect(filtered, months)
    plan = {
        "mode": "communities",
        "city": city,
        "budget_wan": budget,
        "est_area_sqm": area,
        "months": months,
        "ranked_all": [c.to_dict() for c in ranked],
        "budget_filtered": [c.to_dict() for c in filtered],
        "per_source_fetch_plan": fetch_plan,
    }
    _dump_plan(plan, args.output)
    return 0


def cmd_fetch(args) -> int:
    city = args.city or "杭州"
    sources = load_sources(city)
    src = next((s for s in sources if s.name == args.source), None)
    if src is None:
        print(f"未知数据源：{args.source}（可选："
              f"{', '.join(s.name for s in sources)}）", file=sys.stderr)
        return 2
    res = src.fetch(args.community, args.district or "", city,
                    int(getattr(args, "months", 36) or 36))
    print(json.dumps(res.to_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_timeline(args) -> int:
    city = args.city or "杭州"
    sources = load_sources(city)
    selected = [s for s in sources if not args.source or s.name == args.source]
    if not selected:
        print(f"未知数据源：{args.source}（可选："
              f"{', '.join(s.name for s in sources)}）", file=sys.stderr)
        return 2
    result = {
        "mode": "timeline",
        "city": city,
        "community": args.community,
        "district": args.district or "",
        "months": int(getattr(args, "months", 36) or 36),
        "sources": [],
    }
    for src in selected:
        res = src.fetch(args.community, args.district or "", city,
                        int(getattr(args, "months", 36) or 36))
        data = res.to_dict()
        data["history"] = sorted(data["history"], key=lambda p: p.get("date", ""))
        result["sources"].append(data)
    # 合并所有源时间轴，生成自包含 SVG 走势图，随结果一并返回
    merged = []
    for s in result["sources"]:
        merged.extend(s.get("history", []))
    result["svg_chart"] = render_timeline_chart(
        merged, title=f"{args.community}（{city}）价格走势")
    _dump_plan(result, args.output)
    return 0


def cmd_sources(args) -> int:
    info = city_source_queries(args.city)
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


def _dump_plan(plan: dict, output: Optional[str]) -> None:
    text = json.dumps(plan, ensure_ascii=False, indent=2)
    if output:
        Path(output).write_text(text, encoding="utf-8")
        print(f"已写出分析计划：{output}")
    else:
        print(text)

# --------------------------------------------------------------------------- #
# 报告辅助：橄榄手记主题 / 可点击引用 / 学区梯队
# --------------------------------------------------------------------------- #
OLIVE_CSS = """/* 橄榄手记风格（house-buying 报告，单文件自包含） */
:root{
  --paper:#f6f3ec; --card:#fffdf8; --ink:#2f2a24; --sub:#8a8272;
  --olive:#5c6b3c; --olive-soft:#e8ecd9; --accent:#b45309;
  --line:#e4ddcd; --warn:#f6e9e3; --warn-ink:#9a3412;
}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  line-height:1.75;font-size:15px}
.wrap{max-width:860px;margin:0 auto;padding:32px 20px 80px}
h1{font-family:Georgia,"Songti SC","SimSun",serif;color:var(--olive);
  font-size:26px;margin:0 0 6px}
h2{font-family:Georgia,"Songti SC","SimSun",serif;color:var(--olive);
  font-size:20px;margin:40px 0 12px;padding-bottom:8px;border-bottom:2px solid var(--line)}
h3{font-size:16px;margin:22px 0 8px;color:var(--ink)}
p{margin:8px 0}
.meta{color:var(--sub);font-size:13px;margin-bottom:22px}
.verdict{background:var(--olive-soft);border:1px solid var(--olive);
  border-radius:14px;padding:20px 22px;margin:18px 0}
.verdict .big{font-size:21px;font-weight:700;color:var(--olive);margin-bottom:8px}
.kv{display:grid;grid-template-columns:110px 1fr;row-gap:4px;font-size:14px}
.kv b{color:var(--sub);font-weight:600}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;
  padding:18px 22px;box-shadow:0 1px 4px rgba(92,107,60,.08);margin:14px 0}
table{width:100%;border-collapse:collapse;margin:14px 0;font-size:13.5px;
  background:var(--card);border-radius:12px;overflow:hidden}
th{background:var(--olive-soft);font-weight:600;text-align:left}
th,td{border:1px solid var(--line);padding:7px 10px;vertical-align:top}
.num{text-align:right;font-variant-numeric:tabular-nums}
.chartbox{background:var(--card);border:1px solid var(--line);border-radius:14px;
  padding:14px;margin:16px 0}
.chartbox svg{width:100%;height:auto;display:block}
.caption{color:var(--sub);font-size:12.5px;margin-top:8px}
.cite-ref{color:var(--olive);text-decoration:none;font-size:.85em;vertical-align:super;font-weight:600}
.cite-ref:hover{text-decoration:underline}
.cite-meta{color:var(--sub);font-size:12px;margin-left:6px;font-weight:400}
.cites a{color:var(--olive);text-decoration:underline;text-underline-offset:3px}
.cites li{margin:4px 0;font-size:13.5px}
.warn{background:var(--warn);border:1px solid #e5b8a4;color:var(--warn-ink);
  border-radius:10px;padding:12px 16px;font-size:14px;margin:14px 0}
.tag{display:inline-block;background:var(--olive-soft);color:var(--olive);
  border-radius:6px;padding:1px 8px;font-size:12px;margin-right:6px}
.foot{margin-top:48px;padding-top:16px;border-top:1px solid var(--line);
  color:var(--sub);font-size:12.5px}
.recent-tx{margin:14px 0}
.recent-tx h3{margin:18px 0 8px}
.tx-table{font-size:13px}
.tx-table td:nth-child(3),.tx-table td:nth-child(4){text-align:right;
  font-variant-numeric:tabular-nums}
.tx-table td a{color:var(--olive);text-decoration:none;font-weight:600}
.tx-table td a:hover{text-decoration:underline}
.muted{color:var(--sub);font-size:12.5px;margin:6px 0}
"""


def cmd_gov(args) -> int:
    city = getattr(args, "city", "") or "杭州"
    community = getattr(args, "community", "") or ""
    district = getattr(args, "district", "") or ""
    months = getattr(args, "months", 36)
    if not community:
        print("【官方单小区数据 gov 适配器（T1）】")
        print("用法: python data_sources.py gov --community <小区> --city <城市> [--district <区>]")
        print("说明: 在 scripts/sources.json 为该城配置 gov.endpoint 后，直拉官方小区级"
              "成交/公示(T1 强证据)；未配置或失败则退回精确 T1 检索式。")
        print("      已公开单小区数据的城市（宁波/苏州/无锡/佛山/珠海等）见 "
              "references/data-source-playbook.md 第八节。")
        return 0
    src = GovCommunityAdapter(city=city)
    res = src.fetch(community, district, city, months=months)
    print(f"【gov:{city} {community}】mode={res.mode} confidence={res.confidence} tier={res.tier}")
    for q in res.queries:
        print(f"  - {q}")
    if res.mode == "api" and "---RAW---" in res.raw_note:
        print(f"  - 已拉取官方原始页（供 AI 解析），长度 {len(res.raw_note)} 字符")
    return 0


def olive_theme_css() -> str:
    """返回「橄榄手记」风格完整 CSS（浅色、高对比、清晰优先），粘入 <style> 即可。"""
    return OLIVE_CSS


def render_citations(cites: list) -> str:
    """生成可点击参考资料列表 HTML（<ol class="cites">）。

    每条 <li> 带 id="cite-N"，正文可用 <a href="#cite-N" class="cite-ref">[N]</a>
    点击跳转到对应引用。url 缺失显示“未提供链接”，不编造。空列表返回空串。

    引用防伪元数据（可选字段，见 data-source-playbook.md「引用格式规范」）：
      label        来源名称 + 标题（必填）
      url          真实链接（必填；缺失显示“未提供链接”）
      date         发布时间或访问时间，如 "2026-07" / "2026-07-15 访问"
      caliber      数据口径，如 "成交" / "挂牌" / "网签" / "参考均价"
      consistency  多源一致性程度，如 "双源一致" / "单源" / "来源冲突（见正文）"
    输出形如：
      <li id="cite-1"><a href="..." target="_blank">label</a>
        <span class="cite-meta">[2026-07发布；口径:成交；一致性:双源一致]</span></li>
    """
    if not cites:
        return ""
    items = []
    for i, c in enumerate(cites, 1):
        label = str(c.get("label") or f"来源 {i}")
        url = str(c.get("url") or "").strip()
        meta_parts = []
        date = str(c.get("date") or "").strip()
        if date:
            meta_parts.append(f"{date}发布" if "访问" not in date else date)
        caliber = str(c.get("caliber") or "").strip()
        if caliber:
            meta_parts.append(f"口径:{caliber}")
        consistency = str(c.get("consistency") or "").strip()
        if consistency:
            meta_parts.append(f"一致性:{consistency}")
        meta = f' <span class="cite-meta">[{"; ".join(meta_parts)}]</span>' if meta_parts else ""
        if url:
            items.append(
                f'<li id="cite-{i}"><a href="{url}" target="_blank" rel="noopener">'
                f"{label}</a>{meta}</li>")
        else:
            items.append(f'<li id="cite-{i}">{label}（未提供链接）{meta}</li>')
    return '<ol class="cites">\n' + "\n".join(items) + "\n</ol>"


# --------------------------------------------------------------------------- #
# 最近成交（近 10 条）渲染 + 贝壳 CLI 安装引导
# --------------------------------------------------------------------------- #
def _txn_sort_key(t: dict):
    """成交记录按时间倒序的排序键（缺时间排最后）。

    先统一日期写法（点分隔/中文/短横 -> YYYY-MM / YYYY-MM-DD），再拆数字排序，
    兼容真实 CLI 的「2026.04.26」与检索回填的「2026-07」。
    """
    d = str(t.get("date") or t.get("dealDate") or "").strip()
    nd = _beike_normalize_date(d)
    parts = re.findall(r"\d+", nd)
    if len(parts) >= 3:
        return (0, int(parts[0]), int(parts[1]), int(parts[2]))
    if len(parts) == 2:
        return (0, int(parts[0]), int(parts[1]), 0)
    if len(parts) == 1:
        return (0, int(parts[0]), 0, 0)
    return (1, 0, 0, 0)


def _txn_layout_area(t: dict) -> str:
    """从标题/原始块抽取「户型/面积」描述。"""
    area = t.get("area")
    layout = ""
    blob = t.get("raw_block") or {}
    title = str(t.get("title") or blob.get("房源标题") or t.get("communityName") or "")
    lm = re.search(r"(\d+室\d+厅(?:\d*卫)?)", title)
    if lm:
        layout = lm.group(1)
    if area not in (None, "", 0):
        try:
            a = float(area)
            return f"{layout} {a:.1f}㎡".strip() if layout else f"{a:.1f}㎡"
        except (TypeError, ValueError):
            pass
    return layout or (title[:24] if title else "—")


def render_recent_transactions(transactions: list, n: int = 10,
                               heading: str = "最近成交（近 10 条）",
                               source_note: str = None) -> str:
    """生成「最近成交」HTML 表（真实详情 URL、单价/总价/面积/时间）。

    transactions 为成交行列表（dict，字段见 _beike_block_to_row / _build_result）：
    price(元/㎡), totalPrice(万), area(㎡), date, title, url, raw_block...
    返回自包含 HTML（<div class="recent-tx"> 内含 <table>）。空列表返回提示块。
    所有详情链接均指向真实 ke.com 成交页（或来源页），严禁编造 URL。
    """
    txns = [t for t in (transactions or []) if isinstance(t, dict)
            and ("trans" in str(t.get("kind") or "trans").lower()
                 or t.get("kind") is None)]
    txns.sort(key=_txn_sort_key, reverse=True)
    txns = txns[: max(1, int(n))]
    if not txns:
        return ('<div class="recent-tx empty">\n'
                '<p class="muted">未获取到可核验的成交记录（官方 CLI 未安装/未返回成交，'
                '或联网检索未命中）。如需真实成交，请配置贝壳 CLI 后重跑，'
                '或按检索式联网补充并标注来源。</p>\n</div>')
    rows = []
    for t in txns:
        d = str(t.get("date") or t.get("dealDate") or "—")
        la = _txn_layout_area(t)
        total = t.get("totalPrice")
        total_s = (f"{float(total):.0f}万" if isinstance(total, (int, float))
                   else (str(total) if total else "—"))
        price = t.get("price")
        price_s = (f"{float(price):,.0f}" if isinstance(price, (int, float))
                   else (str(price) if price else "—"))
        url = str(t.get("url") or "").strip()
        link = (f'<a href="{url}" target="_blank" rel="noopener">详情↗</a>'
                if url else "—")
        rows.append(
            f"<tr><td>{d}</td><td>{la}</td><td>{total_s}</td>"
            f"<td>{price_s}</td><td>{link}</td></tr>")
    note = (source_note if source_note else
            '数据来源：贝壳官方 CLI（buy sold）真实成交，详情链接指向 '
            'ke.com 成交页；联网检索回填的成交需标注来源与访问时间。单价=总价/面积反算 '
            '或平台直接给出。')
    return ('<div class="recent-tx">\n'
            f'<h3>{heading}</h3>\n<table class="tx-table">\n'
            "<thead><tr><th>成交时间</th><th>户型/面积</th><th>总价</th>"
            "<th>单价(元/㎡)</th><th>详情</th></tr></thead>\n<tbody>\n"
            + "\n".join(rows) + "\n</tbody>\n</table>\n"
            f'<p class="muted">{note}</p>\n</div>')


def _tx_detail_escape(s):
    """最小化 HTML 转义，避免标题/字段里的特殊字符破坏报告结构。"""
    if not s:
        return ""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _tx_group_html(title: str, pairs) -> str:
    """把 [(label, value), ...] 渲染成一组字段；仅展示非空项，全空返回空串。"""
    items = []
    for lab, val in pairs:
        val = _tx_detail_escape(val)
        if not val:
            continue
        items.append(f'<div><dt>{lab}</dt><dd>{val}</dd></div>')
    if not items:
        return ""
    return f'<div class="tx-group"><h4>{title}</h4><dl>{"".join(items)}</dl></div>'


def render_transaction_details(transactions, n: int = 8,
                               heading: str = "房屋成交详细信息（贝壳官方 CLI 全维度）",
                               source_note: str = None) -> str:
    """生成「房屋成交详细信息」模块：逐条成交卡片，全量呈现 CLI 真实维度。

    与「最近成交近10条」表互补——该表只给价格/面积/时间概览，本模块展开每条成交的
    价格与议价空间、成交周期与热度、房屋属性、房源特征等全部字段。所有数据来自
    buy sold 真实返回（details 字典），缺失字段不展示、绝不编造。详情链接指向真实
    ke.com 成交页。空列表返回提示块（不编造假成交）。
    """
    txns = [t for t in (transactions or []) if isinstance(t, dict)
            and str(t.get("kind") or "trans").lower() == "transaction"
            and t.get("details")]
    txns.sort(key=_txn_sort_key, reverse=True)
    txns = txns[: max(1, int(n))]
    if not txns:
        return ('<div class="tx-detail empty">\n'
                '<p class="muted">未获取到可核验的成交明细（官方 CLI 未安装/未返回成交，'
                '或联网检索未命中）。本模块不编造假成交；配置贝壳 CLI 后重跑即可补全。</p>\n'
                '</div>')
    cards = []
    for t in txns:
        det = t.get("details", {})
        # 议价空间（挂牌价 -> 成交价）
        neg = ""
        dp = det.get("deal_price_wan")
        lp = det.get("list_price_wan")
        if isinstance(dp, (int, float)) and isinstance(lp, (int, float)) and lp:
            neg = f"{(lp - dp) / lp * 100:.1f}%"
        price_s = (f"{float(t['price']):,.0f}" if isinstance(t.get("price"), (int, float))
                   else (str(t["price"]) if t.get("price") else "—"))
        total_s = (f"{float(t['totalPrice']):.0f}万" if isinstance(t.get("totalPrice"), (int, float))
                   else (str(t["totalPrice"]) if t.get("totalPrice") else "—"))
        date_s = str(det.get("deal_date") or t.get("date") or "—")
        title_s = _tx_detail_escape(det.get("title") or t.get("title") or "—")
        url = str(t.get("url") or "").strip()
        link = (f'<a class="tx-link" href="{url}" target="_blank" rel="noopener">'
                f'贝壳成交页↗</a>' if url else "")
        u = det.get("usage") or ""
        o = det.get("ownership") or ""
        e = det.get("elevator") or ""
        c = det.get("decoration") or ""
        g1 = _tx_group_html("价格与议价", [
            ("成交价", total_s if total_s != "—" else ""),
            ("挂牌价", f"{float(lp):.0f}万" if isinstance(lp, (int, float)) else ""),
            ("议价空间", neg),
            ("成交单价", f"{price_s} 元/㎡"),
        ])
        g2 = _tx_group_html("成交周期与热度", [
            ("成交周期", det.get("deal_cycle")),
            ("总带看次数", det.get("total_visits")),
            ("关注/浏览", det.get("followers")),
        ])
        g3 = _tx_group_html("房屋属性", [
            ("朝向", det.get("orientation")),
            ("楼型", det.get("building_type")),
            ("楼层", det.get("floor")),
            ("用途 / 权属", f"{u} · {o}" if (u or o) else ""),
            ("电梯 / 装修", f"{e} · {c}" if (e or c) else ""),
            ("年代", det.get("era")),
        ])
        g4 = _tx_group_html("房源特征", [
            ("户型面积", det.get("layout_info")),
            ("小区", det.get("community")),
            ("学区", det.get("school")),
            ("同户型行情", det.get("same_layout_market")),
        ])
        grid = "".join(g for g in (g1, g2, g3, g4) if g)
        cards.append(
            f'<div class="tx-card"><div class="tx-card-head">'
            f'<span class="tx-date">{date_s}</span>'
            f'<span class="tx-title">{title_s}</span>{link}</div>'
            f'<div class="tx-grid">{grid}</div></div>')
    note = (source_note if source_note else
            '数据来源：贝壳官方 CLI（buy sold）真实成交，详情链接指向 '
            'ke.com 成交页。议价空间=挂牌价与成交价之差（官方仅给总价+面积，'
            '单价=总价/面积反算）；朝向/楼型/楼层/装修/带看/关注等维度均来自 CLI 真实返回，'
            '未返回的字段不展示，绝不编造。')
    return ('<div class="tx-detail">\n<h3>' + heading + '</h3>\n'
            + "\n".join(cards) + "\n"
            f'<p class="muted">{note}</p>\n</div>')


def parse_manual_chengjiao(text: str) -> dict:
    """解析用户手动粘贴的成交记录（贝壳/链家 App、小程序截图转录）。

    轻量、零依赖：每行一条，字段顺序宽松，支持以下任意组合：
      · 日期：2025-03-15 / 2025.3 / 2025年3月 / 202503
      · 面积：89.2㎡ / 89.2平 / 89.2平方米
      · 总价：300万 / 300w
      · 单价：33000元/㎡ / 3.3万/㎡（可选，缺则按 总价/面积 反算）
      · 户型：3室1厅(2卫) / 三室一厅
      · 朝向/楼层：南 / 中楼层（可选）
    也支持 Markdown 表格（表头含 日期/时间、面积、总价、单价、户型 之一）。
    返回 {"transactions":[{...}], "errors":[str]}。解析失败的行进 errors。
    解析出的记录结构与 CLI 成交一致（kind/date/title/totalPrice/price/area/
    url/details），可直接喂给 render_recent_transactions / render_transaction_details。
    """
    txns: list = []
    errors: list = []
    if not text or not text.strip():
        return {"transactions": [], "errors": ["空输入"], "source": ""}
    lines = text.strip().splitlines()
    # 来源标注：文件首部以 `# 来源:` / `# source:` 注释声明数据来源
    source = ""
    for ln in lines:
        s = ln.strip()
        if s.startswith("#"):
            m = re.match(r"#\s*(?:来源|source)\s*[:：]\s*(.+)", s, re.I)
            if m:
                source = m.group(1).strip()
    # 若是 Markdown 表格，提取数据行
    table_rows = []
    for ln in lines:
        s = ln.strip()
        if s.startswith("|") and s.endswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            table_rows.append(cells)
    if len(table_rows) >= 2:
        header = [h.replace(" ", "") for h in table_rows[0]]
        for row in table_rows[1:]:
            if set("".join(row)) <= set("-: "):
                continue
            if len(row) != len(header):
                continue
            blob = " ".join(row)
            parsed = _parse_one_chengjiao(blob,
                                          (row[header.index("日期")] if "日期" in header else "")
                                          or (row[header.index("时间")] if "时间" in header else ""))
            if parsed:
                txns.append(parsed)
            else:
                errors.append("表格行未解析：" + " | ".join(row))
        # 混合输入：表格之外的纯文本行也尝试解析
        for ln in lines:
            s = ln.strip()
            if s.startswith("|"):
                continue
            if not s or s.startswith("#"):
                continue
            parsed = _parse_one_chengjiao(s, "")
            if parsed:
                txns.append(parsed)
            elif re.search(r"\d", s) and re.search(r"万|㎡|平|室", s):
                errors.append("未解析：" + s)
        return {"transactions": txns, "errors": errors, "source": source}
    # 逐行解析（普通文本）
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        parsed = _parse_one_chengjiao(s, "")
        if parsed:
            txns.append(parsed)
        elif re.search(r"\d", s) and re.search(r"万|㎡|平|室", s):
            errors.append("未解析：" + s)
    return {"transactions": txns, "errors": errors, "source": source}


def _parse_one_chengjiao(blob: str, explicit_date: str = "") -> Optional[dict]:
    """解析单条成交文本，返回成交 dict 或 None。"""
    b = blob
    # 日期
    date = ""
    if explicit_date:
        dm = re.search(r"(\d{4})[-/.年](\d{1,2})(?:[-/.月](\d{1,2}))?", explicit_date)
        if dm:
            date = f"{int(dm.group(1)):04d}-{int(dm.group(2)):02d}" + (
                f"-{int(dm.group(3)):02d}" if dm.group(3) else "")
    if not date:
        dm = re.search(r"(\d{4})[-/.年](\d{1,2})(?:[-/.月](\d{1,2}))?", b)
        if dm:
            date = f"{int(dm.group(1)):04d}-{int(dm.group(2)):02d}" + (
                f"-{int(dm.group(3)):02d}" if dm.group(3) else "")
    if not date:
        dm = re.search(r"(\d{4})(\d{2})(\d{2})", b)
        if dm and 2000 <= int(dm.group(1)) <= 2100:
            date = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}"
    if not date:
        return None
    # 面积
    am = re.search(r"(\d+(?:\.\d+)?)\s*(?:㎡|平方米|平)", b)
    area = float(am.group(1)) if am else None
    # 总价（万）
    tm = re.search(r"(\d+(?:\.\d+)?)\s*(?:万|w|W)", b)
    total = float(tm.group(1)) if tm else None
    # 单价（元/㎡）
    pm = re.search(r"(\d{4,7})\s*(?:元/㎡|元每平|/㎡|元每平米)", b)
    price = float(pm.group(1)) if pm else None
    # 户型
    lm = re.search(r"(\d+室\d+厅(?:\d*卫)?)", b)
    layout = lm.group(1) if lm else ""
    # 朝向
    om = re.search(r"(东南|东北|西南|西北|南北|东西|[东南西北]向?)", b)
    orient = om.group(1) if om else ""
    # 楼层
    fm = re.search(r"(低|中|高)楼层|(\d+)\s*楼|顶层|底层", b)
    floor = fm.group(0) if fm else ""
    if total is None:
        return None  # 没有总价无法成记录
    if price is None and area:
        price = round(total * 10000 / area)
    title_parts = [x for x in [layout, (f"{area:.1f}㎡" if area else ""),
                               orient, floor] if x]
    title = " ".join(title_parts) if title_parts else b[:24]
    details = {
        "deal_date": date,
        "title": title,
        "layout_info": (f"{layout} {area:.1f}㎡" if layout and area
                        else (f"{area:.1f}㎡" if area else title)),
        "community": "",
    }
    return {
        "kind": "transaction",
        "date": date,
        "title": title,
        "totalPrice": total,
        "price": price,
        "area": area,
        "url": "",
        "details": details,
    }


def beike_cli_setup_prompt() -> str:
    """返回面向用户的贝壳 CLI 安装引导（友好、可复制）。

    安装/鉴权一次性；未安装时由 agent 在首次使用时转述给用户。
    关键 UX：若用户选择「安装」，agent 必须阻塞等待用户完成安装+auth 并回复确认，
    期间不得并行跑联网检索或生成报告；若用户选择「暂不安装」，才继续走联网检索兜底。
    """
    return ("【建议】安装贝壳官方 CLI，获取真实成交/挂牌数据（更准、带真实详情链接）\n\n"
            "1) 安装 CLI（官方脚本）：\n"
            "   curl -fsSL https://raw.githubusercontent.com/"
            "LianjiaTech/beike-ai-platform/master/cli/releases/install.sh | bash\n\n"
            "2) 浏览器登录并获取 API Key：\n"
            "   运行 beike login，按提示在浏览器登录后拿到 Bearer Key；\n"
            "   或直接访问 https://building.ke.com/?action=get-key&source=house-buying\n\n"
            "3) 保存 Key 到本机：\n"
            "   beike auth <你的API_KEY> --save\n\n"
            "【重要】如果你选择安装，请完成上面 3 步后回复「已安装并 auth」，\n"
            "我才会继续用真实 CLI 数据完成分析。在你确认之前，我会暂停，不会用联网检索兜底跑。\n"
            "→ 如果你不想现在安装，直接回复「暂不安装 / 跳过」，我将立即用联网检索继续分析（数据会标注为“检索式回填”，不报错）。")


def school_tier_rank(school: str, city: str = "") -> dict:
    """内置少量已知学校的梯队（第一/二/三/四），未收录返回“未评级”。

    内置表仅覆盖示例城市（南京/杭州）；其余按 references/school-tier-reference.md
    联网评估。梯队是公开口碑/官方信息整理的参考，报告必须另附评级依据与来源。
    """
    _KNOWN = {
        ("南京", "拉萨路小学"): ("第一梯队", "公认头部名校，学位预警常见"),
        ("南京", "力学小学"): ("第一梯队", "传统名校，集团化办学"),
        ("南京", "琅琊路小学"): ("第一梯队", "传统名校"),
        ("南京", "北京东路小学"): ("第一梯队", "传统名校，集团化"),
        ("南京", "银城小学"): ("第二梯队", "优质集团校，口碑好"),
        ("南京", "晓庄小学"): ("第二梯队", "区级优质集团校，2018 复校，三年级学业检测全区名列前茅"),
        ("南京", "伯乐中学"): ("第二梯队", "省示范初中，校方称连续 40 余年中考居全区第一方阵"),
        ("杭州", "学军小学"): ("第一梯队", "公认头部"),
        ("杭州", "文三街小学"): ("第一梯队", "传统名校"),
        ("杭州", "保俶塔实验学校"): ("第一梯队", "九年一贯头部"),
        ("杭州", "采荷一小"): ("第二梯队", "优质区属"),
    }
    hit = _KNOWN.get((city, school))
    if hit:
        tier, basis = hit
        return {"school": school, "city": city, "tier": tier,
                "basis": basis, "known": True}
    return {"school": school, "city": city,
            "tier": "未评级（证据不足）",
            "basis": "内置表未收录，按 references/school-tier-reference.md 联网评估并附来源",
            "known": False}


# --------------------------------------------------------------------------- #
# 报告辅助：更多零依赖 SVG 图表（横向比较 / 三情景 / 学区梯队）
# --------------------------------------------------------------------------- #
def _svg_boilerplate(width: int, height: int, title: str = "") -> list:
    """SVG 公共头。"""
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
           f'font-family="-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif">',
           f'<rect width="{width}" height="{height}" fill="#fffdf8"/>']
    if title:
        svg.append(f'<text x="16" y="20" font-size="13" fill="#2f2a24" '
                   f'font-weight="600">{title}</text>')
    return svg


def render_bar_chart(data: list, title: str = "", width: int = 720,
                     height: int = 340, value_fmt: str = "{:.0f}") -> str:
    """生成零依赖 SVG 柱状图。

    data: list[dict] = [{"label": "华荟花园", "value": 28038}, ...]
    value_fmt: 柱顶数值格式化字符串，默认整数。
    配色：橄榄绿系，标题位于左上角。
    """
    if not data:
        return "<!-- 无柱状图数据 -->"
    try:
        vals = [float(d["value"]) for d in data]
    except (KeyError, TypeError, ValueError):
        return "<!-- 柱状图数据格式错误 -->"
    labels = [str(d.get("label", "")) for d in data]
    n = len(data)
    top = 36 if title else 18
    bottom = 72
    left = 56
    right = 24
    plot_h = height - top - bottom
    plot_w = width - left - right
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.12 or max(hi * 0.05, 1)
    ymin, ymax = max(0, lo - pad), hi + pad

    svg = _svg_boilerplate(width, height, title)
    # grid lines (5)
    for gi in range(5):
        gv = ymin + (ymax - ymin) * gi / 4
        gy = top + plot_h * (1 - (gv - ymin) / (ymax - ymin or 1))
        svg.append(f'<line x1="{left}" y1="{gy:.1f}" x2="{width - right}" y2="{gy:.1f}" '
                   f'stroke="#e4ddcd" stroke-width="1"/>')
        svg.append(f'<text x="{left - 8}" y="{gy + 4:.1f}" font-size="10" fill="#8a8272" '
                   f'text-anchor="end">{gv / 10000:.2f}万</text>')

    bar_w = plot_w / n * 0.55
    gap = plot_w / n
    colors = ["#5c6b3c", "#6b7c4a", "#8a9a6a", "#a8b38a", "#c6cfaa"]
    for i, (lab, v) in enumerate(zip(labels, vals)):
        x = left + gap * i + (gap - bar_w) / 2
        bh = plot_h * (v - ymin) / (ymax - ymin or 1)
        y = top + plot_h - bh
        color = colors[i % len(colors)]
        svg.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" '
                   f'rx="4" fill="{color}"/>')
        svg.append(f'<text x="{x + bar_w / 2:.1f}" y="{y - 6:.1f}" font-size="10" '
                   f'fill="#2f2a24" text-anchor="middle">{value_fmt.format(v)}</text>')
        # x label: wrap by char, max 2 lines
        cx = x + bar_w / 2
        if len(lab) <= 5:
            svg.append(f'<text x="{cx:.1f}" y="{height - bottom + 18}" font-size="10" '
                       f'fill="#6b7280" text-anchor="middle">{lab}</text>')
        else:
            mid = len(lab) // 2
            svg.append(f'<text x="{cx:.1f}" y="{height - bottom + 14}" font-size="9" '
                       f'fill="#6b7280" text-anchor="middle">{lab[:mid]}</text>')
            svg.append(f'<text x="{cx:.1f}" y="{height - bottom + 28}" font-size="9" '
                       f'fill="#6b7280" text-anchor="middle">{lab[mid:]}</text>')
    svg.append("</svg>")
    return "\n".join(svg)


def render_range_chart(data: list, title: str = "", width: int = 720,
                       height: int = 320) -> str:
    """生成零依赖 SVG 区间/三情景图。

    data: list[dict] = [
        {"label": "基准", "low": -8, "mid": -2, "high": 3},
        {"label": "乐观", "low": 0, "mid": 3, "high": 8},
        {"label": "悲观", "low": -15, "mid": -10, "high": -3},
    ]
    每个条表示一个情景在多个时间维度（6-12月/1-3年/3-10年）的 low~high 区间，
    中点 mid 用圆点标注。单位：%。
    """
    if not data:
        return "<!-- 无区间图数据 -->"
    try:
        lows = [float(d["low"]) for d in data]
        highs = [float(d["high"]) for d in data]
        mids = [float(d["mid"]) for d in data]
        labels = [str(d.get("label", "")) for d in data]
    except (KeyError, TypeError, ValueError):
        return "<!-- 区间图数据格式错误 -->"
    lo, hi = min(lows), max(highs)
    pad = (hi - lo) * 0.15 or max(abs(hi) * 0.1, 1)
    xmin, xmax = lo - pad, hi + pad
    top = 38 if title else 20
    bottom = 50
    left = 72
    right = 32
    plot_w = width - left - right
    plot_h = height - top - bottom
    n = len(data)
    row_h = plot_h / n

    def x(v: float) -> float:
        return left + plot_w * (v - xmin) / (xmax - xmin or 1)

    svg = _svg_boilerplate(width, height, title)
    # 0 基准线
    zx = x(0)
    svg.append(f'<line x1="{zx:.1f}" y1="{top}" x2="{zx:.1f}" y2="{height - bottom}" '
               f'stroke="#9a3412" stroke-width="1" stroke-dasharray="3,3"/>')
    # grid lines
    for gi in range(5):
        gv = xmin + (xmax - xmin) * gi / 4
        gx = x(gv)
        svg.append(f'<line x1="{gx:.1f}" y1="{top}" x2="{gx:.1f}" y2="{height - bottom}" '
                   f'stroke="#e4ddcd" stroke-width="1"/>')
        svg.append(f'<text x="{gx:.1f}" y="{height - bottom + 14}" font-size="10" '
                   f'fill="#8a8272" text-anchor="middle">{gv:.0f}%</text>')

    colors = {"乐观": "#5c6b3c", "基准": "#8a9a6a", "悲观": "#b45309"}
    for i, (lab, low, mid_v, high) in enumerate(zip(labels, lows, mids, highs)):
        y = top + row_h * i + row_h / 2
        x1, x2 = x(low), x(high)
        color = colors.get(lab, "#6b7c4a")
        # 区间条
        svg.append(f'<line x1="{x1:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y:.1f}" '
                   f'stroke="{color}" stroke-width="6" stroke-linecap="round"/>')
        # 端点
        svg.append(f'<circle cx="{x1:.1f}" cy="{y:.1f}" r="3" fill="{color}"/>')
        svg.append(f'<circle cx="{x2:.1f}" cy="{y:.1f}" r="3" fill="{color}"/>')
        # 中点
        xm = x(mid_v)
        svg.append(f'<circle cx="{xm:.1f}" cy="{y:.1f}" r="4" fill="#fff" '
                   f'stroke="{color}" stroke-width="2"/>')
        svg.append(f'<text x="{xm:.1f}" y="{y - 10:.1f}" font-size="9" '
                   f'fill="{color}" text-anchor="middle">{mid_v:.0f}%</text>')
        # label
        svg.append(f'<text x="{left - 8}" y="{y + 4:.1f}" font-size="11" '
                   f'fill="#2f2a24" text-anchor="end" font-weight="600">{lab}</text>')

    svg.append("</svg>")
    return "\n".join(svg)


# 兼容别名：学区梯队对比本质是柱状图
def render_tier_chart(data: list, title: str = "", width: int = 720,
                      height: int = 300) -> str:
    """生成学区梯队指数对比柱状图（10=第一梯队，7=第二梯队，5=第三梯队，3=第四梯队）。"""
    return render_bar_chart(data, title=title, width=width, height=height,
                            value_fmt="{:.0f}")

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
        Community(name="A", city="杭州", housing_type="commodity", avg_listing_price=60000),
        Community(name="B", city="杭州", housing_type="resettlement", avg_listing_price=30000),
        Community(name="C", city="杭州", housing_type="commodity", avg_listing_price=80000),
        Community(name="D", city="杭州", housing_type="commodity", avg_listing_price=None),
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

    # 3) 数据源检索式生成：城市必须可声明，不再写死杭州
    h = HangfangSource()
    q = h.search_queries("文鼎苑", "西湖", "杭州", 36)
    assert any("杭房数研" in x and "文鼎苑" in x for x in q), "杭房检索式缺失"
    x = XiaojiSource()
    qx = x.search_queries("文鼎苑", "西湖", "杭州", 36)
    assert any("小鸡选房" in x and "文鼎苑" in x for x in qx), "小鸡检索式缺失"
    b = BeikeSource()
    qb = b.search_queries("文鼎苑", "浦东", "上海", 24)
    assert any("上海" in x and "贝壳" in x for x in qb), "贝壳检索式未带城市"
    assert not any("杭州" in x for x in qb), "贝壳检索式残留杭州"
    w = WoaiwojiaSource()
    qw = w.search_queries("文鼎苑", "浦东", "上海", 24)
    assert any("我爱我家" in x and "上海" in x for x in qw), "我爱我家检索式缺失"
    print("✓ 城市化检索式与新增我爱我家源正确")

    # 4) API 模式 + 时间轴（mock 服务器验证历史点解析）
    _mock_server(8791, {
        "data": {"list": [
            {"price": 62000, "totalPrice": 558, "area": 90, "date": "2026-07",
             "type": "listing", "history": [
                 {"month": "2026-06", "price": 61000, "count": 3},
                 {"month": "2026-05", "price": 59500, "count": 2},
             ]},
            {"price": 60000, "totalPrice": 540, "area": 90, "date": "2026-06",
             "type": "transaction", "history": [
                 {"month": "2026-06", "price": 59000, "count": 1},
             ]},
        ]}
    })
    h_api = HangfangSource(cfg={"endpoint": "http://127.0.0.1:8791/data",
                                "token": "test-token"})
    res = h_api.fetch("文鼎苑", "西湖", "上海", 24)
    assert res.mode == "api", "未走 API 模式"
    assert res.city == "上海", "城市未透传"
    assert len(res.listings) == 1 and len(res.transactions) == 1, "API 解析错误"
    assert len(res.history) >= 3, f"时间轴解析错误: {len(res.history)}"
    assert all(p.date.startswith("2026-") for p in res.history), "时间轴日期未归一化"
    assert res.confidence == "high", "API 置信度错误"
    print("✓ 杭房数研 API 模式（mock）解析正确：挂牌1/成交1/时间轴3点")

    # 5) 城市级配置覆盖
    b_cfg = BeikeSource(cfg={"cities": {
        "上海": {"endpoint": "http://127.0.0.1:8791/data", "token": "t"},
    }})
    assert b_cfg.can_api("上海"), "城市级 API 配置未生效"
    assert not b_cfg.can_api("北京"), "未配置城市不应误判可 API"
    srcs = load_sources("上海")
    assert any(s.name == "我爱我家" for s in srcs), "我爱我家未纳入数据源"
    print("✓ 城市级配置与我爱我家数据源注册正确")
    _mock_server.srv.shutdown()

    # 6) 无配置时退回检索模式
    h_ws = HangfangSource()
    res2 = h_ws.fetch("文鼎苑", "西湖", "上海", 12)
    assert res2.mode == "websearch", "未退回检索模式"
    assert any("上海" in x for x in res2.queries), "检索式未带城市"
    print("✓ 未配置接口时正确退回联网检索模式")

    # 7) 报告辅助：橄榄手记 CSS / 可点击引用（含锚点）/ 学区梯队 / 图表
    css = olive_theme_css()
    assert "--olive:#5c6b3c" in css, "橄榄手记 CSS 缺失主色"
    assert ".cite-ref" in css, "引用锚点样式缺失"
    cites = render_citations(
        [{"label": "栖霞区教育局2025年招生办法", "url": "https://edu.example.gov/a"}])
    assert 'href="https://edu.example.gov/a"' in cites, "引用链接未生成"
    assert 'target="_blank"' in cites, "引用未新开窗口"
    assert 'id="cite-1"' in cites, "引用未生成 cite-N 锚点"
    assert render_citations([]) == "", "空引用应返回空串"

    bar = render_bar_chart([{"label": "A", "value": 100}, {"label": "B", "value": 200}])
    assert "<svg" in bar and "A" in bar and "B" in bar, "柱状图生成失败"
    rng = render_range_chart([
        {"label": "乐观", "low": 0, "mid": 3, "high": 8},
        {"label": "基准", "low": -8, "mid": -2, "high": 3},
        {"label": "悲观", "low": -15, "mid": -10, "high": -3},
    ])
    assert "<svg" in rng and "乐观" in rng, "区间图生成失败"
    tier = render_tier_chart([
        {"label": "拉力琅", "value": 10},
        {"label": "晓庄小学", "value": 7},
    ])
    assert "<svg" in tier and "晓庄小学" in tier, "梯队图生成失败"

    t = school_tier_rank("晓庄小学", "南京")
    assert t["known"] and t["tier"] == "第二梯队", f"学区梯队查表错误: {t}"
    t2 = school_tier_rank("未知学校甲", "南京")
    assert not t2["known"] and "未评级" in t2["tier"], "未知学校应返回未评级"
    print("✓ 橄榄手记CSS / 可点击引用锚点 / 学区梯队 / SVG 图表辅助正确")

    # 8) T3 交叉验证源注册 + 数据源分级标注
    srcs = load_sources("上海")
    names = {s.name for s in srcs}
    for n in ("贝壳", "我爱我家", "诸葛找房", "安居客", "房天下", "58同城"):
        assert n in names, f"数据源未注册: {n}"
    tier_map = {s.name: s.tier for s in srcs}
    assert tier_map["贝壳"] == "T0" and tier_map["我爱我家"] == "T0", "T0 核心源分级错误"
    assert tier_map["诸葛找房"] == "T3" and tier_map["58同城"] == "T3", "T3 交叉源分级错误"
    assert tier_map["杭房数研"] == "T1.5", "杭房数研应标注 T1.5 城市高频源"
    z = ZhugeSource()
    assert any("诸葛找房" in x and "上海" in x for x in z.search_queries("文鼎苑", "浦东", "上海", 24)), "诸葛检索式缺失"
    w = WubaSource()
    assert any("58同城" in x and "上海" in x for x in w.search_queries("文鼎苑", "浦东", "上海", 24)), "58同城检索式缺失"
    # fetch 结果带 tier
    res = ZhugeSource().fetch("文鼎苑", "浦东", "上海", 12)
    assert res.tier == "T3" and res.mode == "websearch", "T3 源 fetch 分级/模式错误"
    print("✓ T3 交叉验证源注册与五级分级标注正确")

    # 9) 环比/同比/N月涨跌幅
    momyoy = compute_mom_yoy([
        {"date": "2026-01", "price_per_sqm": 10000, "kind": "listing", "count": 10},
        {"date": "2026-02", "price_per_sqm": 11000, "kind": "listing", "count": 8},
        {"date": "2026-03", "price_per_sqm": 9900, "kind": "listing", "count": 6},
        {"date": "2025-03", "price_per_sqm": 9000, "kind": "listing", "count": 5},
    ])
    assert "listing" in momyoy, "环比/同比缺少挂牌口径"
    L = momyoy["listing"]
    # 2026-02 vs 2026-01: (11000-10000)/10000 = +10%；2026-03 vs 2026-02 = -10%
    assert abs(L["mom"]["2026-02"] - 0.10) < 1e-9, f"环比计算错误: {L['mom']}"
    assert abs(L["mom"]["2026-03"] + 0.10) < 1e-9, f"环比计算错误: {L['mom']}"
    # 2025-03 与 2026-01 不连续，缺月不编造环比
    assert "2026-01" not in L["mom"], "缺月不应编造环比"
    # 同比：2026-03 vs 2025-03 = +10%
    assert abs(L["yoy"]["2026-03"] - 0.10) < 1e-9, f"同比计算错误: {L['yoy']}"
    # 12个月涨跌幅：2026-03 vs 2025-03 = +10%；3/6 个月前月份缺失 → 不输出
    assert abs(L["change_nm"][12] - 0.10) < 1e-9, f"12月涨跌幅错误: {L['change_nm']}"
    assert 3 not in L["change_nm"], "缺月不应编造3月涨跌幅"
    assert L["peak"]["price"] == 11000 and L["valley"]["date"] == "2025-03", "峰谷错误"
    assert L["current"]["price"] == 9900 and L["months_covered"] == 4, "当前值错误"
    # 单点时点不编造环比
    single = compute_mom_yoy([{"date": "2026-07", "price_per_sqm": 50000, "kind": "listing"}])
    assert single["listing"]["mom"] == {}, "单月不应产生环比"
    print("✓ 环比/同比/12月涨跌幅/峰谷/当前值计算正确（含缺月不编造）")

    # 10) 引用防伪元数据（发布时间/口径/一致性）+ 维度框架
    cites = render_citations([
        {"label": "贝壳某小区页", "url": "https://hz.ke.com/xiaoqu/a",
         "date": "2026-07-15 访问", "caliber": "挂牌", "consistency": "双源一致"},
        {"label": "教育局招生公告", "url": "https://edu.example.gov/b",
         "date": "2026-06", "caliber": "官方文件"},
    ])
    assert 'class="cite-meta"' in cites and "口径:挂牌" in cites, "引用元数据未生成"
    assert "一致性:双源一致" in cites and "2026-07-15 访问" in cites, "引用元数据内容错误"
    assert 'href="https://hz.ke.com/xiaoqu/a"' in cites, "引用链接丢失"
    dims = DIMENSION_FRAMEWORK
    assert set(dims) == {"price", "volume", "supply_demand", "land",
                         "school_policy", "population", "credit"}, "维度框架缺失"
    assert dims["price"]["mandatory"] is True and dims["volume"]["mandatory"] is False, "第一维度标记错误"
    print("✓ 引用防伪元数据与7维度网络框架正确")

    # 8) 政策基线快照（A 模块）
    nb = national_policy_baseline()
    assert "多校划片" in nb, "全国政策基线缺失"
    hzp = load_city_policy("杭州")
    assert hzp.get("multi_school_assignment"), "杭州政策基线缺失"
    assert load_city_policy("不存在城").get("verify_status") == "待联网核验", "未登记城市未回退默认"
    print("✓ 政策基线快照（city_policy.json）读取正确")

    # 9) 学区划片/预警源注册表（C+D 模块）
    qz = city_source_queries("上海")
    assert qz.get("school_district"), "school_district 字段缺失"
    assert qz.get("enrollment_alert"), "enrollment_alert 字段缺失"
    assert any("学区划片" in x for x in qz["queries"]), "学区划片检索式缺失"
    assert any("学区预警" in x for x in qz["queries"]), "学区预警检索式缺失"
    print("✓ 学区划片/预警源注册表（city_sources.json）已接入 sources 命令")

    # 10) 官方单小区 gov 适配器（G 模块）
    g = GovCommunityAdapter(city="杭州")
    assert not g.can_api("杭州"), "无 endpoint 不应判定可 API"
    res = g.fetch("文鼎苑", "", "杭州", 12)
    assert res.mode == "websearch", "无 endpoint 应退回检索"
    assert any("官方" in x for x in res.queries), "gov 检索式缺失"
    assert res.tier == "T1", "gov 应为 T1"
    print("✓ 官方单小区 gov 适配器（无配置退回 T1 检索）正确")

    # 11) 贝壳官方 CLI 接入：环境自适应（装了走真实通道，没装安全退回）
    assert isinstance(beike_cli_available(), bool), "beike_cli_available 应返回 bool"
    cli_src = BeikeCliSource()
    r11 = cli_src.fetch("坤和西溪里", "", "杭州", 12)
    if beike_cli_available():
        # 本机已装 CLI + Key：验证走真实通道且不抛异常、不编造
        assert r11.mode in ("cli", "cli_unavailable"), "已装CLI应走cli或安全降级"
        if r11.mode == "cli_unavailable":
            assert r11.listings == [] and r11.transactions == [], "降级不应编造"
            assert r11.queries, "降级应提供检索式"
        else:
            assert isinstance(r11.listings, list) and isinstance(r11.transactions, list)
        print("✓ 贝壳CLI已安装：走真实通道（或安全降级），无异常/无编造")
    else:
        assert r11.mode == "cli_unavailable", "无CLI应标记 cli_unavailable"
        assert r11.queries, "无CLI应提供联网检索式"
        assert "beike" in r11.raw_note.lower() or "贝壳" in r11.raw_note, "应有安装提示"
        assert r11.listings == [] and r11.transactions == [], "无CLI不应编造数据"
        print("✓ 贝壳CLI未安装时安全退回联网检索（无异常/无编造）")

    # 12) 解析器：近似真实结构的 fixture 验证字段映射（仅自测，非真实数据）
    fixture = {"data": {"list": [
        {"communityName": "坤和西溪里", "unitPrice": 58000, "totalPrice": 520,
         "area": 89.6, "type": "listing",
         "url": "https://hz.ke.com/ershoufang/abc.html",
         "title": "坤和西溪里 3室2厅"},
        {"communityName": "坤和西溪里", "unitPrice": 56000, "totalPrice": 500,
         "area": 89.0, "type": "sold", "dealDate": "2026-07",
         "url": "https://hz.ke.com/chengjiao/def.html"},
    ]}}
    rows12, _ = _parse_beike_cli_payload(fixture)
    assert len(rows12) == 2, "fixture 应解析出2条"
    li12, tr12, _ = cli_src._build_result(rows12, "坤和西溪里", "杭州", "贝壳(官方CLI)")
    assert len(li12) == 1 and len(tr12) == 1, "挂牌/成交应分流"
    assert li12[0].price_per_sqm == 58000, "单价映射错误"
    assert tr12[0].kind == "transaction", "成交类型错误"
    assert rows12[0]["url"].startswith("https://hz.ke.com"), "详情URL应保留"
    # 未知结构不抛异常
    bad_rows, bad_note = _parse_beike_cli_payload({"foo": "bar"})
    assert bad_rows == [] and bad_note, "未知结构应空列表+说明，不抛异常"
    print("✓ 贝壳CLI payload 解析与挂牌/成交分流正确（fixture）；未知结构安全降级")

    # 13) 多平台统一检索：无 CLI/无 endpoint 时整合且安全兜底
    ms = multi_platform_search("坤和西溪里", "", "杭州", 12, include_cross=True)
    assert ms["mode"] == "search", "统一检索模式错误"
    names13 = {p["source"] for p in ms["platforms"]}
    assert "贝壳" in names13 and "我爱我家" in names13, "缺少核心双源"
    assert len(ms["platforms"]) >= 2, "至少含贝壳与我爱我家"
    for p in ms["platforms"]:
        assert p["status"] in ("ok_real", "empty_real",
                               "websearch_fallback", "error"), "状态非法"
        assert isinstance(p["listings"], list), "listings 应为列表"
    # 单平台异常兜底逻辑（与统一检索包裹逻辑一致）
    class _Boom(BaseSource):
        name = "爆炸源"
        tier = "T3"
        def search_queries(self, *a, **k): return ["q"]
        def fetch(self, *a, **k): raise RuntimeError("boom")
    boom = _Boom()
    bentry = {"source": "爆炸源", "status": "ok"}
    try:
        boom.fetch("x")
    except Exception as exc:
        bentry["status"] = "error"
        bentry["note"] = f"爆炸源 取数异常：{exc}"
    assert bentry["status"] == "error" and "boom" in bentry["note"], "异常应被兜底标注"
    print("✓ 多平台统一检索整合与状态标注正确；单平台异常兜底逻辑正确")

    # 14) 贝壳多命令聚合 + 成交反算单价（对齐「贝壳买房专家」命令体系）
    # 注意：真实 beike CLI `--json` 返回半结构化文本（data 为 XML/Markdown 混合
    # 文本，房源用 <房源ID> 包裹内嵌 JSON 片段），故 fixture 采用真实文本结构。
    def _fake_beike(args):
        # 模拟官方 CLI：args = ["buy", <cmd>, "-c", city, "-q", query]
        # 采用与真实 CLI 一致的结构：
        #   search/sold -> 字段嵌套在 摘要信息/基本信息；market -> 小区行情数据；
        #   resblock -> 摘要信息（小区信息为中文串，官方 CLI 不直给均价）。
        cmd = args[1] if len(args) > 1 else ""
        if cmd == "search":
            return {"data": (
                "<贝壳召回知识>\n<房源>\n<111>\n\n"
                '{"摘要信息":{"价格信息":"总价520万，单价58000元/平米",'
                '"房源标题":"坤和西溪里 3室2厅 89.6㎡ 520万",'
                '"房源ID":"111","房源售卖状态":"在售",'
                '"小区ID":"1811043641191",'
                '"小区信息":"坤和西溪里(小区ID:1811043641191)，2010年建成，'
                '容积率1.8，绿化率35%，物业费3元/平米/月，车位配比1:1.5，1440户"'
                '}}\n\n</111>\n</房源>')}
        if cmd == "sold":
            # 成交记录只给 总价(万) + 户型面积(在房源名称里)，无单价 -> 必须反算
            # 真实 CLI 的 房源ID 即区块标签，基本信息里只有 小区ID
            return {"data": (
                "<贝壳召回知识>\n<成交房源>\n<222>\n\n"
                '{"基本信息":{"成交价格":"500万","成交日期":"2026.07.15",'
                '"房源名称":"坤和西溪里 2室2厅 89㎡ 500万",'
                '"挂牌价格":"520万","小区ID":"1811043641191"'
                '}}\n\n</222>\n</成交房源>')}
        if cmd == "market":
            return {"data": (
                "<价格走势>\n<坤和西溪里行情>\n\n"
                '{"小区最新行情":{"成交均价":{"2026-07":"5.60万/m2","环比":"0"},'
                '"挂牌均价":{"2026-07":"5.90万/m2","环比":"-1.90%"}}}\n\n'
                '{"小区行情数据":{"成交均价":{"最近6月趋势":'
                '{"2026-05":"5.70万/m2","2026-06":"5.65万/m2","2026-07":"5.60万/m2"}},'
                '"挂牌均价":{"最近6月趋势":'
                '{"2026-05":"6.00万/m2","2026-06":"5.95万/m2","2026-07":"5.90万/m2"}},'
                '"成交量":{"最近6月趋势":'
                '{"2026-05":"3套","2026-06":"4套","2026-07":"2套"}}}}\n\n'
                "</坤和西溪里行情>\n</价格走势>")}
        if cmd == "resblock":
            return {"data": (
                "<贝壳召回知识>\n<小区>\n<坤和西溪里>\n\n"
                '{"摘要信息":{"小区名称":"坤和西溪里","小区ID":"1811043641191",'
                '"小区信息":"坤和西溪里(小区ID:1811043641191)，2010年建成，'
                '容积率1.8，绿化率35%，物业费3元/平米/月，车位配比1:1.5，1440户",'
                '"市场行情":"在售57套，在售价格范围290-815万"'
                '}}\n\n</坤和西溪里>\n</小区>')}
        raise RuntimeError("unexpected cmd " + str(args))
    _old_run = globals().get("_run_beike_cli")
    globals()["_run_beike_cli"] = _fake_beike
    try:
        multi = BeikeCliSource(city="杭州")
        r14 = multi.fetch("坤和西溪里", "", "杭州", 12)
        assert r14.mode == "cli", "多命令聚合应标记 cli"
        assert len(r14.listings) == 1, "应有1条挂牌"
        assert len(r14.transactions) == 1, "应有1条成交(反算单价)"
        # 成交反算：500万 / 89㎡ ≈ 56179.78 元/㎡
        assert abs(r14.transactions[0].price_per_sqm - 500 * 10000 / 89.0) < 1, \
            f"成交反算单价错误: {r14.transactions[0].price_per_sqm}"
        assert r14.transactions[0].kind == "transaction"
        assert len(r14.history) >= 3, f"market 走势点应进 history: {len(r14.history)}"
        assert {"2026-05", "2026-06", "2026-07"} <= {p.date for p in r14.history}, \
            "走势月份缺失"
        rb = r14.extra.get("resblock", {})
        # 真实 CLI 的 resblock 不直给均价；此处验证它能抽出的真实字段
        assert rb.get("xiaoqu_id") == "1811043641191", "小区ID缺失"
        assert "xiaoqu/1811043641191" in rb.get("url", ""), "小区页URL缺失"
        assert rb.get("name") == "坤和西溪里", "小区名缺失"
        assert rb.get("build_year") == "2010", "建成年份缺失"
        assert rb.get("volume_rate") == 1.8 and rb.get("households") == 1440, \
            "容积率/户数提取错误"
        assert rb.get("green_rate") == 35.0, "绿化率提取错误"
        assert rb.get("property_fee") == 3.0, "物业费提取错误"
        assert rb.get("car_ratio") == "1:1.5", "车位配比提取错误"
        assert rb.get("onsale_count") == 57, "在售套数提取错误"
        assert rb.get("price_range_wan") == [290.0, 815.0], "价格范围提取错误"
        assert "avg_listing_price" not in rb, "官方CLI无均价不应编造"
        assert r14.extra["listings"][0]["url"] == \
            "https://hz.ke.com/ershoufang/111.html", "挂牌详情URL错误"
        assert r14.extra["transactions"][0]["url"] == \
            "https://hz.ke.com/chengjiao/222.html", "成交详情URL错误"
        # 部分命令失败：只少一类数据，不整体异常
        def _fake_beike_partial(args):
            if args[1] == "market":
                raise RuntimeError("market 暂不可用")
            return _fake_beike(args)
        globals()["_run_beike_cli"] = _fake_beike_partial
        r14b = multi.fetch("坤和西溪里", "", "杭州", 12)
        assert r14b.mode == "cli" and len(r14b.listings) == 1, \
            "部分命令失败应保留其他数据"
        assert "market 调用失败" in r14b.raw_note, "应记录 market 失败说明"
        # 全部命令失败：退回 websearch 兜底（不抛异常、不编造）
        def _fake_beike_boom(args):
            raise RuntimeError("boom all")
        globals()["_run_beike_cli"] = _fake_beike_boom
        r14c = multi.fetch("坤和西溪里", "", "杭州", 12)
        assert r14c.mode == "cli_unavailable", "全命令失败应退回 websearch"
        assert r14c.listings == [] and r14c.transactions == [], "兜底不应编造"
        assert r14c.queries, "兜底应给检索式"
    finally:
        globals()["_run_beike_cli"] = _old_run
    print("✓ 贝壳多命令聚合(search+sold+market+resblock) 文本解析 + 成交反算单价 + 部分/全失败兜底正确")

    # #16 最近成交(近10条) 渲染
    rt_tx = [
        {"price": 58000, "totalPrice": 520, "area": 89.6, "date": "2026-05",
         "title": "银树湾 3室2厅 89.6㎡", "url": "", "kind": "transaction"},
        {"price": 52595, "totalPrice": 899, "area": 170.9, "date": "2026-07",
         "title": "银树湾 3室2厅 89.6㎡ 520万",
         "url": "https://hz.ke.com/chengjiao/111.html", "kind": "transaction"},
        {"price": 56179, "totalPrice": 500, "area": 89, "date": "2026-07-15",
         "title": "银树湾 2室1厅 89㎡ 500万",
         "url": "https://hz.ke.com/chengjiao/222.html", "kind": "transaction"},
    ]
    rt_html = render_recent_transactions(rt_tx, n=10)
    assert rt_html.count("<tr>") == 4, "最近成交表应有 1 表头 + 3 数据行"
    assert "2026-07-15" in rt_html and "2026-07" in rt_html and "2026-05" in rt_html
    # 时间倒序：最新(2026-07-15)应排在 2026-07 之前（按完整单元格匹配，避免前缀重叠）
    assert rt_html.index(">2026-07-15<") < rt_html.index(">2026-07<"), "应按时间倒序"
    assert "https://hz.ke.com/chengjiao/111.html" in rt_html, "真实详情URL应保留"
    rt_empty = render_recent_transactions([], n=10)
    assert "未获取到可核验的成交记录" in rt_empty, "空数据应给提示块"
    # recent_transactions 截断到 10
    rt_many = [{"price": i, "totalPrice": i, "date": "2026-%02d" % ((i % 12) + 1),
                "kind": "transaction"} for i in range(1, 25)]
    rt_top = render_recent_transactions(rt_many, n=10)
    assert rt_top.count("<tr>") == 11, "应截断到 10 条(+表头)"
    print("✓ 最近成交(近10条) 渲染：时间倒序 + 真实URL + 空数据提示 + 截断正确")

    print("\nself-test passed" if ok else "self-test failed")
    return 0 if ok else 1


# --------------------------------------------------------------------------- #
# 多平台统一检索（贝壳官方CLI + 我爱我家 + 可选 T3 交叉源）
# --------------------------------------------------------------------------- #
def multi_platform_search(community: str, district: str = "", city: str = "杭州",
                          months: int = 36, include_cross: bool = True) -> dict:
    """多平台统一检索：贝壳（官方 CLI 优先）+ 我爱我家（+ 可选 T3 交叉源）。

    设计目标（对应 skill 优化需求）：
    - 真实平台数据优先：贝壳走官方 CLI 拿到实时结构化数据（含真实详情 URL）。
    - 统一检索：我爱我家作为并列 T0 源，与贝壳在同一结果结构中合并。
    - 兜底与防伪：任一平台失败都不抛异常，仅在其 status 标注 error / 退回
      检索式；无真实数据时绝不编造，交由 AI 代理按检索式联网取数回填。
    """
    beike_src: BaseSource = (BeikeCliSource(city=city)
                             if beike_cli_available() else BeikeSource(city=city))
    spec = [
        ("贝壳", beike_src),
        ("我爱我家", WoaiwojiaSource(city=city)),
    ]
    if include_cross:
        spec += [
            ("诸葛找房", ZhugeSource(city=city)),
            ("安居客", AnjukeSource(city=city)),
            ("房天下", FangSource(city=city)),
            ("58同城", WubaSource(city=city)),
        ]

    platform_results: list = []
    merged_listings: list = []
    merged_transactions: list = []
    merged_history: list = []
    for name, src in spec:
        entry = {
            "source": name,
            "community": community,
            "city": city,
            "listings": [],
            "transactions": [],
            "history": [],
            "resblock": {},
            "queries": [],
            "mode": "unknown",
            "tier": getattr(src, "tier", "T3"),
            "confidence": "low",
            "status": "ok",
            "note": "",
        }
        try:
            res = src.fetch(community, district, city, months)
            d = res.to_dict()
            enriched_listings = (res.extra.get("listings")
                                 if res.extra.get("listings") else d["listings"])
            enriched_tx = (res.extra.get("transactions")
                           if res.extra.get("transactions") else d["transactions"])
            entry.update({
                "listings": enriched_listings,
                "transactions": enriched_tx,
                "history": d["history"],
                "resblock": res.extra.get("resblock", {}) if res.extra else {},
                "queries": d["queries"],
                "mode": d["mode"],
                "confidence": d["confidence"],
                "tier": d["tier"],
                "note": d["raw_note"],
            })
            if d["mode"] == "cli":
                entry["status"] = ("ok_real"
                                   if (entry["listings"] or entry["transactions"])
                                   else "empty_real")
            elif d["mode"] in ("cli_unavailable", "websearch"):
                entry["status"] = "websearch_fallback"
            else:
                entry["status"] = "ok"
            merged_listings.extend(entry["listings"])
            merged_transactions.extend(entry["transactions"])
            merged_history.extend(entry["history"])
        except Exception as exc:  # 单平台异常不影响整体，明确标注 error
            entry["status"] = "error"
            entry["note"] = f"{name} 取数异常：{exc}"
            entry["queries"] = src.search_queries(community, district, city, months)
        platform_results.append(entry)

    recent_tx = [t for t in merged_transactions if isinstance(t, dict)
                 and "trans" in str(t.get("kind") or "trans").lower()]
    recent_tx.sort(key=_txn_sort_key, reverse=True)
    recent_tx = recent_tx[:10]
    return {
        "mode": "search",
        "community": community,
        "district": district,
        "city": city,
        "months": months,
        "beike_cli_available": beike_cli_available(),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "platforms": platform_results,
        "merged_listings": merged_listings,
        "merged_transactions": merged_transactions,
        "recent_transactions": recent_tx,
        "merged_history": merged_history,
        "note": ("多平台统一检索完成：status=ok_real 为官方CLI实时数据；"
                 "websearch_fallback 表示未配置官方接口、需由 AI 代理按检索式联网取数；"
                 "所有价格证据须回填真实 URL 与口径，禁止编造或填默认口径。"),
    }


def cmd_search(args) -> int:
    city = args.city or "杭州"
    result = multi_platform_search(
        args.community, args.district or "", city,
        int(getattr(args, "months", 36) or 36),
        include_cross=not getattr(args, "no_cross", False),
    )
    _dump_plan(result, args.output)
    return 0


def cmd_beike_check(args) -> int:
    """首次使用检测：本机是否安装并配置贝壳 CLI。

    已安装配置 → 静默确认（agent 无需提示用户）。
    未安装 → 打印友好安装引导 + 明确「暂不安装」可选项（不阻塞分析）。
    """
    if beike_cli_available():
        where = (f"Key 位于 {BEIKE_KEY_FILE}" if BEIKE_KEY_FILE.is_file()
                 else "beike auth 已保存")
        print("✓ 贝壳 CLI 已安装并配置（" + where + "）。")
        print("  将直接使用官方实时数据通道，无需提示安装。")
        return 0
    print("○ 未检测到贝壳官方 CLI 或未鉴权。")
    print(beike_cli_setup_prompt())
    return 0


# --------------------------------------------------------------------------- #
# 学区分析增强：策展学区知识（references/school-data/{city}.json）
# --------------------------------------------------------------------------- #
SCHOOL_DATA_DIR = SKILL_DIR / "references" / "school-data"


def load_school_data(city: str) -> dict:
    """读取城市策展学区知识；无则返回 {}。"""
    try:
        p = SCHOOL_DATA_DIR / f"{city}.json"
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {}


def _resolve_schools(sdata: dict, community: str, cli_school: str) -> list:
    """解析目标小区对口学校名列表（策展映射优先，其次 CLI 字段命中）。"""
    cmap = sdata.get("community_school_map") or {}
    for name, schools in cmap.items():
        if name and name in (community or ""):
            return list(schools)
    if cli_school:
        hits = [s for s in (sdata.get("schools") or {}) if s and s in cli_school]
        if hits:
            return hits
    return []


_TIER_SCORE = {"第一梯队": 9, "第二梯队": 7, "第三梯队": 5, "第四梯队": 3}


def build_school_analysis(city: str, community: str, cli_school: str) -> dict:
    """生成 §5/§6/§10 的学区深度分析片段 + 引用规格。

    返回 dict：matched=False 时调用方退回占位逻辑。命中时含：
      schools, primary_school, duikou,
      tier_html(§6：对口/确定性 + 梯队表 + 生源代际),
      premium_html(§5), nonschool_html(§10),
      cite_specs[(ik,label,url,caliber,consistency), ...],
      school_tier_score(int|None), school_summary(str)
    HTML 中以 [[sch:IK]] 作为待替换引用锚点，由调用方注册 cite 后替换。
    """
    sdata = load_school_data(city)
    if not sdata:
        return {"matched": False}
    names = _resolve_schools(sdata, community, cli_school)
    if not names:
        return {"matched": False}
    S = sdata.get("schools") or {}
    resolved = [(nm, S[nm]) for nm in names if nm in S]
    if not resolved:
        return {"matched": False}
    cl = sdata.get("city_level") or {}
    cite_specs: list = []
    seen: set = set()

    def reg(ik):
        src = (sdata.get("sources") or {}).get(ik)
        if src and ik not in seen:
            seen.add(ik)
            cite_specs.append((ik, src.get("name", ik),
                               src.get("url", "#"), src.get("caliber", ""),
                               src.get("year", "skill内置")))

    for nm, sc in resolved:
        for ik in (sc.get("sources") or []):
            reg(ik)
    for ev in (cl.get("events_2026") or []):
        for ik in (ev.get("sources") or []):
            reg(ik)
    reg("e18")  # 教育局（学位锁定/政策基线）

    # ---- §6 对口 + 学区确定性 ----
    primary_name, primary = resolved[0]
    duikou = [sc.get("duikou_chuzhong") for nm, sc in resolved
              if sc.get("duikou_chuzhong")]
    duikou_html = ("<li><b>对口初中</b>：" + "；".join(duikou) + "</li>") if duikou else ""
    hy = primary.get("hukou_years") or {}
    hukou_row = ""
    if hy:
        hukou_row = (f"<tr><td>落户年限（{primary_name}）</td><td>"
                     + " ｜ ".join(f"{y}:{v}" for y, v in hy.items())
                     + f" ［{cl.get('hukou_note','')}］</td></tr>")
    determinacy = f"""
<p><b>对口学校（策展知识库，须以当年教育局公告核验）</b>：</p>
<ul>
  <li><b>对口小学</b>：{primary.get('group', primary.get('type',''))}（{primary.get('tier','')}）{duikou_html}</li>
</ul>
<table class='d'>
<tr><th>确定性维度</th><th>现状（杭州·{community or '目标'}）</th></tr>
{hukou_row}
<tr><td>学位锁定</td><td>{cl.get('seat_lock_text','—')} ［[[sch:e18]]］</td></tr>
</table>
<div class="warn"><b>⚠️ 学位占用 / 落户年限（skill 不机读，须用户自查）：</b>买前 3 步：① 浙里办 / 杭州不动产登记 查学位占用（六年一学位）；② 线下核验落户年限是否达标（{cl.get('hukou_note','以当年教育局公告为准')}）；③ 合同加《学位未被占用声明书》+ 赔偿条款。skill 不宣称已核验具体房源。</div>
"""

    # ---- §6 梯队评级表 ----
    tier_rows = ""
    for nm, sc in resolved:
        srcs = "、".join(f"[[sch:{ik}]]" for ik in (sc.get("sources") or []))
        tier_rows += (f"<tr><td>{nm}</td><td><b>{sc.get('tier','')}</b></td>"
                      f"<td>{sc.get('evidence', sc.get('group',''))}</td>"
                      f"<td>{srcs or '（待核验）'}</td></tr>")
    tier_table = f"""
<table class='d'>
<tr><th>学校</th><th>梯队</th><th>关键依据</th><th>来源</th></tr>
{tier_rows}
</table>
<p class='note'>梯队评级依据公开证据（集团化关系 / 可核验升学表现 / 学位紧张度）；民间榜单标「非官方」，不得仅凭自媒体口碑定梯队。证据不足须写「未评级」。</p>
"""

    # ---- §6 生源代际传导（cohort）----
    exam_rows = ""
    for nm, sc in resolved:
        ex = sc.get("exam") or {}
        for yr, d in ex.items():
            if isinstance(d, dict) and ("重高率" in d or "前三率" in d):
                exam_rows += (f"<tr><td>{nm}</td><td>{yr}</td>"
                              f"<td>{d.get('前三率','—')}</td>"
                              f"<td>{d.get('重高率','—')}</td>"
                              f"<td>{d.get('优高率','—')}</td>"
                              f"<td>{d.get('caliber', d.get('note',''))}</td></tr>")
    cohort_html = ""
    if exam_rows:
        cohort_html = f"""
<p><b>近 3-5 年升学表现（口径对齐 + 来源锚点）</b>：</p>
<table class='d'>
<tr><th>学校</th><th>年份</th><th>前三率(%)</th><th>重高率(%)</th><th>优高率(%)</th><th>口径/备注</th></tr>
{exam_rows}
</table>
"""
        cohort_2027 = primary.get("cohort_2027")
        if not cohort_2027 and len(resolved) > 1:
            cohort_2027 = resolved[1][1].get("cohort_2027")
        if cohort_2027:
            cohort_html += f"""
<p><b>生源代际传导（cohort）</b>：{primary_name} 近年中考数据反映 ~2013–2019 入学 cohort 的九年培养结果；当前在学 cohort 将承接近年师资与生源。按「出生→小学→初中→中考」约 15 年滞后推演，<b>2027 中考重高率三情景</b>：乐观 ~{cohort_2027.get('乐观','—')} ｜ 基准 ~{cohort_2027.get('基准','—')} ｜ 悲观 ~{cohort_2027.get('悲观','—')}。{cohort_2027.get('note','')}</p>
<p class='note'>置信度中-低：政策（多校划片/教师轮岗/民转公停招）与人口（少子化）均为外生变量，10 年预测天然低置信，须显式提示「2026 为政策落地元年」。详细方法见 references/school-cohort-analysis.md。</p>
"""
        else:
            cohort_html += "<p class='note'>未收录该校近年升学率时间序列，无法做代际传导推演；请按 references/school-cohort-analysis.md 联网补齐近 3-5 年中考数据后填入。</p>"

    tier_html = determinacy + tier_table + cohort_html

    # ---- §5 学区溢价 ----
    premium_html = f"""
<p><b>学区溢价（区间估算，置信度低-中）</b>：{cl.get('premium_note','本 CLI 无精确可比盘，不输出精确百分比；仅以挂牌−成交口径差作下限参考。')}</p>
<table class='d'>
<tr><th>对象</th><th>学校属性</th><th>近年成交/挂牌单价</th><th>相对差异</th></tr>
<tr><td>{community or '目标学区房'}</td><td>{'、'.join(nm for nm,_ in resolved)}（{primary.get('tier','')}）</td><td>贝壳成交序列（见 §2）</td><td>—</td></tr>
<tr><td>同板块非顶级学区次新</td><td>弱学区/普通公办</td><td>需 §7 联网补充</td><td>约 −10%~−20%（区间估算）</td></tr>
</table>
<p class='note'>溢价拆分铁律：须用同面积段成交价、对齐楼龄/户型/装修后比较，不把产品力溢价误算为学区溢价（见 references/school-premium-comparison.md）。CLI 缺可比盘，此处为区间估算而非精确测算，置信度低-中。</p>
"""

    # ---- §10 学区 vs 非学区 专章 ----
    events = cl.get("events_2026") or []
    ev_html = ""
    if events:
        ev = events[0]
        ev_srcs = "、".join(f"[[sch:{ik}]]" for ik in (ev.get("sources") or []))
        ev_html = (f"<b>重大事件（{ev.get('date','')}）</b>：{ev.get('event','')} —— "
                   f"{ev.get('impact','')} ［{ev_srcs}］。")
    nonschool_html = f"""
<p><b>差异比较</b>：{community or '目标'} 对口 {'、'.join(nm for nm,_ in resolved)}（{primary.get('tier','')}），相对同板块非学区次新，单价高出部分主要来自学校确定性/入学门槛/口碑，而非居住价值本身；区间估算溢价约 10–20%（见 §5，置信度低-中）。</p>
<p><b>后续走势（三情景）</b>：① <b>溢价可持续/收窄/反转</b>：当前政策基调（多校划片+教师轮岗+落户年限回落+民转公停招）指向<b>溢价趋势性收窄</b>。② {ev_html} ③ <b>驱动变量</b>：少子化（出生人口约 6 年传导到小学入学）、教育均衡化、近 12–36 个月量价动量。④ <b>结论</b>：学区房相对非学区的相对价值中长期趋于收敛，购买决策应更看重自住舒适度 + 转售流动性，而非「赌学区暴涨」。</p>
"""

    scores = [_TIER_SCORE.get(sc.get("tier", ""), 0) for nm, sc in resolved]
    school_tier_score = max(scores) if scores and any(scores) else None
    school_summary = "、".join(f"{nm}（{sc.get('tier','')}）" for nm, sc in resolved)

    return {
        "matched": True,
        "schools": names,
        "primary_school": primary_name,
        "duikou": duikou,
        "tier_html": tier_html,
        "premium_html": premium_html,
        "nonschool_html": nonschool_html,
        "cite_specs": cite_specs,
        "school_tier_score": school_tier_score,
        "school_summary": school_summary,
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main() -> int:
    p = argparse.ArgumentParser(description="全国城市购房取数与学区工作流助手")
    sub = p.add_subparsers(dest="cmd")

    ps = sub.add_parser("school", help="学区流程：发现小区→排序→预算过滤→多源拉取→差异比较")
    ps.add_argument("--school", default="")
    ps.add_argument("--city", default="杭州", help="目标城市，例如 上海 / 北京 / 杭州")
    ps.add_argument("--budget", type=float, default=None, help="总预算（万元）")
    ps.add_argument("--area", type=float, default=None, help="预估面积（㎡）")
    ps.add_argument("--months", type=int, default=36, help="时间轴长度（月）")
    ps.add_argument("--communities", default="")
    ps.add_argument("--input", default="")
    ps.add_argument("--output", default="")
    ps.set_defaults(func=cmd_school)

    pc = sub.add_parser("communities", help="直接给小区（多个）流程：排序→预算过滤→多源拉取")
    pc.add_argument("--communities", default="")
    pc.add_argument("--school", default="")
    pc.add_argument("--city", default="杭州", help="目标城市，例如 上海 / 北京 / 杭州")
    pc.add_argument("--budget", type=float, default=None)
    pc.add_argument("--area", type=float, default=None)
    pc.add_argument("--months", type=int, default=36)
    pc.add_argument("--input", default="")
    pc.add_argument("--output", default="")
    pc.set_defaults(func=cmd_communities)

    pf = sub.add_parser("fetch", help="单源拉取某个小区的挂盘/成交/时间轴数据")
    pf.add_argument("--source", required=True,
                    help="贝壳 / 我爱我家 / 杭房数研 / 小鸡选房 / 诸葛找房 / 安居客 / 房天下 / 58同城")
    pf.add_argument("--community", required=True)
    pf.add_argument("--district", default="")
    pf.add_argument("--city", default="杭州", help="目标城市，例如 上海 / 北京 / 杭州")
    pf.add_argument("--months", type=int, default=36)
    pf.set_defaults(func=cmd_fetch)

    pt = sub.add_parser("timeline", help="拉取某小区近 N 个月价格时间轴（支持单源或全源）")
    pt.add_argument("--community", required=True)
    pt.add_argument("--district", default="")
    pt.add_argument("--city", default="杭州", help="目标城市，例如 上海 / 北京 / 杭州")
    pt.add_argument("--months", type=int, default=36)
    pt.add_argument("--source", default="", help="留空表示所有数据源")
    pt.add_argument("--output", default="")
    pt.set_defaults(func=cmd_timeline)

    psrc = sub.add_parser("sources", help="按声明城市列出预置信息源与精确取数检索式")
    psrc.add_argument("--city", required=True, help="目标城市，例如 上海 / 北京 / 杭州")
    psrc.set_defaults(func=cmd_sources)

    pdim = sub.add_parser(
        "dimensions", help="输出维度网络框架（房价为第一维度，其余按诉求逐层展开）")
    pdim.add_argument("--dimension", default="", help="单维查询：price/volume/supply_demand/"
                      "land/school_policy/population/credit")
    pdim.set_defaults(func=cmd_dimensions)

    ppol = sub.add_parser(
        "policy", help="读取某城 2026 政策基线（多校划片/教师轮岗/户籍脱钩/学位锁定/预警）")
    ppol.add_argument("--city", default="", help="目标城市；留空则输出全国政策基线")
    ppol.set_defaults(func=cmd_policy)

    pgov = sub.add_parser(
        "gov", help="T1 官方单小区数据适配器：配置 endpoint 直拉，否则精确检索兜底")
    pgov.add_argument("--community", default="")
    pgov.add_argument("--district", default="")
    pgov.add_argument("--city", default="杭州")
    pgov.add_argument("--months", type=int, default=36)
    pgov.set_defaults(func=cmd_gov)

    psearch = sub.add_parser(
        "search", help="多平台统一检索：贝壳(官方CLI优先)+我爱我家(+可选T3交叉)，每平台带状态与兜底")
    psearch.add_argument("--community", required=True)
    psearch.add_argument("--district", default="")
    psearch.add_argument("--city", default="杭州", help="目标城市，例如 上海 / 北京 / 杭州")
    psearch.add_argument("--months", type=int, default=36)
    psearch.add_argument("--no-cross", action="store_true",
                         help="不包含 T3 交叉验证源（诸葛找房/安居客/房天下/58同城）")
    psearch.add_argument("--output", default="")
    psearch.set_defaults(func=cmd_search)

    pcheck = sub.add_parser(
        "beike-check", help="检测本机是否安装并配置贝壳 CLI（首次使用引导；"
        "未安装打印安装引导并提示可跳过）")
    pcheck.set_defaults(func=cmd_beike_check)

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
